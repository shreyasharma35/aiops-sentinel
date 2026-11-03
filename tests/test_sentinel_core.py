"""
Unit & Integration Tests for AIOps Sentinel Core Engine
Verifies Adaptive Thresholds (MAD), ML Anomaly Detection, Incident Correlation,
Explainable RCA, AI Runbook Generation, and Controlled Automated Recovery.
"""

import pytest
import asyncio
import numpy as np
from backend.database import init_db
from backend.sentinel.adaptive_thresholds import adaptive_engine
from backend.sentinel.anomaly_detector import ml_detector
from backend.sentinel.incident_engine import incident_engine
from backend.sentinel.root_cause_analyzer import rca_analyzer
from backend.sentinel.ai_runbook import runbook_generator
from backend.sentinel.recovery_engine import recovery_engine
from backend.sentinel.simulation_engine import simulation_engine
from backend.sentinel.service_dependency import dependency_engine

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db()

def test_adaptive_threshold_mad_calculation():
    """Verify Median Absolute Deviation (MAD) calculates robust adaptive bounds."""
    # Baseline normal values around 150-250ms
    normal_values = [150.0, 160.0, 155.0, 170.0, 165.0, 158.0, 162.0, 168.0, 152.0, 175.0]
    
    thresholds = adaptive_engine.calculate_mad_thresholds(
        values=normal_values,
        static_warning=400.0,
        static_critical=1000.0,
        multiplier=3.0
    )

    assert thresholds["is_adaptive_active"] is True
    assert thresholds["median"] > 140.0 and thresholds["median"] < 180.0
    assert thresholds["warning_threshold"] > thresholds["median"]
    assert thresholds["critical_threshold"] > thresholds["warning_threshold"]

def test_ml_isolation_forest_anomaly_detection():
    """Verify Isolation Forest training and multivariate anomaly scoring."""
    service_name = "payment-service"
    
    # 1. Create clean baseline training samples with natural variance
    np.random.seed(42)
    clean_samples = []
    for _ in range(30):
        clean_samples.append({
            "cpu_percent": float(15.0 + np.random.normal(0, 1.5)),
            "memory_percent": float(35.0 + np.random.normal(0, 2.0)),
            "latency_ms": float(160.0 + np.random.normal(0, 12.0)),
            "request_count": float(10.0 + np.random.normal(0, 1.0)),
            "error_rate": 0.0
        })

    train_res = ml_detector.train_model_for_service(service_name, clean_samples)
    assert train_res["trained"] is True

    # 2. Test normal input
    normal_input = {"cpu_percent": 16.0, "memory_percent": 36.0, "latency_ms": 170.0, "request_count": 10.0, "error_rate": 0.0}
    normal_pred = ml_detector.predict_anomaly(service_name, normal_input, {"median": 160.0})
    assert normal_pred["is_ml_anomaly"] is False
    assert normal_pred["anomaly_score"] < 0.65

    # 3. Test extreme outlier (high latency + high errors)
    outlier_input = {"cpu_percent": 88.0, "memory_percent": 75.0, "latency_ms": 3500.0, "request_count": 50.0, "error_rate": 0.8}
    outlier_pred = ml_detector.predict_anomaly(service_name, outlier_input, {"median": 160.0})
    assert outlier_pred["is_ml_anomaly"] is True
    assert outlier_pred["anomaly_score"] >= 0.50
    assert "Latency" in outlier_pred["explanation"]

def test_incident_correlation_and_deduplication():
    """Verify cascading alerts are correlated into a single unified incident."""
    svc = "payment-service"

    # Trigger alert
    inc = incident_engine.process_service_alert(
        service_name=svc,
        severity="CRITICAL",
        metric_name="latency_ms",
        observed_value=3200.0,
        baseline_value=220.0,
        detection_source="DUAL_CONFIRMED",
        explanation="Payment latency 3200ms exceeded critical MAD threshold"
    )

    assert inc is not None
    assert inc["incident_id"].startswith("INC-")
    assert inc["affected_service"] == svc
    assert inc["status"] == "ACTIVE"
    assert len(inc["evidence"]) >= 1

    # Second alert on same service must be deduplicated into same incident
    inc_second = incident_engine.process_service_alert(
        service_name=svc,
        severity="CRITICAL",
        metric_name="latency_ms",
        observed_value=3400.0,
        baseline_value=220.0,
        detection_source="DUAL_CONFIRMED",
        explanation="Subsequent high latency tick"
    )

    assert inc_second["incident_id"] == inc["incident_id"]

def test_explainable_rca_ranking():
    """Verify RCA engine investigates dependencies, evidence, and produces ranked hypotheses."""
    incidents = incident_engine.get_all_incidents()
    assert len(incidents) > 0
    active_inc = incidents[0]

    rca = rca_analyzer.analyze_incident(active_inc["incident_id"])
    assert "ranked_candidates" in rca
    assert len(rca["ranked_candidates"]) > 0

    top_cand = rca["ranked_candidates"][0]
    assert "cause_title" in top_cand
    assert "confidence_score" in top_cand
    assert top_cand["confidence_score"] > 0.5
    assert len(top_cand["observed_facts"]) > 0

def test_ai_runbook_generation():
    """Verify AI runbook generator produces structured markdown with recommended action."""
    incidents = incident_engine.get_all_incidents()
    active_inc = incidents[0]
    rca = rca_analyzer.analyze_incident(active_inc["incident_id"])

    runbook = runbook_generator.generate_runbook(active_inc["incident_id"], rca)
    assert runbook["markdown_content"] is not None
    assert "Incident" in runbook["markdown_content"]
    assert "Runbook" in runbook["markdown_content"]
    assert runbook["recommended_action"] in [
        "RESTART_PAYMENT_CIRCUIT_BREAKER", "RESET_DATABASE_CONNECTIONS", 
        "FLUSH_PRODUCT_CACHE", "RESTART_SERVICE", "SCALE_WORKERS"
    ]

def test_controlled_recovery_approval_and_verification():
    """Verify human approval execution of allowlisted recovery and post-verification."""
    async def _run():
        incidents = incident_engine.get_all_incidents()
        active_inc = incidents[0]

        pending = recovery_engine.get_pending_actions()
        assert len(pending) > 0
        action = pending[0]

        # Execute recovery with human approval
        result = await recovery_engine.execute_approved_recovery(
            action_id=action["action_id"],
            approver="Automated Test SRE",
            notes="Automated verification test"
        )

        assert result["status"] == "COMPLETED"
        assert result["post_recovery_health"] == "HEALTHY"
        assert result["verification_passed"] is True
        assert "audit_log" in result

    asyncio.run(_run())

def test_chaos_simulation_toggle():
    """Verify chaos simulation engine starts and stops scenarios cleanly."""
    res_start = simulation_engine.start_scenario("product_latency", {"delay_ms": 2000})
    assert res_start["status"] == "RUNNING"
    assert "product_latency" in simulation_engine.active_scenarios

    res_stop = simulation_engine.stop_scenario("product_latency")
    assert res_stop["status"] == "STOPPED"
    assert "product_latency" not in simulation_engine.active_scenarios

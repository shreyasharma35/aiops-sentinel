"""
AIOps Sentinel - Background Telemetry Collector & Background Traffic Generator
Periodically aggregates live microservice metrics, executes adaptive threshold evaluation,
triggers ML anomaly detection, and drives the background shopper simulator.
"""

import asyncio
import time
import random
import json
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List

from backend.config import config
from backend.database import db_session
from backend.telemetry import (
    RECENT_METRICS_BUFFER,
    get_current_host_metrics,
    append_structured_log
)
from backend.sentinel.adaptive_thresholds import adaptive_engine
from backend.sentinel.anomaly_detector import ml_detector
from backend.sentinel.incident_engine import incident_engine

class TelemetryCollector:
    def __init__(self):
        self.is_running = False
        self.task: asyncio.Task = None
        self.traffic_generator_enabled = True
        self.traffic_task: asyncio.Task = None
        
        # In-memory service health state cache
        self.service_health_cache: Dict[str, Dict[str, Any]] = {}
        self.total_requests_recorded = 0

    async def start(self):
        """Start the background collector and traffic simulator loops."""
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._collector_loop())
            self.traffic_task = asyncio.create_task(self._traffic_loop())
            append_structured_log(
                service="database-service",
                level="INFO",
                message="Telemetry Collector & Autonomous Shopper Traffic Daemon started."
            )

    async def stop(self):
        """Stop background tasks."""
        self.is_running = False
        if self.task:
            self.task.cancel()
        if self.traffic_task:
            self.traffic_task.cancel()

    async def _collector_loop(self):
        """Main periodic monitoring loop."""
        iteration = 0
        while self.is_running:
            try:
                iteration += 1
                await self._collect_and_evaluate_all_services(iteration)
            except Exception as e:
                append_structured_log(
                    service="database-service",
                    level="ERROR",
                    message=f"Collector cycle exception: {str(e)}"
                )
            await asyncio.sleep(config.TELEMETRY_INTERVAL_SECONDS)

    async def _collect_and_evaluate_all_services(self, iteration: int):
        """Inspect telemetry buffers and stored database metrics to evaluate thresholds, train ML, and log anomalies."""
        host = get_current_host_metrics()

        for svc_name in config.SERVICES:
            buffer = list(RECENT_METRICS_BUFFER.get(svc_name, []))

            # Query historical metrics from SQLite service_metrics table
            db_observations = []
            try:
                with db_session() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT latency_ms, is_error, cpu_percent, memory_percent
                        FROM service_metrics
                        WHERE service_name = ?
                        ORDER BY id DESC
                        LIMIT 60;
                    """, (svc_name,))
                    db_rows = cursor.fetchall()
                    for r in db_rows:
                        db_observations.append({
                            "latency_ms": r["latency_ms"],
                            "is_error": r["is_error"],
                            "cpu_percent": r["cpu_percent"],
                            "memory_percent": r["memory_percent"]
                        })
            except Exception:
                pass

            # Combine in-memory buffer with stored database observations
            all_observations = list(buffer)
            for obs in db_observations:
                if len(all_observations) < 80:
                    all_observations.append(obs)

            # Determine actual metrics
            if buffer:
                current_lat = buffer[-1]["latency_ms"]
                errors = [b["is_error"] for b in buffer]
                error_rate = (sum(errors) / len(errors)) if errors else 0.0
                request_count = len(buffer)
            elif db_observations:
                current_lat = db_observations[0]["latency_ms"]
                errors = [o["is_error"] for o in db_observations[:20]]
                error_rate = (sum(errors) / len(errors)) if errors else 0.0
                request_count = len(db_observations)
            else:
                # Nominal baseline probe when service has not received requests yet
                current_lat = 120.0
                error_rate = 0.0
                request_count = 0

            # Extract clean observations for MAD baseline calculation
            clean_history = [o["latency_ms"] for o in all_observations if o["is_error"] == 0]
            latencies = [o["latency_ms"] for o in all_observations] if all_observations else [current_lat]
            p95_lat = float(np.percentile(latencies, 95)) if len(latencies) >= 5 else current_lat

            # 1. Adaptive Threshold Evaluation
            eval_result = adaptive_engine.evaluate_metric(
                service_name=svc_name,
                current_value=current_lat,
                historical_clean_values=clean_history
            )
            baseline_stats = eval_result["thresholds"]

            # Persist calculated adaptive thresholds into SQLite threshold_configs table
            try:
                with db_session() as conn:
                    conn.execute("""
                        UPDATE threshold_configs
                        SET rolling_median = ?,
                            rolling_mad = ?,
                            dynamic_warning = ?,
                            dynamic_critical = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE service_name = ?;
                    """, (
                        baseline_stats.get("median", 0.0),
                        baseline_stats.get("mad", 0.0),
                        baseline_stats.get("warning_threshold", 0.0),
                        baseline_stats.get("critical_threshold", 0.0),
                        svc_name
                    ))
            except Exception:
                pass

            # 2. ML Isolation Forest Training & Anomaly Evaluation
            current_vector = {
                "cpu_percent": host["cpu_percent"],
                "memory_percent": host["memory_percent"],
                "latency_ms": current_lat,
                "request_count": request_count,
                "error_rate": error_rate
            }

            # Train Isolation Forest using stored clean historical observations if not yet trained
            if not ml_detector.is_trained[svc_name] and len(clean_history) >= config.MIN_TRAINING_SAMPLES:
                training_samples = []
                for o in all_observations:
                    if o.get("is_error", 0) == 0:
                        training_samples.append({
                            "cpu_percent": o.get("cpu_percent", 15.0),
                            "memory_percent": o.get("memory_percent", 35.0),
                            "latency_ms": o.get("latency_ms", 150.0),
                            "request_count": max(1, request_count),
                            "error_rate": 0.0
                        })
                if len(training_samples) >= config.MIN_TRAINING_SAMPLES:
                    ml_detector.train_model_for_service(svc_name, training_samples)

            ml_result = ml_detector.predict_anomaly(
                service_name=svc_name,
                current_metrics=current_vector,
                baseline_stats=baseline_stats
            )

            # 3. Overall Service Health Classification
            mad_severity = eval_result["severity"]
            is_ml_anom = ml_result.get("is_ml_anomaly", False)
            
            if mad_severity == "CRITICAL" or error_rate > 0.15:
                health_status = "CRITICAL"
            elif mad_severity in ("WARNING", "TRANSIENT_WARNING") or error_rate > 0.05 or is_ml_anom:
                health_status = "WARNING"
            else:
                health_status = "HEALTHY"

            # 4. Multi-Signal Anomaly Logging & Incident Declaration
            is_anomaly = (health_status in ("CRITICAL", "WARNING"))
            if is_anomaly:
                if is_ml_anom and eval_result.get("is_persistent", False):
                    detection_method = "DUAL_CONFIRMED"
                elif is_ml_anom:
                    detection_method = "ISOLATION_FOREST_ML"
                else:
                    detection_method = "STATISTICAL_MAD"

                explanation = f"{baseline_stats.get('reason', '')} Observed Latency: {current_lat:.1f}ms. {ml_result.get('explanation', '')}"
                is_incident_declared = 1 if (eval_result.get("is_persistent", False) or detection_method == "DUAL_CONFIRMED") else 0

                # Insert anomaly into SQLite anomalies table
                try:
                    with db_session() as conn:
                        conn.execute("""
                            INSERT INTO anomalies 
                            (service_name, detection_method, anomaly_score, metrics_json, explanation, is_incident)
                            VALUES (?, ?, ?, ?, ?, ?);
                        """, (
                            svc_name,
                            detection_method,
                            ml_result.get("anomaly_score", 0.0),
                            json.dumps(current_vector),
                            explanation,
                            is_incident_declared
                        ))
                except Exception:
                    pass

                # If incident condition met, declare/correlate in Incident Engine
                if is_incident_declared:
                    incident_engine.process_service_alert(
                        service_name=svc_name,
                        severity=health_status,
                        metric_name="latency_ms" if current_lat > baseline_stats.get("warning_threshold", 500) else "error_rate",
                        observed_value=current_lat,
                        baseline_value=baseline_stats["median"],
                        detection_source=detection_method,
                        explanation=explanation
                    )

            # Calculate SLO compliance
            slo = config.SERVICE_SLOS.get(svc_name)
            target_p95 = slo.target_p95_latency_ms if slo else 400.0
            slo_compliance = 100.0 if p95_lat <= target_p95 and error_rate <= (slo.max_error_rate_pct / 100.0 if slo else 0.02) else 75.0

            self.service_health_cache[svc_name] = {
                "service_name": svc_name,
                "status": health_status,
                "current_latency_ms": round(current_lat, 2),
                "p95_latency_ms": round(p95_lat, 2),
                "error_rate_pct": round(error_rate * 100, 2),
                "request_count_1m": request_count,
                "cpu_percent": host["cpu_percent"],
                "memory_percent": host["memory_percent"],
                "slo_compliance_pct": round(slo_compliance, 1),
                "active_anomalies_count": 1 if health_status in ("CRITICAL", "WARNING") else 0,
                "thresholds": baseline_stats,
                "ml_anomaly": ml_result,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

    async def _traffic_loop(self):
        """Simulates autonomous customer shopping traffic in the background."""
        from backend.services.product_service import product_service
        from backend.services.cart_service import cart_service
        from backend.services.order_service import order_service

        session_id = "shopper-daemon-session"
        while self.is_running:
            if not self.traffic_generator_enabled:
                await asyncio.sleep(3.0)
                continue

            try:
                # Action A: Browse catalog
                await product_service.get_all_products()
                self.total_requests_recorded += 1
                await asyncio.sleep(random.uniform(0.8, 1.8))

                # Action B: View specific product
                prod_id = random.randint(1, 15)
                await product_service.get_product_by_id(prod_id)
                self.total_requests_recorded += 1
                await asyncio.sleep(random.uniform(0.6, 1.4))

                # Action C: Randomly add to cart
                if random.random() < 0.6:
                    await cart_service.add_item(session_id, prod_id, quantity=1)
                    self.total_requests_recorded += 1
                    await asyncio.sleep(random.uniform(0.8, 1.6))

                # Action D: Occasionally place an order
                if random.random() < 0.35:
                    cart = await cart_service.get_cart(session_id)
                    if cart["items"]:
                        await order_service.create_order(
                            session_id=session_id,
                            customer_name="Autonomous Demo Shopper",
                            customer_email="shopper@sentinel.local",
                            card_number="4242424242424242"
                        )
                        self.total_requests_recorded += 2

            except Exception:
                pass  # Exceptions during chaos are collected naturally via TelemetryMiddleware

            await asyncio.sleep(random.uniform(1.0, 2.5))

    def get_snapshot(self) -> Dict[str, Any]:
        """Return full telemetry snapshot across host and all services."""
        host = get_current_host_metrics()
        services = self.service_health_cache
        
        # Calculate overall system status
        statuses = [s.get("status", "HEALTHY") for s in services.values()]
        if "CRITICAL" in statuses:
            overall = "CRITICAL"
        elif "WARNING" in statuses:
            overall = "WARNING"
        else:
            overall = "HEALTHY"

        from backend.sentinel.incident_engine import incident_engine
        active_inc_count = len(incident_engine.active_incident_map)

        return {
            "host": host,
            "services": services,
            "overall_health": overall,
            "total_requests_recorded": self.total_requests_recorded,
            "active_incidents_count": active_inc_count,
            "traffic_generator_enabled": self.traffic_generator_enabled
        }

telemetry_collector = TelemetryCollector()

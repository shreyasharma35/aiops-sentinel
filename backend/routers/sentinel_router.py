"""
AIOps Sentinel - SRE Observability & Control Plane API Router
Full SRE endpoints: Telemetry streaming, Adaptive Thresholds, Incidents,
Explainable RCA, Runbooks, Controlled Recovery, and Evaluation Benchmarks.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List, Optional
from backend.models import (
    TelemetrySnapshot, RecoveryApprovalRequest, ThresholdConfigUpdate
)
from backend.sentinel.collector import telemetry_collector
from backend.sentinel.incident_engine import incident_engine
from backend.sentinel.root_cause_analyzer import rca_analyzer
from backend.sentinel.ai_runbook import runbook_generator
from backend.sentinel.recovery_engine import recovery_engine
from backend.sentinel.service_dependency import dependency_engine
from backend.sentinel.deployment_monitor import deployment_monitor
from backend.sentinel.incident_memory import incident_memory
from backend.sentinel.evaluation import evaluation_engine
from backend.telemetry import get_live_structured_logs
from backend.database import db_session
from backend.config import config

router = APIRouter(prefix="/api/sentinel", tags=["AIOps Sentinel Control Plane"])

# --- TELEMETRY & OBSERVABILITY ---

@router.get("/telemetry/snapshot")
async def get_telemetry_snapshot():
    """Live snapshot of all 6 microservices, host CPU/RAM/Disk, and system state."""
    return telemetry_collector.get_snapshot()

@router.get("/logs")
async def get_sre_logs(limit: int = Query(50), service: Optional[str] = Query(None)):
    """Retrieve live structured SRE logs stream."""
    return get_live_structured_logs(limit=limit, service=service)

@router.post("/traffic/toggle")
async def toggle_traffic_generator(enabled: bool = Query(...)):
    """Enable or disable the autonomous customer shopper traffic generator."""
    telemetry_collector.traffic_generator_enabled = enabled
    return {
        "status": "SUCCESS",
        "traffic_generator_enabled": enabled,
        "message": f"Autonomous traffic generator {'ENABLED' if enabled else 'DISABLED'}"
    }

# --- SERVICES & ADAPTIVE THRESHOLDS ---

@router.get("/services")
async def get_monitored_services():
    """List all registered microservices with live health and adaptive metrics."""
    snapshot = telemetry_collector.get_snapshot()
    return snapshot.get("services", {})

@router.post("/thresholds/update")
async def update_threshold_config(update: ThresholdConfigUpdate):
    """Admin configuration: adjust static warning/critical safety limits or mode."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE threshold_configs
            SET static_warning = COALESCE(?, static_warning),
                static_critical = COALESCE(?, static_critical),
                mode = COALESCE(?, mode),
                updated_at = CURRENT_TIMESTAMP
            WHERE service_name = ?;
        """, (update.static_warning, update.static_critical, update.mode, update.service_name))
    return {"status": "SUCCESS", "message": f"Thresholds updated for {update.service_name}"}

@router.get("/anomalies")
async def list_anomalies(limit: int = Query(25), service: Optional[str] = Query(None)):
    """Retrieve recorded multivariate anomalies from SQLite anomalies table."""
    with db_session() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM anomalies WHERE 1=1"
        params = []
        if service:
            query += " AND service_name = ?"
            params.append(service)
        query += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

# --- INCIDENTS & EVIDENCE ---

@router.get("/incidents")
async def list_incidents(limit: int = Query(20)):
    """Retrieve active and historical incidents list."""
    return incident_engine.get_all_incidents(limit=limit)

@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Retrieve full incident detail, evidence timeline, and recommended runbook."""
    inc = incident_engine.get_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

# --- EXPLAINABLE ROOT CAUSE ANALYSIS (RCA) ---

@router.get("/rca/{incident_id}")
async def get_incident_rca(incident_id: str):
    """Run/retrieve multi-dimensional RCA investigation with ranked causal hypotheses."""
    rca = rca_analyzer.analyze_incident(incident_id)
    if not rca:
        raise HTTPException(status_code=404, detail="Incident not found for RCA")
    return rca

# --- SERVICE DEPENDENCY & BLAST RADIUS ---

@router.get("/topology")
async def get_service_topology():
    """Return live service dependency graph topology for interactive Vis.js visualization."""
    snapshot = telemetry_collector.get_snapshot()
    service_health = {svc: data.get("status", "HEALTHY") for svc, data in snapshot.get("services", {}).items()}
    return dependency_engine.get_topology_graph(service_health)

@router.get("/blast-radius/{service_name}")
async def get_blast_radius(service_name: str):
    """Calculate blast radius and impacted user operations for a target service."""
    return dependency_engine.calculate_blast_radius(service_name)

# --- DEPLOYMENTS (CI/CD CORRELATION) ---

@router.get("/deployments")
async def get_deployments(limit: int = Query(10)):
    """List recent deployment release history."""
    return deployment_monitor.get_recent_deployments(limit=limit)

@router.post("/deployments")
async def record_deployment(
    commit_hash: str = Query(...),
    version: str = Query(...),
    author: str = Query("CI/CD Bot"),
    message: str = Query("Automated production release"),
    affected_services: List[str] = Body(["payment-service", "order-service"])
):
    """Record a new deployment event (simulating GitHub Actions webhook)."""
    return deployment_monitor.record_deployment(commit_hash, version, author, message, affected_services)

# --- CONTROLLED RECOVERY & AUDIT LOGS ---

@router.get("/recovery/pending")
async def get_pending_recoveries():
    """Retrieve all recovery actions currently awaiting human approval."""
    return recovery_engine.get_pending_actions()

@router.post("/recovery/approve")
async def approve_recovery_action(req: RecoveryApprovalRequest):
    """
    Submit mandatory human approval to execute an allowlisted recovery action.
    Triggers execution, post-recovery verification, and audit logging.
    """
    try:
        result = await recovery_engine.execute_approved_recovery(
            action_id=req.action_id,
            approver=req.approver_name,
            notes=req.notes
        )
        return result
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recovery/audit")
async def get_recovery_audit_logs(limit: int = Query(25)):
    """List historical recovery execution logs and verification outcomes."""
    return recovery_engine.get_audit_logs(limit=limit)

# --- HISTORICAL INCIDENT MEMORY ---

@router.get("/memory/search")
async def search_similar_incidents(
    service: str = Query("payment-service"),
    query: str = Query("gateway timeout latency")
):
    """Retrieve similar past incidents and their verified resolution paths."""
    return incident_memory.find_similar_incidents(service, query)

# --- PERFORMANCE EVALUATION & BENCHMARKS ---

@router.get("/evaluation")
async def get_evaluation_report():
    """Empirical MTTD, MTTR, False Positive Rate, and comparative performance metrics."""
    return evaluation_engine.get_evaluation_metrics()

# --- INCIDENT STATUS MANAGEMENT & SYSTEM STATS ---

@router.post("/incidents/{incident_id}/status")
async def update_incident_status(incident_id: str, status: str = Query(...)):
    """Update incident status (OPEN, INVESTIGATING, RESOLVED)."""
    with db_session() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE incidents SET status = ? WHERE incident_id = ?;", (status.upper(), incident_id))
        if status.upper() == "RESOLVED":
            cursor.execute("UPDATE incidents SET resolved_at = CURRENT_TIMESTAMP WHERE incident_id = ?;", (incident_id,))
    # Clear from active incident map if resolved
    if status.upper() == "RESOLVED":
        for svc, inc_id in list(incident_engine.active_incident_map.items()):
            if inc_id == incident_id:
                del incident_engine.active_incident_map[svc]
    return {"status": "SUCCESS", "incident_id": incident_id, "new_status": status.upper()}

@router.get("/system/stats")
async def get_system_stats():
    """Database metrics, table row counts, and storage stats for Settings page."""
    import os
    db_size = 0
    wal_size = 0
    try:
        if config.DB_PATH.exists():
            db_size = os.path.getsize(config.DB_PATH)
        wal_path = config.DB_PATH.with_suffix(".db-wal")
        if wal_path.exists():
            wal_size = os.path.getsize(wal_path)
    except Exception:
        pass

    counts = {}
    with db_session() as conn:
        cursor = conn.cursor()
        for tbl in ["products", "orders", "payments", "service_metrics", "anomalies", "incidents", "recovery_actions", "deployment_events"]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
                counts[tbl] = cursor.fetchone()[0]
            except Exception:
                counts[tbl] = 0

    return {
        "db_size_bytes": db_size,
        "db_size_kb": round(db_size / 1024, 2),
        "wal_size_bytes": wal_size,
        "wal_size_kb": round(wal_size / 1024, 2),
        "table_counts": counts,
        "telemetry_interval": config.TELEMETRY_INTERVAL_SECONDS,
        "adaptive_window_size": config.ADAPTIVE_WINDOW_SIZE,
        "adaptive_mad_multiplier": config.ADAPTIVE_MAD_MULTIPLIER,
        "min_observations": config.MIN_OBSERVATIONS_FOR_ADAPTIVE,
        "ollama_base_url": config.OLLAMA_BASE_URL,
        "ollama_model": config.OLLAMA_MODEL,
        "services": config.SERVICES
    }

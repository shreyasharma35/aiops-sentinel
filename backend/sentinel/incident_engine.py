"""
AIOps Sentinel - Incident Engine & Multi-Signal Correlation
Correlates cascading alerts across services, eliminates alert storms,
deduplicates incidents, and manages the incident lifecycle.
"""

import uuid
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from backend.database import db_session
from backend.sentinel.service_dependency import dependency_engine
from backend.telemetry import append_structured_log

class IncidentEngine:
    def __init__(self):
        # In-memory mapping of active incident per service: service_name -> incident_id
        self.active_incident_map: Dict[str, str] = {}
        # Cooldown timestamps to prevent re-triggering immediately after resolution
        self.cooldown_timestamps: Dict[str, float] = {}
        self.cooldown_seconds = 20.0

    def process_service_alert(
        self,
        service_name: str,
        severity: str,
        metric_name: str,
        observed_value: float,
        baseline_value: float,
        detection_source: str,
        explanation: str
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate an alert signal from Adaptive Thresholds or ML Anomaly Detector.
        Correlates with existing active incidents or downstream dependencies,
        or creates a new unified incident.
        """
        now = time.time()
        
        # Check cooldown to prevent flap
        if (now - self.cooldown_timestamps.get(service_name, 0)) < self.cooldown_seconds:
            return None

        # 1. Check if this service is already part of an active incident
        if service_name in self.active_incident_map:
            incident_id = self.active_incident_map[service_name]
            self._add_evidence(
                incident_id=incident_id,
                evidence_type=detection_source,
                metric_name=metric_name,
                observed=observed_value,
                baseline=baseline_value,
                description=f"Ongoing alert: {explanation}"
            )
            return self.get_incident_by_id(incident_id)

        # 2. Check if a downstream dependency already has an active incident (correlation!)
        # E.g. If order-service is failing, but payment-service is already active, correlate into payment incident!
        callers = dependency_engine.callers.get(service_name, [])
        for caller in callers:
            if caller in self.active_incident_map:
                incident_id = self.active_incident_map[caller]
                self._add_evidence(
                    incident_id=incident_id,
                    evidence_type="CASCADING_FAILURE_CORRELATION",
                    metric_name=metric_name,
                    observed=observed_value,
                    baseline=baseline_value,
                    description=f"Cascading failure in caller '{caller}': {explanation}"
                )
                self.active_incident_map[service_name] = incident_id
                return self.get_incident_by_id(incident_id)

        # 3. Create a new Unified Incident
        incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        title = self._generate_incident_title(service_name, metric_name, severity)
        blast_info = dependency_engine.calculate_blast_radius(service_name)
        blast_json = json.dumps(blast_info["impacted_services"])

        with db_session() as conn:
            conn.execute("""
                INSERT INTO incidents 
                (incident_id, title, affected_service, severity, status, blast_radius_json, created_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?, CURRENT_TIMESTAMP);
            """, (incident_id, title, service_name, severity, blast_json))

        self.active_incident_map[service_name] = incident_id

        # Insert primary evidence
        self._add_evidence(
            incident_id=incident_id,
            evidence_type=detection_source,
            metric_name=metric_name,
            observed=observed_value,
            baseline=baseline_value,
            description=explanation
        )

        append_structured_log(
            service=service_name,
            level="CRITICAL" if severity == "CRITICAL" else "ERROR",
            message=f"New Incident Declared: [{incident_id}] {title}",
            metadata={"incident_id": incident_id, "service": service_name, "severity": severity}
        )

        # Auto-trigger Root Cause Analysis and Runbook Generation
        from backend.sentinel.root_cause_analyzer import rca_analyzer
        from backend.sentinel.ai_runbook import runbook_generator
        from backend.sentinel.recovery_engine import recovery_engine

        rca_result = rca_analyzer.analyze_incident(incident_id)
        runbook = runbook_generator.generate_runbook(incident_id, rca_result)
        recovery_engine.propose_recovery_action(incident_id, service_name, rca_result)

        return self.get_incident_by_id(incident_id)

    def resolve_incident(self, incident_id: str, resolved_by: str, action_taken: str):
        """Mark an incident as resolved, log MTTR, and initiate cooldown."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT affected_service, created_at FROM incidents WHERE incident_id = ?;", (incident_id,))
            row = cursor.fetchone()
            if row:
                svc = row["affected_service"]
                conn.execute("""
                    UPDATE incidents 
                    SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP, resolved_by = ?, resolution_action = ?
                    WHERE incident_id = ?;
                """, (resolved_by, action_taken, incident_id))

                # Remove from active mapping
                if svc in self.active_incident_map:
                    del self.active_incident_map[svc]
                self.cooldown_timestamps[svc] = time.time()

                append_structured_log(
                    service=svc,
                    level="INFO",
                    message=f"Incident {incident_id} successfully marked RESOLVED by {resolved_by}. Action: {action_taken}"
                )

    def _add_evidence(self, incident_id: str, evidence_type: str, metric_name: str, observed: float, baseline: float, description: str):
        try:
            with db_session() as conn:
                conn.execute("""
                    INSERT INTO incident_evidence 
                    (incident_id, evidence_type, metric_name, observed_value, expected_baseline, description)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (incident_id, evidence_type, metric_name, observed, baseline, description))
        except Exception:
            pass

    def _generate_incident_title(self, service: str, metric: str, severity: str) -> str:
        if "payment" in service:
            return "Payment Gateway Degradation & Downstream Transaction Bottleneck"
        elif "order" in service:
            return "Order Service Dispatch Queue Failure & 500 Spike"
        elif "database" in service:
            return "Database Service Connection Contention & Table Lock"
        elif "product" in service:
            return "Product Catalog Latency Surge & Cache Degradation"
        return f"{service.replace('-', ' ').title()} Performance Degradation ({severity})"

    def get_incident_by_id(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Fetch complete incident representation with evidence."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM incidents WHERE incident_id = ?;", (incident_id,))
            inc = cursor.fetchone()
            if not inc:
                return None

            cursor.execute("SELECT * FROM incident_evidence WHERE incident_id = ? ORDER BY id ASC;", (incident_id,))
            ev_rows = cursor.fetchall()
            evidence = []
            for ev in ev_rows:
                evidence.append({
                    "evidence_type": ev["evidence_type"],
                    "metric_name": ev["metric_name"],
                    "observed_value": ev["observed_value"],
                    "expected_baseline": ev["expected_baseline"],
                    "description": ev["description"],
                    "created_at": ev["created_at"]
                })

            # Check for linked recovery action
            cursor.execute("SELECT action_id, action_name, status FROM recovery_actions WHERE incident_id = ? ORDER BY id DESC LIMIT 1;", (incident_id,))
            rec_row = cursor.fetchone()
            rec_action = dict(rec_row) if rec_row else None

            # Check for runbook
            cursor.execute("SELECT markdown_content, recommended_action FROM runbooks WHERE incident_id = ?;", (incident_id,))
            rb_row = cursor.fetchone()

            return {
                "incident_id": inc["incident_id"],
                "title": inc["title"],
                "affected_service": inc["affected_service"],
                "severity": inc["severity"],
                "status": inc["status"],
                "blast_radius": json.loads(inc["blast_radius_json"]) if inc["blast_radius_json"] else [],
                "created_at": inc["created_at"],
                "resolved_at": inc["resolved_at"],
                "resolved_by": inc["resolved_by"],
                "resolution_action": inc["resolution_action"],
                "evidence": evidence,
                "recovery_action": rec_action,
                "runbook": {
                    "content": rb_row["markdown_content"] if rb_row else None,
                    "recommended_action": rb_row["recommended_action"] if rb_row else None
                } if rb_row else None
            }

    def get_all_incidents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent incidents list."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT incident_id FROM incidents ORDER BY id DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            return [self.get_incident_by_id(r["incident_id"]) for r in rows if r["incident_id"]]

incident_engine = IncidentEngine()

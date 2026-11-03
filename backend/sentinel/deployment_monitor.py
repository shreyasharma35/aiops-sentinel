"""
AIOps Sentinel - Deployment Correlation Engine
Captures CI/CD GitHub Actions release events, correlates deployment timestamps
with metric degradation onsets, and flags potential software regressions.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from backend.database import db_session
from backend.telemetry import append_structured_log

class DeploymentMonitor:
    def __init__(self):
        self.correlation_window_minutes = 15.0

    def record_deployment(
        self,
        commit_hash: str,
        version: str,
        author: str,
        message: str,
        affected_services: List[str]
    ) -> Dict[str, Any]:
        """Record a new deployment event (simulating GitHub Actions webhook)."""
        services_json = json.dumps(affected_services)
        with db_session() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO deployment_events 
                (commit_hash, version, author, message, status, deployed_at, affected_services_json)
                VALUES (?, ?, ?, ?, 'SUCCESS', CURRENT_TIMESTAMP, ?);
            """, (commit_hash, version, author, message, services_json))

        append_structured_log(
            service=affected_services[0] if affected_services else "system",
            level="INFO",
            message=f"Deployment {version} ({commit_hash[:7]}) recorded by {author}: {message}",
            metadata={"version": version, "commit": commit_hash}
        )

        return {
            "version": version,
            "commit_hash": commit_hash,
            "author": author,
            "affected_services": affected_services,
            "status": "RECORDED"
        }

    def correlate_incident_with_deployments(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Check if any recent deployment event occurred within the correlation window
        affecting this service or related microservices.
        """
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT commit_hash, version, author, message, status, deployed_at, affected_services_json
                FROM deployment_events
                ORDER BY deployed_at DESC
                LIMIT 5;
            """)
            rows = cursor.fetchall()

        now = datetime.now(timezone.utc)
        for r in rows:
            try:
                # Handle ISO or SQLite timestamp
                dep_time_str = r["deployed_at"]
                if "T" in dep_time_str:
                    dep_time = datetime.fromisoformat(dep_time_str)
                else:
                    dep_time = datetime.strptime(dep_time_str, "%Y-%m-%d %H:%M:%S")

                elapsed_mins = (now - dep_time).total_seconds() / 60.0
                if 0 <= elapsed_mins <= self.correlation_window_minutes:
                    affected_services = json.loads(r["affected_services_json"])
                    if service_name in affected_services or "all" in affected_services:
                        # High correlation
                        confidence = round(max(0.60, 0.95 - (elapsed_mins / self.correlation_window_minutes) * 0.35), 2)
                        return {
                            "correlated": True,
                            "version": r["version"],
                            "commit_hash": r["commit_hash"],
                            "author": r["author"],
                            "message": r["message"],
                            "deployed_at": r["deployed_at"],
                            "elapsed_minutes": round(elapsed_mins, 1),
                            "confidence": confidence,
                            "explanation": (
                                f"Service '{service_name}' degraded approximately {round(elapsed_mins, 1)} minutes "
                                f"after deployment {r['version']} ('{r['message']}'). Possible code or config regression."
                            )
                        }
            except Exception:
                continue

        return None

    def get_recent_deployments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List deployment event history."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT commit_hash, version, author, message, status, deployed_at, affected_services_json
                FROM deployment_events
                ORDER BY deployed_at DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()

            deployments = []
            for r in rows:
                deployments.append({
                    "commit_hash": r["commit_hash"],
                    "version": r["version"],
                    "author": r["author"],
                    "message": r["message"],
                    "status": r["status"],
                    "deployed_at": r["deployed_at"],
                    "affected_services": json.loads(r["affected_services_json"]) if r["affected_services_json"] else []
                })
            return deployments

deployment_monitor = DeploymentMonitor()

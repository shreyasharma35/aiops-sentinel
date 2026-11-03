"""
AIOps Sentinel - AI-Assisted Runbook Generator
Generates structured, step-by-step SRE remediation runbooks using local Ollama LLMs,
with a deterministic, expert SRE knowledge-base fallback when Ollama is offline.
"""

import httpx
import json
from typing import Dict, Any, Optional
from backend.config import config
from backend.database import db_session
from backend.telemetry import append_structured_log

class AIRunbookGenerator:
    def __init__(self):
        self.ollama_url = f"{config.OLLAMA_BASE_URL}/api/generate"

    def generate_runbook(self, incident_id: str, rca_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a structured remediation runbook for the incident.
        Attempts Ollama local LLM generation first; seamlessly falls back
        to expert rule-based generation if Ollama is unavailable.
        """
        service_name = rca_data.get("affected_service", "unknown-service")
        top_candidate = rca_data.get("ranked_candidates", [{}])[0]
        cause_title = top_candidate.get("cause_title", "Unclassified Anomaly")
        recommended_action = self._select_allowlisted_action(service_name, cause_title)

        markdown_content = None
        generated_by = "OLLAMA_LLM"

        # 1. Attempt Ollama Local LLM Generation
        try:
            markdown_content = self._query_ollama(service_name, rca_data, recommended_action)
        except Exception as e:
            append_structured_log(
                service=service_name,
                level="INFO",
                message=f"Local Ollama generation skipped ({str(e)}). Engaging Sentinel Rule-Based SRE Expert Engine."
            )
            markdown_content = None

        # 2. Expert SRE Rule-Based Fallback Engine
        if not markdown_content:
            generated_by = "SENTINEL_EXPERT_RCA_RULES"
            markdown_content = self._generate_expert_rulebook(service_name, rca_data, recommended_action)

        # 3. Store in SQLite runbooks table
        with db_session() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runbooks 
                (incident_id, generated_by, markdown_content, recommended_action, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (incident_id, generated_by, markdown_content, recommended_action))

        return {
            "incident_id": incident_id,
            "generated_by": generated_by,
            "recommended_action": recommended_action,
            "markdown_content": markdown_content
        }

    def _query_ollama(self, service: str, rca_data: Dict[str, Any], recommended_action: str) -> Optional[str]:
        """Query local Ollama instance with timeout guardrail."""
        prompt = f"""
You are an expert SRE and AIOps Reliability Engineer. Write a concise, actionable incident remediation runbook in Markdown for:
- Service: {service}
- Root Cause: {rca_data.get('root_cause_summary')}
- Evidence: {json.dumps(rca_data.get('ranked_candidates', [{}])[0].get('observed_facts', []))}
- Recommended Action: {recommended_action}

Include:
1. Incident Summary & Impact
2. Diagnostic Verification
3. Step-by-Step Remediation
4. Post-Recovery Verification Checklist
"""
        payload = {
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 400}
        }
        with httpx.Client(timeout=config.OLLAMA_TIMEOUT_SECONDS) as client:
            resp = client.post(self.ollama_url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response")
        return None

    def _generate_expert_rulebook(self, service: str, rca_data: Dict[str, Any], action: str) -> str:
        """Deterministic SRE expert runbook template based on observed RCA evidence."""
        top_cand = rca_data.get("ranked_candidates", [{}])[0]
        cause_title = top_cand.get("cause_title", "Performance Degradation")
        facts = top_cand.get("observed_facts", ["Metrics deviated beyond baseline limits."])
        action_desc = config.ALLOWLISTED_RECOVERY_ACTIONS.get(action, "Execute service state reset.")

        facts_md = "\n".join([f"- **Observed Fact:** {f}" for f in facts])

        return f"""# SRE Incident Remediation Runbook: {service.upper()}

## 1. Incident Executive Summary
- **Target Microservice:** `{service}`
- **Investigated Root Cause:** {cause_title}
- **Confidence Rating:** {int(top_cand.get('confidence_score', 0.85) * 100)}%
- **Status:** Requires Controlled Recovery Approval

## 2. Telemetry Evidence & Observed Symptoms
{facts_md}

## 3. Step-by-Step Diagnostic Procedures
1. **Verify Health Endpoint:** Query `http://localhost:8000/api/ecommerce/{service.split('-')[0]}/health` to assess live status code and connection latency.
2. **Inspect Error Buffers:** Check live structured logs for unhandled socket timeouts, database locks, or gateway rejections.
3. **Trace Blast Radius:** Ensure dependent downstream services (e.g., Order Checkout pipeline) are isolated from cascading thread starvation.

## 4. Recommended Recovery Action (Allowlisted)
> [!IMPORTANT]
> **Proposed Action:** `{action}`
> **Action Details:** {action_desc}

### Why this action?
Executing `{action}` clears pending socket wait queues, resets the circuit breaker trip counter, and immediately restores nominal response times without corrupting state.

## 5. Post-Recovery Verification Checklist
- [ ] Confirm service p95 latency returns below SLO threshold (< 400ms).
- [ ] Verify HTTP status codes return 200 OK across 3 consecutive health probes.
- [ ] Ensure shopping cart and checkout order operations complete normally.
- [ ] Confirm no residual deadlock exists in SQLite transaction pool.

## 6. Long-Term Prevention Guidance
- Tune downstream HTTP client timeout to 3000ms max to prevent worker thread saturation.
- Implement exponential backoff retry jitter for upstream external banking API calls.
"""

    def _select_allowlisted_action(self, service: str, cause: str) -> str:
        """Map service and root cause to allowlisted, safe recovery actions."""
        cause_lower = cause.lower()
        if "payment" in service or "banking" in cause_lower or "circuit breaker" in cause_lower:
            return "RESTART_PAYMENT_CIRCUIT_BREAKER"
        elif "database" in service or "lock" in cause_lower:
            return "RESET_DATABASE_CONNECTIONS"
        elif "product" in service or "cache" in cause_lower:
            return "FLUSH_PRODUCT_CACHE"
        elif "traffic" in cause_lower or "surge" in cause_lower:
            return "SCALE_WORKERS"
        return "RESTART_SERVICE"

runbook_generator = AIRunbookGenerator()

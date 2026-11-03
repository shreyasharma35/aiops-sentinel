"""
AIOps Sentinel - Unified Execution Runner
Starts the integrated E-Commerce Storefront and AIOps SRE Observability Control Center.
"""

import sys
import uvicorn
from backend.config import config

# Ensure stdout handles unicode cleanly on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    print("=" * 72)
    print("[*] AIOPS SENTINEL - INTELLIGENT OBSERVABILITY & AUTONOMOUS RECOVERY")
    print("    Final-Year B.Tech Minor Project (Integrated Architecture)")
    print("=" * 72)
    print(f"[>] Customer E-Commerce Storefront:  http://localhost:{config.PORT}/store")
    print(f"[>] AIOps Sentinel SRE Dashboard:    http://localhost:{config.PORT}/sentinel")
    print(f"[>] OpenAPI / Swagger Documentation: http://localhost:{config.PORT}/docs")
    print("=" * 72)
    print("[+] Core Platform Engines:")
    print("    * Fake Store API catalog ingestion & local SQLite caching")
    print("    * Telemetry & Host resource tracking (psutil)")
    print("    * Adaptive Thresholds (Rolling Median + MAD + SLO guardrails)")
    print("    * Machine Learning Anomaly Detection (Scikit-Learn Isolation Forest)")
    print("    * Multi-Signal Incident Correlation & Deduplication")
    print("    * Explainable Root Cause Analysis (Ranked Hypotheses + Evidence)")
    print("    * Service Dependency Graph & Blast-Radius Mapping")
    print("    * AI-Assisted Runbook Generator (Ollama + Expert SRE Engine)")
    print("    * Controlled Automated Recovery with Human-in-the-Loop Approval")
    print("    * Chaos Engineering & Failure Simulation Lab")
    print("    * Empirical Performance Evaluation (MTTD, MTTR, Accuracy)")
    print("=" * 72)
    print("Press CTRL+C to halt server gracefully.\n")

    uvicorn.run(
        "backend.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()

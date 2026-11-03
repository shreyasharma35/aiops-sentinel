"""
Database Service Module
Manages SQLite WAL connection health, ping latency probes,
connection pooling status, and failure simulation hooks.
"""

import time
import asyncio
from typing import Dict, Any
from backend.database import db_session
from backend.telemetry import append_structured_log

class DatabaseService:
    def __init__(self):
        self.service_name = "database-service"

    async def execute_ping(self) -> Dict[str, Any]:
        """Execute a lightweight test query measuring database ping latency."""
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        start = time.perf_counter()
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "UP", "ping_ms": duration_ms}

    def health_check(self) -> Dict[str, Any]:
        """Perform a synchronous database health probe."""
        start = time.perf_counter()
        try:
            with db_session() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode;")
                journal_mode = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM products;")
                prod_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM orders;")
                order_count = cursor.fetchone()[0]

            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            return {
                "service": self.service_name,
                "status": "UP",
                "journal_mode": str(journal_mode).upper(),
                "query_latency_ms": duration_ms,
                "tables_verified": True,
                "product_rows": prod_count,
                "order_rows": order_count
            }
        except Exception as e:
            append_structured_log(
                service=self.service_name,
                level="CRITICAL",
                message=f"Database health check failed: {str(e)}"
            )
            return {
                "service": self.service_name,
                "status": "DOWN",
                "error": str(e),
                "query_latency_ms": round((time.perf_counter() - start) * 1000, 2)
            }

database_service = DatabaseService()

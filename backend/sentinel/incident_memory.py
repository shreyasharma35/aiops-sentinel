"""
AIOps Sentinel - Historical Incident Memory & Similarity Retrieval
Stores previous incident resolution patterns, computes text and attribute similarity,
and suggests previously verified remediation actions.
"""

import re
from typing import Dict, List, Any, Optional
from backend.database import db_session

class IncidentMemory:
    def __init__(self):
        pass

    def find_similar_incidents(
        self,
        service_name: str,
        query_text: str,
        limit: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retrieve historical resolved incidents matching the service and query tokens.
        Computes token-based Jaccard similarity.
        """
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT incident_id, title, affected_service, severity, status, 
                       root_cause_summary, resolution_action, resolved_at, resolved_by
                FROM incidents
                WHERE status = 'RESOLVED' AND resolution_action IS NOT NULL
                ORDER BY id DESC
                LIMIT 50;
            """)
            rows = cursor.fetchall()

        if not rows:
            # Provide sample historical case studies if database is freshly seeded
            return self._default_historical_patterns(service_name)

        query_tokens = self._tokenize(f"{service_name} {query_text}")
        results = []

        for r in rows:
            doc_text = f"{r['affected_service']} {r['title']} {r['root_cause_summary'] or ''}"
            doc_tokens = self._tokenize(doc_text)
            
            # Jaccard similarity score
            intersection = query_tokens.intersection(doc_tokens)
            union = query_tokens.union(doc_tokens)
            similarity = round(len(intersection) / max(len(union), 1), 2)

            if r["affected_service"] == service_name:
                similarity = min(1.0, similarity + 0.35)

            if similarity > 0.15:
                results.append({
                    "incident_id": r["incident_id"],
                    "title": r["title"],
                    "affected_service": r["affected_service"],
                    "similarity_score": round(similarity, 2),
                    "root_cause_summary": r["root_cause_summary"],
                    "successful_resolution": r["resolution_action"],
                    "resolved_at": r["resolved_at"],
                    "resolved_by": r["resolved_by"]
                })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]

    def _tokenize(self, text: str) -> set:
        words = re.findall(r"\w+", text.lower())
        stopwords = {"and", "the", "in", "is", "of", "to", "for", "with", "a", "an", "on", "service"}
        return {w for w in words if w not in stopwords and len(w) > 2}

    def _default_historical_patterns(self, service: str) -> List[Dict[str, Any]]:
        """Curated baseline historical knowledge base for common failure patterns."""
        knowledge_base = [
            {
                "incident_id": "INC-HIST-001",
                "title": "Payment Gateway Timeout & Circuit Breaker Trip",
                "affected_service": "payment-service",
                "similarity_score": 0.94 if "payment" in service else 0.40,
                "root_cause_summary": "Upstream banking API latency surge triggered local circuit breaker.",
                "successful_resolution": "RESTART_PAYMENT_CIRCUIT_BREAKER - Circuit breaker reset and connection pool recycled.",
                "resolved_at": "2026-10-24 14:22:10",
                "resolved_by": "Senior SRE Lead"
            },
            {
                "incident_id": "INC-HIST-002",
                "title": "SQLite WAL Lock Contention on High Order Volume",
                "affected_service": "database-service",
                "similarity_score": 0.91 if "database" in service else 0.35,
                "root_cause_summary": "Long-running write transaction blocked concurrent order checkout workers.",
                "successful_resolution": "RESET_DATABASE_CONNECTIONS - Connection pool restarted with WAL pragmas verified.",
                "resolved_at": "2026-10-28 09:15:44",
                "resolved_by": "Database Operations"
            },
            {
                "incident_id": "INC-HIST-003",
                "title": "Product Catalog Latency Surge & Cache Miss Cascade",
                "affected_service": "product-service",
                "similarity_score": 0.88 if "product" in service else 0.30,
                "root_cause_summary": "Stale in-memory cache evicted simultaneously causing Fake Store API rate limit.",
                "successful_resolution": "FLUSH_PRODUCT_CACHE - In-memory cache invalidated and re-hydrated in background.",
                "resolved_at": "2026-10-29 18:40:02",
                "resolved_by": "Platform SRE"
            }
        ]
        return knowledge_base

incident_memory = IncidentMemory()

"""
Product Service Module
Handles catalog ingestion from Fake Store API, local SQLite caching,
category filtering, and service-level health checks.
"""

import time
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from backend.config import config
from backend.database import db_session, get_db_connection
from backend.telemetry import append_structured_log

class ProductService:
    def __init__(self):
        self.service_name = "product-service"
        self._memory_cache: Dict[str, Any] = {}
        self._cache_timestamp = 0

    async def _fetch_from_fakestore_api(self, endpoint: str) -> Optional[Any]:
        """Fetch real-time data from Fake Store API with safe timeout."""
        url = f"{config.FAKESTORE_API_URL}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=config.FAKESTORE_TIMEOUT_SECONDS) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            append_structured_log(
                service=self.service_name,
                level="WARN",
                message=f"Fake Store API fetch fallback: {str(e)}",
                metadata={"endpoint": endpoint}
            )
        return None

    async def sync_with_fakestore_api(self, force: bool = False) -> bool:
        """Fetch latest products from Fake Store API and persist to SQLite cache."""
        now = time.time()
        if not force and (now - self._cache_timestamp) < config.CATALOG_CACHE_TTL_SECONDS:
            return False

        api_data = await self._fetch_from_fakestore_api("/products")
        if api_data and isinstance(api_data, list) and len(api_data) > 0:
            with db_session() as conn:
                for item in api_data:
                    conn.execute("""
                        INSERT OR REPLACE INTO products 
                        (id, title, price, description, category, image, rating_rate, rating_count, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                    """, (
                        item.get("id"),
                        item.get("title"),
                        item.get("price"),
                        item.get("description"),
                        item.get("category"),
                        item.get("image"),
                        item.get("rating", {}).get("rate", 4.5),
                        item.get("rating", {}).get("count", 100)
                    ))
            self._cache_timestamp = now
            append_structured_log(
                service=self.service_name,
                level="INFO",
                message=f"Catalog successfully synced from Fake Store API ({len(api_data)} products updated in SQLite)."
            )
            return True
        return False

    async def get_all_products(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve products. Ingests from Fake Store API if TTL expired,
        and queries local SQLite database for sub-millisecond filtering.
        """
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        # Trigger background sync if TTL expired
        if not category and not search:
            if (time.time() - self._cache_timestamp) > config.CATALOG_CACHE_TTL_SECONDS:
                try:
                    await self.sync_with_fakestore_api(force=True)
                except Exception:
                    pass

        products = []
        with db_session() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM products WHERE 1=1"
            params = []
            if category and category.lower() != "all":
                query += " AND LOWER(category) = LOWER(?)"
                params.append(category)
            if search:
                query += " AND (LOWER(title) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?))"
                term = f"%{search}%"
                params.extend([term, term])
            query += " ORDER BY id ASC;"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            for r in rows:
                products.append({
                    "id": r["id"],
                    "title": r["title"],
                    "price": r["price"],
                    "description": r["description"],
                    "category": r["category"],
                    "image": r["image"],
                    "rating": {
                        "rate": r["rating_rate"],
                        "count": r["rating_count"]
                    }
                })

        return products

    async def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Fetch product details by ID."""
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
            r = cursor.fetchone()
            if r:
                return {
                    "id": r["id"],
                    "title": r["title"],
                    "price": r["price"],
                    "description": r["description"],
                    "category": r["category"],
                    "image": r["image"],
                    "rating": {
                        "rate": r["rating_rate"],
                        "count": r["rating_count"]
                    }
                }

        # Fallback to Fake Store API if not found in DB
        api_item = await self._fetch_from_fakestore_api(f"/products/{product_id}")
        if api_item:
            with db_session() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO products 
                    (id, title, price, description, category, image, rating_rate, rating_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    api_item.get("id"),
                    api_item.get("title"),
                    api_item.get("price"),
                    api_item.get("description"),
                    api_item.get("category"),
                    api_item.get("image"),
                    api_item.get("rating", {}).get("rate", 4.5),
                    api_item.get("rating", {}).get("count", 100)
                ))
            return api_item

        return None

    async def get_categories(self) -> List[str]:
        """Fetch distinct categories from database."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM products ORDER BY category ASC;")
            rows = cursor.fetchall()
            return [r["category"] for r in rows if r["category"]]

    def health_check(self) -> Dict[str, Any]:
        """Service-level health check."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products;")
            count = cursor.fetchone()[0]
        return {
            "service": self.service_name,
            "status": "UP" if count > 0 else "DEGRADED",
            "catalog_count": count,
            "upstream_api": config.FAKESTORE_API_URL
        }

product_service = ProductService()

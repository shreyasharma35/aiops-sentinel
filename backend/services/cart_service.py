"""
Cart Service Module
Manages shopping cart persistence in SQLite by session ID,
quantity calculations, and service-level health checks.
"""

from typing import Dict, Any, List
from backend.database import db_session
from backend.telemetry import append_structured_log

class CartService:
    def __init__(self):
        self.service_name = "cart-service"

    async def get_cart(self, session_id: str) -> Dict[str, Any]:
        """Fetch all items in the cart for a given session with total amount."""
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, session_id, product_id, title, price, image, quantity
                FROM cart_items
                WHERE session_id = ?
                ORDER BY id DESC;
            """, (session_id,))
            rows = cursor.fetchall()

            items = []
            total_amount = 0.0
            total_items = 0

            for r in rows:
                subtotal = round(r["price"] * r["quantity"], 2)
                total_amount += subtotal
                total_items += r["quantity"]
                items.append({
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "product_id": r["product_id"],
                    "title": r["title"],
                    "price": r["price"],
                    "image": r["image"],
                    "quantity": r["quantity"],
                    "subtotal": subtotal
                })

            return {
                "items": items,
                "total_items": total_items,
                "total_amount": round(total_amount, 2),
                "currency": "USD"
            }

    async def add_item(self, session_id: str, product_id: int, quantity: int = 1) -> Dict[str, Any]:
        """Add item to cart or increment quantity if already exists."""
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        with db_session() as conn:
            cursor = conn.cursor()
            # Fetch product details
            cursor.execute("SELECT title, price, image FROM products WHERE id = ?;", (product_id,))
            prod = cursor.fetchone()
            if not prod:
                raise ValueError(f"Product ID {product_id} not found in catalog")

            # Check if product is already in session cart
            cursor.execute("""
                SELECT id, quantity FROM cart_items 
                WHERE session_id = ? AND product_id = ?;
            """, (session_id, product_id))
            existing = cursor.fetchone()

            if existing:
                new_qty = existing["quantity"] + quantity
                cursor.execute("""
                    UPDATE cart_items SET quantity = ? WHERE id = ?;
                """, (new_qty, existing["id"]))
            else:
                cursor.execute("""
                    INSERT INTO cart_items (session_id, product_id, title, price, image, quantity)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (session_id, product_id, prod["title"], prod["price"], prod["image"], quantity))

        append_structured_log(
            service=self.service_name,
            level="INFO",
            message=f"Added product {product_id} (qty {quantity}) to cart session {session_id[:8]}",
            metadata={"product_id": product_id, "session_id": session_id}
        )
        return await self.get_cart(session_id)

    async def update_quantity(self, session_id: str, item_id: int, quantity: int) -> Dict[str, Any]:
        """Update quantity of specific cart line item. Removes if quantity <= 0."""
        from backend.sentinel.simulation_engine import simulation_engine
        await simulation_engine.check_and_apply_fault(self.service_name)

        with db_session() as conn:
            cursor = conn.cursor()
            if quantity <= 0:
                cursor.execute("DELETE FROM cart_items WHERE id = ? AND session_id = ?;", (item_id, session_id))
            else:
                cursor.execute("UPDATE cart_items SET quantity = ? WHERE id = ? AND session_id = ?;", (quantity, item_id, session_id))

        return await self.get_cart(session_id)

    async def remove_item(self, session_id: str, item_id: int) -> Dict[str, Any]:
        """Remove a line item from session cart."""
        return await self.update_quantity(session_id, item_id, 0)

    async def clear_cart(self, session_id: str) -> Dict[str, Any]:
        """Clear all items from session cart."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cart_items WHERE session_id = ?;", (session_id,))
        return await self.get_cart(session_id)

    def health_check(self) -> Dict[str, Any]:
        """Service health check."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cart_items;")
            active_items = cursor.fetchone()[0]
        return {
            "service": self.service_name,
            "status": "UP",
            "active_cart_items_count": active_items
        }

cart_service = CartService()

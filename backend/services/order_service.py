"""
Order Service Module
Orchestrates order placement, cart retrieval, payment processing,
and order state lifecycle in SQLite.
"""

import uuid
import json
import asyncio
from typing import Dict, Any, List, Optional
from backend.database import db_session
from backend.services.cart_service import cart_service
from backend.services.payment_service import payment_service, PaymentGatewayError
from backend.telemetry import append_structured_log

class OrderService:
    def __init__(self):
        self.service_name = "order-service"

    async def create_order(
        self,
        session_id: str,
        customer_name: str,
        customer_email: str,
        card_number: str
    ) -> Dict[str, Any]:
        """
        Create an order from the session cart and orchestrate payment.
        Demonstrates downstream service dependency: Order -> Payment -> Database.
        """
        from backend.sentinel.simulation_engine import simulation_engine
        
        # Check active chaos faults on Order Service
        await simulation_engine.check_and_apply_fault(self.service_name)

        # 1. Fetch Cart Items
        cart = await cart_service.get_cart(session_id)
        if not cart["items"] or cart["total_amount"] <= 0:
            raise ValueError("Cannot checkout: Cart is empty.")

        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        total_amount = cart["total_amount"]
        items_json = json.dumps(cart["items"])

        # 2. Insert Pending Order into SQLite
        order_id = None
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (order_number, session_id, customer_name, customer_email, total_amount, currency, status, items_json)
                VALUES (?, ?, ?, ?, ?, 'USD', 'PENDING_PAYMENT', ?);
            """, (order_number, session_id, customer_name, customer_email, total_amount, items_json))
            order_id = cursor.lastrowid

        append_structured_log(
            service=self.service_name,
            level="INFO",
            message=f"Order {order_number} initiated. Calling downstream Payment Service for ${total_amount:.2f}",
            metadata={"order_number": order_number, "order_id": order_id, "amount": total_amount}
        )

        # 3. Call Downstream Payment Service
        payment_result = None
        try:
            payment_result = await payment_service.process_payment(
                order_id=order_id,
                amount=total_amount,
                card_number=card_number
            )
        except PaymentGatewayError as pe:
            payment_service.record_failure(order_id, total_amount, str(pe), card_number)
            with db_session() as conn:
                conn.execute("UPDATE orders SET status = 'PAYMENT_FAILED' WHERE id = ?;", (order_id,))
            append_structured_log(
                service=self.service_name,
                level="ERROR",
                message=f"Order {order_number} failed: Downstream payment error: {str(pe)}",
                metadata={"order_number": order_number, "error": str(pe)}
            )
            raise RuntimeError(f"Order processing failed: Downstream Payment Service reported {str(pe)}")
        except Exception as e:
            payment_service.record_failure(order_id, total_amount, str(e), card_number)
            with db_session() as conn:
                conn.execute("UPDATE orders SET status = 'PAYMENT_FAILED' WHERE id = ?;", (order_id,))
            append_structured_log(
                service=self.service_name,
                level="ERROR",
                message=f"Order {order_number} encountered unexpected payment failure: {str(e)}",
                metadata={"order_number": order_number, "error": str(e)}
            )
            raise RuntimeError(f"Payment communication error: {str(e)}")

        # 4. Mark Order Confirmed and Clear Cart
        with db_session() as conn:
            conn.execute("UPDATE orders SET status = 'CONFIRMED' WHERE id = ?;", (order_id,))

        await cart_service.clear_cart(session_id)

        append_structured_log(
            service=self.service_name,
            level="INFO",
            message=f"Order {order_number} successfully placed and confirmed.",
            metadata={"order_number": order_number, "payment_id": payment_result["payment_id"]}
        )

        return {
            "order_number": order_number,
            "order_id": order_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "total_amount": total_amount,
            "currency": "USD",
            "status": "CONFIRMED",
            "payment_id": payment_result["payment_id"],
            "items_count": len(cart["items"]),
            "items": cart["items"],
            "created_at": order_number
        }

    async def get_order_by_number(self, order_number: str) -> Optional[Dict[str, Any]]:
        """Retrieve confirmed order details by order number."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_number = ?;", (order_number,))
            row = cursor.fetchone()
            if not row:
                return None

            items = json.loads(row["items_json"]) if row["items_json"] else []
            return {
                "id": row["id"],
                "order_number": row["order_number"],
                "customer_name": row["customer_name"],
                "customer_email": row["customer_email"],
                "total_amount": row["total_amount"],
                "currency": row["currency"],
                "status": row["status"],
                "items": items,
                "created_at": row["created_at"]
            }

    def health_check(self) -> Dict[str, Any]:
        """Service health check."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders;")
            total_orders = cursor.fetchone()[0]
        return {
            "service": self.service_name,
            "status": "UP",
            "total_orders_processed": total_orders
        }

order_service = OrderService()

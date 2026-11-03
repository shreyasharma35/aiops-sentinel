"""
Unit & Integration Tests for E-Commerce Services
Verifies Product catalog, Cart operations, Downstream Payment, and Order lifecycle.
"""

import pytest
import asyncio
from backend.database import init_db
from backend.services.product_service import product_service
from backend.services.cart_service import cart_service
from backend.services.order_service import order_service
from backend.services.payment_service import payment_service

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database schema and seed catalog are initialized."""
    init_db()

def test_product_catalog_and_categories():
    """Verify catalog items are retrieved with prices, ratings, and categories."""
    async def _run():
        products = await product_service.get_all_products()
        assert len(products) > 0, "Product catalog must not be empty"
        
        first = products[0]
        assert "id" in first
        assert "title" in first
        assert "price" in first
        assert first["price"] > 0
        assert "category" in first

        categories = await product_service.get_categories()
        assert len(categories) > 0, "Categories must be extracted"
    
    asyncio.run(_run())

def test_cart_lifecycle():
    """Verify adding, updating quantity, and removing items in SQLite cart."""
    async def _run():
        test_session = "test-session-cart-123"
        
        # 1. Add item
        cart = await cart_service.add_item(test_session, product_id=1, quantity=2)
        assert cart["total_items"] >= 2
        assert cart["total_amount"] > 0

        # 2. Update quantity
        item_id = cart["items"][0]["id"]
        cart_updated = await cart_service.update_quantity(test_session, item_id, quantity=3)
        assert cart_updated["total_items"] >= 3

        # 3. Clear cart
        cleared = await cart_service.clear_cart(test_session)
        assert cleared["total_items"] == 0
        assert len(cleared["items"]) == 0
    
    asyncio.run(_run())

def test_order_creation_and_payment_flow():
    """Verify complete checkout pipeline: Cart -> Order -> Payment -> Confirmation."""
    async def _run():
        test_session = "test-session-checkout-456"
        
        # Add product
        await cart_service.add_item(test_session, product_id=2, quantity=1)

        # Place order
        order = await order_service.create_order(
            session_id=test_session,
            customer_name="Test Shopper",
            customer_email="test@sentinel.local",
            card_number="4242424242424242"
        )

        assert order["status"] == "CONFIRMED"
        assert order["order_number"].startswith("ORD-")
        assert order["payment_id"].startswith("PAY-")
        assert order["total_amount"] > 0

        # Cart should be cleared after confirmed order
        cart_after = await cart_service.get_cart(test_session)
        assert cart_after["total_items"] == 0

    asyncio.run(_run())

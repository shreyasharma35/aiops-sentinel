"""
E-Commerce API Router
Handles customer-facing shopping endpoints: Catalog, Cart, Checkout, Orders, and Auth.
"""

from fastapi import APIRouter, HTTPException, Query, Header
from typing import Optional, List, Dict, Any
from backend.models import (
    Product, CartItemAdd, CartSummary, OrderCreate, OrderResponse
)
from backend.services.product_service import product_service
from backend.services.cart_service import cart_service
from backend.services.order_service import order_service
from backend.services.payment_service import payment_service
from backend.services.auth_service import auth_service
from backend.services.database_service import database_service

router = APIRouter(prefix="/api/ecommerce", tags=["E-Commerce Storefront"])

# --- CATALOG & PRODUCTS ---

@router.get("/products", response_model=List[Product])
async def list_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search keyword in title or description")
):
    """Retrieve catalog items with category and search filtering."""
    try:
        products = await product_service.get_all_products(category=category, search=search)
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products/{product_id}")
async def get_product(product_id: int):
    """Fetch product by ID."""
    prod = await product_service.get_product_by_id(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod

@router.get("/categories", response_model=List[str])
async def get_categories():
    """List all product categories."""
    return await product_service.get_categories()

# --- SHOPPING CART ---

@router.get("/cart")
async def get_cart(x_session_id: str = Header("demo-session-1")):
    """Get active cart contents for current session."""
    return await cart_service.get_cart(x_session_id)

@router.post("/cart/add")
async def add_to_cart(item: CartItemAdd, x_session_id: str = Header("demo-session-1")):
    """Add item to shopping cart."""
    try:
        return await cart_service.add_item(x_session_id, item.product_id, item.quantity)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cart/update")
async def update_cart_quantity(
    item_id: int = Query(...),
    quantity: int = Query(...),
    x_session_id: str = Header("demo-session-1")
):
    """Update line item quantity."""
    return await cart_service.update_quantity(x_session_id, item_id, quantity)

@router.delete("/cart/{item_id}")
async def remove_cart_item(item_id: int, x_session_id: str = Header("demo-session-1")):
    """Remove line item from cart."""
    return await cart_service.remove_item(x_session_id, item_id)

@router.post("/cart/clear")
async def clear_cart(x_session_id: str = Header("demo-session-1")):
    """Clear all items in cart."""
    return await cart_service.clear_cart(x_session_id)

# --- ORDERS & CHECKOUT ---

@router.post("/orders/checkout")
async def checkout_order(order_data: OrderCreate, x_session_id: str = Header("demo-session-1")):
    """
    Submit cart for checkout.
    Orchestrates order creation and calls Payment Service.
    """
    try:
        result = await order_service.create_order(
            session_id=x_session_id,
            customer_name=order_data.customer_name,
            customer_email=order_data.customer_email,
            card_number=order_data.card_number
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checkout execution failed: {str(e)}")

@router.get("/orders/{order_number}")
async def get_order_details(order_number: str):
    """Retrieve details for a placed order."""
    order = await order_service.get_order_by_number(order_number)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# --- AUTH & USER ---

@router.get("/auth/me")
async def get_current_user(username: str = Query("demo_shopper")):
    """Fetch current user session info."""
    user = await auth_service.get_user_profile(username)
    if not user:
        user = await auth_service.authenticate_user(username)
    return user

@router.post("/auth/login")
async def login(username: str = Query(...)):
    """Authenticate or create user profile."""
    return await auth_service.authenticate_user(username)

# --- INDIVIDUAL SERVICE HEALTH ENDPOINTS ---

@router.get("/products/health")
async def product_service_health():
    return product_service.health_check()

@router.get("/cart/health")
async def cart_service_health():
    return cart_service.health_check()

@router.get("/orders/health")
async def order_service_health():
    return order_service.health_check()

@router.get("/payment/health")
async def payment_service_health():
    return payment_service.health_check()

@router.get("/auth/health")
async def auth_service_health():
    return auth_service.health_check()

@router.get("/database/health")
async def database_service_health():
    return database_service.health_check()

@router.get("/database/ping")
async def database_ping():
    return await database_service.execute_ping()

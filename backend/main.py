"""
AIOps Sentinel - Unified Application Main Entrypoint
Hosts the E-Commerce Demonstration Storefront and the AIOps SRE Observability Platform
under ONE integrated, cohesive FastAPI architecture.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import config
from backend.database import init_db
from backend.telemetry import TelemetryMiddleware
from backend.sentinel.collector import telemetry_collector
from backend.routers.ecommerce_router import router as ecommerce_router
from backend.routers.sentinel_router import router as sentinel_router
from backend.routers.simulation_router import router as simulation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: initialize database and start telemetry collector."""
    print("[*] Initializing AIOps Sentinel Unified Platform...")
    init_db()
    print("[+] SQLite database initialized & seed catalog verified.")
    await telemetry_collector.start()
    print("[+] Background Telemetry Collector & Shopper Traffic Daemon started.")
    yield
    print("[*] Shutting down Telemetry Collector...")
    await telemetry_collector.stop()
    print("[*] Shutdown complete.")

app = FastAPI(
    title="AIOps Sentinel & E-Commerce Platform",
    description="Explainable, Adaptive, Deployment-Aware Incident Detection & Autonomous SRE Recovery",
    version="1.0.0",
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telemetry Interceptor Middleware (measures request latency, error codes, host resources)
app.add_middleware(TelemetryMiddleware)

# Mount Static Assets & Templates
config.STATIC_DIR.mkdir(parents=True, exist_ok=True)
config.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

# Register API Routers
app.include_router(ecommerce_router)
app.include_router(sentinel_router)
app.include_router(simulation_router)

# --- WEB PAGE ROUTES ---

@app.get("/", response_class=HTMLResponse)
@app.get("/store", response_class=HTMLResponse)
async def serve_storefront():
    """Customer-facing E-Commerce demonstration storefront."""
    store_html = config.TEMPLATES_DIR / "ecommerce.html"
    if store_html.exists():
        return HTMLResponse(content=store_html.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>E-Commerce Storefront template loading...</h1>")

@app.get("/sentinel", response_class=HTMLResponse)
async def serve_sentinel_dashboard():
    """AIOps Sentinel SRE Observability & Autonomous Recovery Control Center."""
    sentinel_html = config.TEMPLATES_DIR / "sentinel.html"
    if sentinel_html.exists():
        return HTMLResponse(content=sentinel_html.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>AIOps Sentinel SRE Dashboard template loading...</h1>")

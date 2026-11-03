"""
AIOps Sentinel - Configuration Manager
Central configuration for Services, Thresholds, Telemetry, and Recovery allowlist.
"""

import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "sentinel.db"

class ServiceSLO(BaseModel):
    service_name: str
    target_p95_latency_ms: float
    max_error_rate_pct: float
    min_availability_pct: float
    static_latency_warning_ms: float
    static_latency_critical_ms: float

class AppConfig:
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    DB_PATH: Path = DB_PATH
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    STATIC_DIR: Path = BASE_DIR / "static"

    # External APIs
    FAKESTORE_API_URL: str = os.getenv("FAKESTORE_API_URL", "https://fakestoreapi.com")
    FAKESTORE_TIMEOUT_SECONDS: float = 6.0
    CATALOG_CACHE_TTL_SECONDS: int = 3600

    # Telemetry & Monitoring
    TELEMETRY_INTERVAL_SECONDS: float = float(os.getenv("TELEMETRY_INTERVAL_SECONDS", "2.0"))
    METRIC_RETENTION_MAX_DATAPOINTS: int = 200
    ADAPTIVE_WINDOW_SIZE: int = int(os.getenv("ADAPTIVE_WINDOW_SIZE", "30"))
    ADAPTIVE_MAD_MULTIPLIER: float = float(os.getenv("ADAPTIVE_MAD_MULTIPLIER", "3.0"))
    MIN_OBSERVATIONS_FOR_ADAPTIVE: int = int(os.getenv("MIN_OBSERVATIONS_FOR_ADAPTIVE", "8"))
    HYSTERESIS_COOLDOWN_TICKS: int = 3
    PERSISTENCE_TICKS: int = 2

    # Anomaly Detection (ML)
    ISOLATION_FOREST_CONTAMINATION: float = float(os.getenv("ISOLATION_FOREST_CONTAMINATION", "0.05"))
    MIN_TRAINING_SAMPLES: int = 20

    # Local LLM (Ollama)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_TIMEOUT_SECONDS: float = 12.0

    # Admin Auth
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "sentinel-sre-secure")

    # Registered Monitored Services
    SERVICES: list[str] = [
        "product-service",
        "cart-service",
        "order-service",
        "payment-service",
        "auth-service",
        "database-service"
    ]

    # Predefined Allowlisted Recovery Actions (strictly enforced for security)
    ALLOWLISTED_RECOVERY_ACTIONS: dict[str, str] = {
        "RESTART_PAYMENT_CIRCUIT_BREAKER": "Resets the payment gateway circuit breaker, clears connection pool, and cancels simulated latency/error injection.",
        "RESTART_SERVICE": "Gracefully restarts the target microservice internal state and flushes active request queues.",
        "FLUSH_PRODUCT_CACHE": "Clears corrupted or stale in-memory product cache and re-hydrates from verified catalogue storage.",
        "RESET_DATABASE_CONNECTIONS": "Re-initializes the SQLite connection pool, resolves table lock contention, and clears hung transactions.",
        "SCALE_WORKERS": "Increases simulated concurrency capacity and flushes overloaded background queues.",
        "CLEAR_CHAOS_SIMULATION": "Immediately aborts all active chaos simulations across all services and returns platform to normal baseline."
    }

    # Service-specific SLO targets and static guardrail thresholds
    SERVICE_SLOS: dict[str, ServiceSLO] = {
        "product-service": ServiceSLO(
            service_name="product-service",
            target_p95_latency_ms=300.0,
            max_error_rate_pct=2.0,
            min_availability_pct=99.5,
            static_latency_warning_ms=500.0,
            static_latency_critical_ms=1200.0
        ),
        "cart-service": ServiceSLO(
            service_name="cart-service",
            target_p95_latency_ms=200.0,
            max_error_rate_pct=1.0,
            min_availability_pct=99.9,
            static_latency_warning_ms=400.0,
            static_latency_critical_ms=900.0
        ),
        "order-service": ServiceSLO(
            service_name="order-service",
            target_p95_latency_ms=450.0,
            max_error_rate_pct=2.0,
            min_availability_pct=99.0,
            static_latency_warning_ms=700.0,
            static_latency_critical_ms=1800.0
        ),
        "payment-service": ServiceSLO(
            service_name="payment-service",
            target_p95_latency_ms=400.0,
            max_error_rate_pct=1.5,
            min_availability_pct=99.9,
            static_latency_warning_ms=650.0,
            static_latency_critical_ms=2000.0
        ),
        "auth-service": ServiceSLO(
            service_name="auth-service",
            target_p95_latency_ms=150.0,
            max_error_rate_pct=1.0,
            min_availability_pct=99.9,
            static_latency_warning_ms=300.0,
            static_latency_critical_ms=800.0
        ),
        "database-service": ServiceSLO(
            service_name="database-service",
            target_p95_latency_ms=100.0,
            max_error_rate_pct=0.5,
            min_availability_pct=99.95,
            static_latency_warning_ms=250.0,
            static_latency_critical_ms=600.0
        )
    }

config = AppConfig()

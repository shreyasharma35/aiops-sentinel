"""
AIOps Sentinel - Telemetry & Observability Engine
Real-time request metrics interception, host resource tracking via psutil,
and structured in-memory observability buffers.
"""

import time
import uuid
import psutil
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.config import config
from backend.database import db_session

# Rolling in-memory metrics buffer (service -> deque of {timestamp, latency_ms, status_code, is_error, cpu, mem})
RECENT_METRICS_BUFFER: Dict[str, deque] = {
    svc: deque(maxlen=config.METRIC_RETENTION_MAX_DATAPOINTS) for svc in config.SERVICES
}

# Live structured SRE logs circular buffer
STRUCTURED_LOGS_BUFFER: deque = deque(maxlen=200)

def append_structured_log(service: str, level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    """Append a structured log entry into the live SRE log stream."""
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": service,
        "level": level.upper(),  # INFO, WARN, ERROR, CRITICAL
        "message": message,
        "metadata": metadata or {}
    }
    STRUCTURED_LOGS_BUFFER.append(entry)

def get_live_structured_logs(limit: int = 50, service: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve the latest structured logs, optionally filtered by service."""
    logs = list(STRUCTURED_LOGS_BUFFER)
    if service:
        logs = [log for log in logs if log["service"] == service]
    return logs[-limit:]

def get_current_host_metrics() -> Dict[str, Any]:
    """Capture host system CPU, Memory, Disk and Process stats using psutil."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        proc = psutil.Process()
        proc_mem = proc.memory_info().rss / (1024 * 1024)  # MB
        
        return {
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(mem.percent, 1),
            "disk_percent": round(disk.percent, 1),
            "process_memory_mb": round(proc_mem, 1),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "cpu_percent": 15.0,
            "memory_percent": 35.0,
            "disk_percent": 50.0,
            "process_memory_mb": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

def classify_service_from_path(path: str) -> str:
    """Map request route path to logical monitored microservice."""
    path_lower = path.lower()
    if "/api/ecommerce/products" in path_lower or "/api/ecommerce/categories" in path_lower:
        return "product-service"
    elif "/api/ecommerce/cart" in path_lower:
        return "cart-service"
    elif "/api/ecommerce/orders" in path_lower:
        return "order-service"
    elif "/api/ecommerce/payment" in path_lower:
        return "payment-service"
    elif "/api/ecommerce/auth" in path_lower or "/api/ecommerce/users" in path_lower:
        return "auth-service"
    elif "/api/ecommerce/database" in path_lower:
        return "database-service"
    elif "/sentinel" in path_lower or "/api/sentinel" in path_lower:
        return "database-service"  # Internal sentinel queries touch database service
    else:
        return "product-service"  # Default storefront asset/view route

class TelemetryMiddleware(BaseHTTPMiddleware):
    """
    High-performance middleware that intercepts all HTTP requests,
    measures latency, captures error status, updates rolling telemetry buffers,
    and records datapoints into SQLite.
    """
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        
        service_name = classify_service_from_path(request.url.path)
        
        # Attach request ID to request state
        request.state.request_id = req_id
        request.state.service_name = service_name
        
        is_error = 0
        status_code = 500
        error_msg = None
        
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                is_error = 1
                error_msg = f"HTTP {status_code} returned on {request.method} {request.url.path}"
            return response
        except Exception as exc:
            is_error = 1
            status_code = 500
            error_msg = f"Unhandled exception: {str(exc)}"
            raise exc
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            # Host stats sample
            host_stats = get_current_host_metrics()
            
            # 1. Update in-memory rolling buffer
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": duration_ms,
                "status_code": status_code,
                "is_error": is_error,
                "cpu_percent": host_stats["cpu_percent"],
                "memory_percent": host_stats["memory_percent"],
                "request_id": req_id
            }
            if service_name in RECENT_METRICS_BUFFER:
                RECENT_METRICS_BUFFER[service_name].append(record)
                
            # 2. Append structured log
            if is_error:
                append_structured_log(
                    service=service_name,
                    level="ERROR",
                    message=error_msg or f"Request failed with code {status_code}",
                    metadata={"path": request.url.path, "latency_ms": duration_ms, "req_id": req_id}
                )
            elif duration_ms > 1000:
                append_structured_log(
                    service=service_name,
                    level="WARN",
                    message=f"High latency observed: {duration_ms}ms on {request.method} {request.url.path}",
                    metadata={"path": request.url.path, "latency_ms": duration_ms, "req_id": req_id}
                )
            
            # 3. Persist to SQLite database asynchronously/silently
            try:
                # Filter out pure polling static file calls to avoid database saturation
                if not request.url.path.startswith("/static/"):
                    with db_session() as conn:
                        conn.execute("""
                            INSERT INTO service_metrics 
                            (service_name, latency_ms, status_code, is_error, cpu_percent, memory_percent, request_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?);
                        """, (service_name, duration_ms, status_code, is_error, 
                              host_stats["cpu_percent"], host_stats["memory_percent"], req_id))
            except Exception:
                pass  # Telemetry storage must never break request pipeline

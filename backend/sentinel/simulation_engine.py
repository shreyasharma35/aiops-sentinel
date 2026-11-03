"""
AIOps Sentinel - Failure Simulation & Chaos Lab Engine
Controlled, safe fault injection across e-commerce services to simulate
real-world operational incidents for telemetry, detection, RCA, and recovery.
"""

import time
import asyncio
import threading
from typing import Dict, Any, Optional
from backend.telemetry import append_structured_log

class SimulationEngine:
    def __init__(self):
        # Active scenario states: scenario_name -> dict(enabled=bool, params=dict, start_time=float)
        self.active_scenarios: Dict[str, Dict[str, Any]] = {}
        self._cpu_thread: Optional[threading.Thread] = None
        self._cpu_running = False
        self._memory_hog: Optional[bytearray] = None
        self._traffic_spike_task: Optional[asyncio.Task] = None
        self._traffic_spike_running = False

    def start_scenario(self, scenario: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start or enable a chaos scenario."""
        params = params or {}
        self.active_scenarios[scenario] = {
            "enabled": True,
            "params": params,
            "started_at": time.time(),
            "target_service": params.get("target_service", self._default_service_for_scenario(scenario))
        }

        # Handle system-level simulations
        if scenario == "high_cpu":
            self._start_high_cpu()
        elif scenario == "memory_leak":
            self._start_memory_leak()
        elif scenario == "traffic_spike":
            self._start_traffic_spike()

        target_svc = self.active_scenarios[scenario]["target_service"]
        append_structured_log(
            service=target_svc,
            level="WARN",
            message=f"Chaos Failure Simulation ACTIVATED: [{scenario}] target={target_svc}",
            metadata={"scenario": scenario, "params": params}
        )

        return {
            "scenario": scenario,
            "status": "RUNNING",
            "target_service": target_svc,
            "message": f"Scenario '{scenario}' active on '{target_svc}'"
        }

    def stop_scenario(self, scenario: str) -> Dict[str, Any]:
        """Stop a specific chaos scenario."""
        if scenario in self.active_scenarios:
            target_svc = self.active_scenarios[scenario].get("target_service", "all")
            del self.active_scenarios[scenario]

            if scenario == "high_cpu":
                self._stop_high_cpu()
            elif scenario == "memory_leak":
                self._stop_memory_leak()
            elif scenario == "traffic_spike":
                self._stop_traffic_spike()

            append_structured_log(
                service=target_svc,
                level="INFO",
                message=f"Chaos Failure Simulation DEACTIVATED: [{scenario}]",
                metadata={"scenario": scenario}
            )
            return {"scenario": scenario, "status": "STOPPED", "message": f"Scenario '{scenario}' halted."}

        return {"scenario": scenario, "status": "NOT_ACTIVE", "message": "Scenario was not running."}

    def stop_all(self):
        """Immediately cancel all active chaos simulations."""
        scenarios = list(self.active_scenarios.keys())
        for sc in scenarios:
            self.stop_scenario(sc)
        self._stop_high_cpu()
        self._stop_memory_leak()
        self._stop_traffic_spike()

    def get_state(self) -> Dict[str, Any]:
        """Return all active chaos simulations with runtime durations."""
        now = time.time()
        details = {}
        for sc, data in self.active_scenarios.items():
            details[sc] = {
                "target_service": data.get("target_service"),
                "params": data.get("params"),
                "elapsed_seconds": round(now - data.get("started_at", now), 1)
            }
        return {
            "active_scenarios": details,
            "total_active": len(details),
            "cpu_burn_active": self._cpu_running,
            "memory_leak_active": self._memory_hog is not None
        }

    async def check_and_apply_fault(self, service_name: str):
        """
        Called transparently inside service business logic.
        Injects real latency or raises real HTTP/service exceptions if a scenario is active.
        """
        # 1. Payment Latency injection
        if "payment_latency" in self.active_scenarios and service_name == "payment-service":
            delay = self.active_scenarios["payment_latency"]["params"].get("delay_ms", 3200) / 1000.0
            append_structured_log(
                service=service_name,
                level="WARN",
                message=f"Simulating high network latency: sleeping for {delay:.2f}s"
            )
            await asyncio.sleep(delay)

        # 2. Payment Failure injection
        if "payment_failure" in self.active_scenarios and service_name == "payment-service":
            append_structured_log(
                service=service_name,
                level="ERROR",
                message="Simulating upstream payment gateway failure: HTTP 504 Gateway Timeout"
            )
            raise RuntimeError("Upstream Payment Gateway Timeout: Bank API did not respond within 5000ms")

        # 3. Order 500 Surge
        if "order_500_surge" in self.active_scenarios and service_name == "order-service":
            append_structured_log(
                service=service_name,
                level="ERROR",
                message="Simulating Order Service Internal Failure: HTTP 500"
            )
            raise RuntimeError("Internal Order Pipeline Exception: Order dispatch queue locked (HTTP 500)")

        # 4. Product Service Slowdown
        if "product_latency" in self.active_scenarios and service_name == "product-service":
            delay = self.active_scenarios["product_latency"]["params"].get("delay_ms", 2500) / 1000.0
            await asyncio.sleep(delay)

        # 5. Database Connection Lock
        if "db_lock" in self.active_scenarios and service_name in ("database-service", "order-service", "cart-service"):
            append_structured_log(
                service="database-service",
                level="ERROR",
                message="Simulating SQLite Database Table Lock / Connection Pool Starvation"
            )
            await asyncio.sleep(1.5)
            raise RuntimeError("OperationalError: database is locked - SQLite connection pool exhausted")

    def _default_service_for_scenario(self, scenario: str) -> str:
        mapping = {
            "payment_latency": "payment-service",
            "payment_failure": "payment-service",
            "order_500_surge": "order-service",
            "product_latency": "product-service",
            "db_lock": "database-service",
            "high_cpu": "host-system",
            "memory_leak": "host-system",
            "traffic_spike": "cart-service"
        }
        return mapping.get(scenario, "product-service")

    def _start_high_cpu(self):
        """Spins a controlled worker thread burning CPU within safe throttled cycles."""
        if self._cpu_running:
            return
        self._cpu_running = True

        def _burn():
            while self._cpu_running:
                # Controlled burn cycle: 80ms active math, 20ms sleep to prevent freeze
                start = time.perf_counter()
                while (time.perf_counter() - start) < 0.08:
                    _ = [x ** 2 for x in range(3000)]
                time.sleep(0.02)

        self._cpu_thread = threading.Thread(target=_burn, daemon=True)
        self._cpu_thread.start()

    def _stop_high_cpu(self):
        self._cpu_running = False
        self._cpu_thread = None

    def _start_memory_leak(self):
        """Allocates a safe 200MB memory chunk to visibly raise memory percent."""
        if self._memory_hog is None:
            try:
                # 200 MB allocation
                self._memory_hog = bytearray(200 * 1024 * 1024)
            except Exception:
                pass

    def _stop_memory_leak(self):
        """Reclaims the memory buffer."""
        self._memory_hog = None

    def _start_traffic_spike(self):
        """Spawns an asynchronous burst loop generating high concurrency request volume."""
        if self._traffic_spike_running:
            return
        self._traffic_spike_running = True

        async def _burst():
            from backend.services.product_service import product_service
            from backend.services.cart_service import cart_service
            burst_session = "chaos-traffic-spike-session"

            while self._traffic_spike_running:
                tasks = []
                for _ in range(8):
                    tasks.append(product_service.get_all_products())
                    tasks.append(cart_service.get_cart(burst_session))
                    tasks.append(cart_service.add_item(burst_session, product_id=1, quantity=1))
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception:
                    pass
                await asyncio.sleep(0.4)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._traffic_spike_task = loop.create_task(_burst())
        except Exception:
            pass

    def _stop_traffic_spike(self):
        """Halts the high-concurrency traffic burst."""
        self._traffic_spike_running = False
        if self._traffic_spike_task and not self._traffic_spike_task.done():
            self._traffic_spike_task.cancel()
            self._traffic_spike_task = None

simulation_engine = SimulationEngine()

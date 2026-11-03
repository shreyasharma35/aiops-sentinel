"""
Payment Service Module
Simulated payment gateway processing with card authorization,
circuit breaker state, transaction audit logging, and chaos injection points.
"""

import time
import asyncio
import uuid
import random
from typing import Dict, Any, Optional
from backend.database import db_session
from backend.telemetry import append_structured_log

class PaymentGatewayError(Exception):
    """Raised when payment gateway encounters timeout or processing failure."""
    pass

class PaymentService:
    def __init__(self):
        self.service_name = "payment-service"
        self.circuit_breaker_open = False
        self.consecutive_failures = 0
        self.circuit_breaker_threshold = 4

    def reset_circuit_breaker(self):
        """Allowlisted recovery action: reset circuit breaker state."""
        self.circuit_breaker_open = False
        self.consecutive_failures = 0
        append_structured_log(
            service=self.service_name,
            level="INFO",
            message="Payment Service Circuit Breaker manually reset by SRE Recovery Action."
        )

    async def process_payment(self, order_id: int, amount: float, card_number: str) -> Dict[str, Any]:
        """
        Process a simulated payment transaction.
        Measures exact gateway latency and records payment in database.
        """
        from backend.sentinel.simulation_engine import simulation_engine
        
        # Check circuit breaker
        if self.circuit_breaker_open:
            append_structured_log(
                service=self.service_name,
                level="ERROR",
                message="Payment rejected immediately: Circuit breaker is OPEN."
            )
            raise PaymentGatewayError("Payment Gateway Circuit Breaker is OPEN. Downstream payment processing is halted.")

        start_time = time.perf_counter()
        
        # Check active chaos simulation (latency or failure)
        await simulation_engine.check_and_apply_fault(self.service_name)

        # Baseline normal gateway simulation (150ms - 280ms)
        await asyncio.sleep(random.uniform(0.12, 0.25))

        clean_card = "".join(filter(str.isdigit, card_number))
        card_last4 = clean_card[-4:] if len(clean_card) >= 4 else "4242"
        payment_id = f"PAY-{uuid.uuid4().hex[:10].upper()}"

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Record payment transaction in DB
        with db_session() as conn:
            conn.execute("""
                INSERT INTO payments 
                (payment_id, order_id, amount, status, card_last4, response_time_ms, gateway_code, error_message)
                VALUES (?, ?, ?, 'COMPLETED', ?, ?, 'AUTH_APPROVED', NULL);
            """, (payment_id, order_id, amount, card_last4, duration_ms))

        self.consecutive_failures = 0

        append_structured_log(
            service=self.service_name,
            level="INFO",
            message=f"Payment {payment_id} approved for Order #{order_id} (${amount:.2f}) in {duration_ms}ms",
            metadata={"payment_id": payment_id, "duration_ms": duration_ms, "card_last4": card_last4}
        )

        return {
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": amount,
            "status": "COMPLETED",
            "card_last4": card_last4,
            "response_time_ms": duration_ms,
            "gateway_message": "Authorized and settled successfully."
        }

    def record_failure(self, order_id: int, amount: float, error_msg: str, card_number: str = "4242"):
        """Record a failed payment attempt and update circuit breaker."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            append_structured_log(
                service=self.service_name,
                level="CRITICAL",
                message=f"Payment circuit breaker TRIPPED after {self.consecutive_failures} consecutive failures."
            )

        clean_card = "".join(filter(str.isdigit, card_number))
        card_last4 = clean_card[-4:] if len(clean_card) >= 4 else "4242"
        payment_id = f"PAY-FAIL-{uuid.uuid4().hex[:8].upper()}"

        try:
            with db_session() as conn:
                conn.execute("""
                    INSERT INTO payments 
                    (payment_id, order_id, amount, status, card_last4, response_time_ms, gateway_code, error_message)
                    VALUES (?, ?, ?, 'FAILED', ?, 3200.0, 'GATEWAY_TIMEOUT', ?);
                """, (payment_id, order_id, amount, card_last4, error_msg))
        except Exception:
            pass

    def health_check(self) -> Dict[str, Any]:
        """Service health check."""
        status = "CRITICAL" if self.circuit_breaker_open else ("WARNING" if self.consecutive_failures > 0 else "UP")
        return {
            "service": self.service_name,
            "status": status,
            "circuit_breaker_open": self.circuit_breaker_open,
            "consecutive_failures": self.consecutive_failures
        }

payment_service = PaymentService()

"""
AIOps Sentinel - Adaptive Threshold Engine
Robust statistical anomaly detection using Rolling Median,
Median Absolute Deviation (MAD), Guardrail Floor/Ceiling, and Hysteresis.
"""

import numpy as np
from typing import Dict, List, Any, Tuple
from backend.config import config
from backend.database import db_session

class AdaptiveThresholdEngine:
    def __init__(self):
        # Persistence counter: service_name -> count of consecutive violations
        self.persistence_counters: Dict[str, int] = {svc: 0 for svc in config.SERVICES}
        # Cooldown counter: service_name -> count of clean samples during recovery
        self.cooldown_counters: Dict[str, int] = {svc: 0 for svc in config.SERVICES}

    def calculate_mad_thresholds(
        self,
        values: List[float],
        static_warning: float,
        static_critical: float,
        multiplier: float = 3.0
    ) -> Dict[str, float]:
        """
        Calculate adaptive thresholds using Rolling Median and Median Absolute Deviation (MAD).
        Returns dict with:
        - median
        - mad
        - dynamic_warning
        - dynamic_critical
        - is_adaptive_active (True if sufficient samples)
        """
        if len(values) < config.MIN_OBSERVATIONS_FOR_ADAPTIVE:
            return {
                "median": round(float(np.median(values)), 2) if values else static_warning * 0.5,
                "mad": 0.0,
                "warning_threshold": static_warning,
                "critical_threshold": static_critical,
                "is_adaptive_active": False,
                "sample_count": len(values),
                "reason": f"Insufficient baseline observations ({len(values)}/{config.MIN_OBSERVATIONS_FOR_ADAPTIVE}). Using static safety thresholds."
            }

        arr = np.array(values, dtype=np.float64)
        med = float(np.median(arr))
        abs_deviations = np.abs(arr - med)
        raw_mad = float(np.median(abs_deviations))
        
        # Scale factor for normal distribution consistency (1.4826)
        mad_scaled = 1.4826 * raw_mad

        # Zero-variation guardrail: prevent collapse if metrics are identical
        if mad_scaled < 0.05 * med:
            mad_scaled = max(0.15 * med, 15.0)

        dyn_warning = med + (multiplier * 0.75) * mad_scaled
        dyn_critical = med + multiplier * mad_scaled

        # Guardrails: Never allow dynamic threshold to drop below minimum safety floor
        warning_thresh = max(dyn_warning, static_warning * 0.7)
        critical_thresh = max(dyn_critical, static_critical * 0.7)

        return {
            "median": round(med, 2),
            "mad": round(mad_scaled, 2),
            "warning_threshold": round(warning_thresh, 2),
            "critical_threshold": round(critical_thresh, 2),
            "is_adaptive_active": True,
            "sample_count": len(values),
            "reason": f"Adaptive MAD active on {len(values)} baseline observations (k={multiplier})."
        }

    def evaluate_metric(
        self,
        service_name: str,
        current_value: float,
        historical_clean_values: List[float]
    ) -> Dict[str, Any]:
        """
        Evaluate an observed service metric against hybrid thresholds.
        Applies persistence check (must exceed threshold for N ticks)
        and hysteresis (must remain normal for M ticks to clear).
        """
        slo = config.SERVICE_SLOS.get(service_name)
        static_warn = slo.static_latency_warning_ms if slo else 500.0
        static_crit = slo.static_latency_critical_ms if slo else 1200.0

        stats = self.calculate_mad_thresholds(
            values=historical_clean_values,
            static_warning=static_warn,
            static_critical=static_crit,
            multiplier=config.ADAPTIVE_MAD_MULTIPLIER
        )

        warn_th = stats["warning_threshold"]
        crit_th = stats["critical_threshold"]

        # Raw alert evaluation
        is_critical = current_value >= crit_th
        is_warning = current_value >= warn_th and not is_critical
        is_clean = current_value < warn_th

        # Update persistence counter
        if is_critical or is_warning:
            self.persistence_counters[service_name] = self.persistence_counters.get(service_name, 0) + 1
            self.cooldown_counters[service_name] = 0
        else:
            self.cooldown_counters[service_name] = self.cooldown_counters.get(service_name, 0) + 1
            if self.cooldown_counters[service_name] >= config.HYSTERESIS_COOLDOWN_TICKS:
                self.persistence_counters[service_name] = 0

        # Persistent status
        persistent_count = self.persistence_counters[service_name]
        is_persistent_violation = persistent_count >= config.PERSISTENCE_TICKS

        # Determine health level
        if is_critical and is_persistent_violation:
            severity = "CRITICAL"
        elif is_warning and is_persistent_violation:
            severity = "WARNING"
        elif persistent_count > 0:
            severity = "TRANSIENT_WARNING"
        else:
            severity = "HEALTHY"

        return {
            "service_name": service_name,
            "current_value": round(current_value, 2),
            "severity": severity,
            "thresholds": stats,
            "persistence_ticks": persistent_count,
            "is_persistent": is_persistent_violation,
            "deviation_factor": round((current_value - stats["median"]) / max(stats["mad"], 1.0), 2) if stats["mad"] > 0 else 1.0
        }

adaptive_engine = AdaptiveThresholdEngine()

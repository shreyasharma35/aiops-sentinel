"""
AIOps Sentinel - Machine Learning Anomaly Detector
Scikit-Learn Isolation Forest implementation for multivariate anomaly detection
across CPU, Memory, Latency, Traffic, and Error Rates.
"""

import numpy as np
from typing import Dict, List, Any, Optional
from sklearn.ensemble import IsolationForest
from backend.config import config
from backend.telemetry import append_structured_log

class MLAnomalyDetector:
    def __init__(self):
        self.models: Dict[str, IsolationForest] = {}
        self.is_trained: Dict[str, bool] = {svc: False for svc in config.SERVICES}
        self.feature_names = ["cpu_percent", "memory_percent", "latency_ms", "request_count", "error_rate"]

    def train_model_for_service(self, service_name: str, observations: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Train or update the Isolation Forest model for a specific service
        using collected normal baseline observations.
        """
        if len(observations) < config.MIN_TRAINING_SAMPLES:
            return {
                "trained": False,
                "samples": len(observations),
                "message": f"Insufficient training data ({len(observations)}/{config.MIN_TRAINING_SAMPLES}). Awaiting baseline warm-up."
            }

        X = []
        for obs in observations:
            row = [
                float(obs.get("cpu_percent", 15.0)),
                float(obs.get("memory_percent", 35.0)),
                float(obs.get("latency_ms", 180.0)),
                float(obs.get("request_count", 10.0)),
                float(obs.get("error_rate", 0.0))
            ]
            X.append(row)

        X_train = np.array(X, dtype=np.float64)
        
        # Guardrail against zero-variance constant data (adds slight micro-jitter if variance is 0)
        stds = np.std(X_train, axis=0)
        if np.any(stds < 1e-3):
            jitter = np.random.normal(0, 0.05, X_train.shape)
            X_train = X_train + jitter

        model = IsolationForest(
            n_estimators=100,
            contamination=config.ISOLATION_FOREST_CONTAMINATION,
            random_state=42
        )
        model.fit(X_train)

        self.models[service_name] = model
        self.is_trained[service_name] = True

        append_structured_log(
            service=service_name,
            level="INFO",
            message=f"Isolation Forest model trained on {len(observations)} clean baseline observations."
        )

        return {
            "trained": True,
            "samples": len(observations),
            "message": f"Isolation Forest ready on {len(observations)} baseline samples."
        }

    def predict_anomaly(
        self,
        service_name: str,
        current_metrics: Dict[str, float],
        baseline_stats: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Evaluate current multivariate metrics using the trained Isolation Forest model.
        Returns anomaly status, anomaly score, and understandable feature explanation.
        """
        if not self.is_trained.get(service_name, False) or service_name not in self.models:
            # Fallback when ML model not yet trained
            return {
                "is_ml_anomaly": False,
                "anomaly_score": 0.0,
                "model_status": "AWAITING_TRAINING",
                "explanation": "Isolation Forest awaiting more baseline observations."
            }

        model = self.models[service_name]
        vec = np.array([[
            float(current_metrics.get("cpu_percent", 15.0)),
            float(current_metrics.get("memory_percent", 35.0)),
            float(current_metrics.get("latency_ms", 180.0)),
            float(current_metrics.get("request_count", 10.0)),
            float(current_metrics.get("error_rate", 0.0))
        ]], dtype=np.float64)

        # Scikit-learn IsolationForest: -1 for outlier/anomaly, 1 for normal
        prediction = model.predict(vec)[0]
        # decision_function: lower (negative) values indicate more anomalous
        raw_score = model.decision_function(vec)[0]
        # Normalize score into [0.0 - 1.0] where 1.0 is extreme anomaly
        anomaly_score = round(max(0.0, min(1.0, 0.5 - raw_score)), 3)

        is_anomaly = bool(prediction == -1 or raw_score < 0.0 or anomaly_score >= 0.55)

        # Generate explainable feature contribution
        explanation_parts = []
        if current_metrics.get("latency_ms", 0) > baseline_stats.get("median", 300) * 2.0:
            explanation_parts.append(f"Latency {current_metrics['latency_ms']:.1f}ms exceeds {baseline_stats.get('median', 300):.1f}ms baseline")
        if current_metrics.get("error_rate", 0) > 0.05:
            explanation_parts.append(f"Error rate elevated to {current_metrics['error_rate']*100:.1f}%")
        if current_metrics.get("cpu_percent", 0) > 75.0:
            explanation_parts.append(f"High CPU utilization {current_metrics['cpu_percent']:.1f}%")

        explanation = "; ".join(explanation_parts) if explanation_parts else "Unusual multivariate metric correlation detected by Isolation Forest."

        return {
            "is_ml_anomaly": is_anomaly,
            "anomaly_score": anomaly_score,
            "model_status": "ACTIVE",
            "explanation": explanation
        }

ml_detector = MLAnomalyDetector()

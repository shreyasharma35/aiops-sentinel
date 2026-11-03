"""
AIOps Sentinel - Data Contracts & Pydantic Models
Unified data schemas for E-Commerce entities, Telemetry, RCA, and Recovery workflows.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- E-COMMERCE MODELS ---

class ProductRating(BaseModel):
    rate: float = 4.5
    count: int = 100

class Product(BaseModel):
    id: int
    title: str
    price: float
    description: Optional[str] = ""
    category: str
    image: Optional[str] = ""
    rating: Optional[ProductRating] = Field(default_factory=ProductRating)

class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = 1

class CartItem(BaseModel):
    id: int
    session_id: str
    product_id: int
    title: str
    price: float
    image: Optional[str] = ""
    quantity: int
    subtotal: float

class CartSummary(BaseModel):
    items: List[CartItem]
    total_items: int
    total_amount: float
    currency: str = "USD"

class OrderItem(BaseModel):
    product_id: int
    title: str
    price: float
    quantity: int

class OrderCreate(BaseModel):
    customer_name: str
    customer_email: str
    card_number: str
    card_exp: str
    card_cvv: str

class OrderResponse(BaseModel):
    order_number: str
    customer_name: str
    customer_email: str
    total_amount: float
    currency: str
    status: str
    payment_id: Optional[str] = None
    created_at: str

# --- OBSERVABILITY & METRICS MODELS ---

class ServiceHealthStatus(BaseModel):
    service_name: str
    status: str  # HEALTHY, WARNING, CRITICAL, DOWN
    current_latency_ms: float
    p95_latency_ms: float
    error_rate_pct: float
    request_count_1m: int
    cpu_percent: float
    memory_percent: float
    slo_compliance_pct: float
    active_anomalies_count: int
    last_updated: str

class HostMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    process_memory_mb: float
    timestamp: str

class TelemetrySnapshot(BaseModel):
    host: HostMetrics
    services: Dict[str, ServiceHealthStatus]
    overall_health: str
    total_requests_recorded: int
    active_incidents_count: int

# --- ADAPTIVE THRESHOLDS & ANOMALY MODELS ---

class ThresholdConfigUpdate(BaseModel):
    service_name: str
    static_warning: Optional[float] = None
    static_critical: Optional[float] = None
    mode: Optional[str] = "hybrid"  # "static", "adaptive", "hybrid"

class AnomalyItem(BaseModel):
    id: int
    timestamp: str
    service_name: str
    detection_method: str  # "STATISTICAL_MAD", "ISOLATION_FOREST_ML", "DUAL_CONFIRMED"
    anomaly_score: float
    explanation: str
    metrics: Dict[str, Any]

# --- INCIDENT & RCA MODELS ---

class EvidenceItem(BaseModel):
    evidence_type: str
    metric_name: str
    observed_value: float
    expected_baseline: float
    confidence: float
    description: str

class IncidentDetail(BaseModel):
    incident_id: str
    title: str
    affected_service: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    status: str    # ACTIVE, INVESTIGATING, MITIGATING, RESOLVED
    root_cause_summary: Optional[str] = None
    blast_radius: List[str] = Field(default_factory=list)
    created_at: str
    resolved_at: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    recommended_recovery_action: Optional[str] = None

class RootCauseRankedCandidate(BaseModel):
    rank: int
    cause_title: str
    category: str  # "UPSTREAM_DEPENDENCY", "CODE_REGRESSION", "RESOURCE_EXHAUSTION", "EXTERNAL_API"
    confidence_score: float
    evidence_list: List[str]
    suggested_action: str

# --- RECOVERY & AUDIT MODELS ---

class RecoveryApprovalRequest(BaseModel):
    action_id: str
    approved: bool
    approver_name: str = "Admin SRE"
    notes: Optional[str] = "Approved after reviewing RCA evidence"

class RecoveryActionDetail(BaseModel):
    action_id: str
    incident_id: str
    action_name: str
    target_service: str
    status: str  # PENDING_APPROVAL, EXECUTING, VERIFYING, COMPLETED, FAILED
    requested_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    verified_at: Optional[str] = None
    pre_recovery_health: Optional[str] = None
    post_recovery_health: Optional[str] = None
    audit_log: Optional[str] = None

# --- CHAOS SIMULATION MODELS ---

class SimulationScenarioToggle(BaseModel):
    scenario: str  # "payment_latency", "order_500_surge", "db_lock", "high_cpu", "memory_leak", "product_delay", "traffic_spike"
    enabled: bool
    intensity_or_delay_ms: Optional[float] = None
    target_service: Optional[str] = None

class SimulationStateResponse(BaseModel):
    active_scenarios: Dict[str, Any]
    total_active: int
    message: str

# --- EVALUATION MODELS ---

class EvaluationReport(BaseModel):
    total_incidents_recorded: int
    mttd_seconds: float
    mttr_seconds: float
    false_positive_rate_pct: float
    rca_top1_accuracy_pct: float
    rca_top3_accuracy_pct: float
    recovery_success_rate_pct: float
    comparative_benchmarks: Dict[str, Any]

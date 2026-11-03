"""
AIOps Sentinel - Service Dependency & Blast-Radius Engine
Maintains directed acyclic graph (DAG) of microservice dependencies,
traces failure propagation, and calculates user-facing blast radius.
"""

from typing import Dict, List, Any, Set

class ServiceDependencyEngine:
    def __init__(self):
        # Directed dependencies: Service -> List of services it depends on (downstream calls)
        self.dependencies: Dict[str, List[str]] = {
            "order-service": ["cart-service", "payment-service", "database-service"],
            "cart-service": ["product-service", "database-service"],
            "payment-service": ["database-service"],
            "product-service": ["database-service"],
            "auth-service": ["database-service"],
            "database-service": []
        }

        # Reverse map: Service -> List of services that depend on IT (callers)
        self.callers: Dict[str, List[str]] = {
            "database-service": ["order-service", "cart-service", "payment-service", "product-service", "auth-service"],
            "payment-service": ["order-service"],
            "cart-service": ["order-service"],
            "product-service": ["cart-service"],
            "auth-service": [],
            "order-service": []
        }

        # User operation mapping per service
        self.user_impact_map: Dict[str, List[str]] = {
            "payment-service": ["Checkout Finalization", "Credit Card Processing", "Order Confirmation"],
            "order-service": ["Order Creation", "Order History Lookup", "Receipt Generation"],
            "cart-service": ["Add to Cart", "Update Quantities", "Cart View", "Checkout Initiation"],
            "product-service": ["Product Catalog Browsing", "Product Search", "Category Filtering", "Product Details"],
            "auth-service": ["Customer Login", "Account Profile Access", "Admin Authentication"],
            "database-service": ["ALL E-Commerce Operations (Catastrophic Data Store Outage)"]
        }

    def calculate_blast_radius(self, failing_service: str) -> Dict[str, Any]:
        """
        Given a failing or degraded service, traverse the dependency graph upwards
        to identify all impacted services, user operations, and overall severity radius.
        """
        impacted_services: Set[str] = {failing_service}
        queue = [failing_service]

        while queue:
            current = queue.pop(0)
            callers = self.callers.get(current, [])
            for c in callers:
                if c not in impacted_services:
                    impacted_services.add(c)
                    queue.append(c)

        # Aggregate user operations
        impacted_ops: Set[str] = set()
        for svc in impacted_services:
            ops = self.user_impact_map.get(svc, [])
            impacted_ops.update(ops)

        total_services = len(self.dependencies)
        blast_percentage = round((len(impacted_services) / total_services) * 100, 1)

        return {
            "root_service": failing_service,
            "impacted_services": list(impacted_services),
            "total_impacted_services": len(impacted_services),
            "blast_radius_percentage": blast_percentage,
            "impacted_user_operations": list(impacted_ops),
            "unaffected_services": [s for s in self.dependencies if s not in impacted_services]
        }

    def get_topology_graph(self, service_health_dict: Dict[str, str]) -> Dict[str, Any]:
        """
        Returns graph representation formatted for interactive UI rendering (Vis.js / SVG).
        Each node includes its live health status and blast-radius indicator.
        """
        nodes = []
        edges = []

        service_labels = {
            "auth-service": "Auth Service (JWT/Session)",
            "product-service": "Product Service (Catalog/Cache)",
            "cart-service": "Cart Service (Basket/Sync)",
            "order-service": "Order Service (Orchestrator)",
            "payment-service": "Payment Service (Gateway)",
            "database-service": "Database Service (SQLite WAL)"
        }

        for svc, label in service_labels.items():
            health = service_health_dict.get(svc, "HEALTHY")
            nodes.append({
                "id": svc,
                "label": label,
                "health": health,
                "color": self._health_to_color(health),
                "shape": "box"
            })

        for src, targets in self.dependencies.items():
            for tgt in targets:
                edges.append({
                    "from": src,
                    "to": tgt,
                    "arrows": "to",
                    "label": "depends on"
                })

        return {"nodes": nodes, "edges": edges}

    def _health_to_color(self, health: str) -> str:
        mapping = {
            "HEALTHY": "#10b981",    # Emerald green
            "WARNING": "#f59e0b",    # Amber
            "CRITICAL": "#ef4444",   # Crimson red
            "DOWN": "#7f1d1d"        # Dark maroon
        }
        return mapping.get(health, "#6b7280")

dependency_engine = ServiceDependencyEngine()

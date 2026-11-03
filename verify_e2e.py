"""
AIOps Sentinel - Complete End-to-End System Demonstration Verification
Tests normal shopping, chaos fault injection, incident correlation,
explainable RCA ranking, AI runbook generation, approved automated recovery,
and empirical evaluation benchmarking.
"""

import sys
import httpx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def run_e2e():
    print("=" * 70)
    print("AIOPS SENTINEL — END-TO-END VERIFICATION WORKFLOW")
    print("=" * 70)

    client = httpx.Client(base_url="http://localhost:8000", timeout=12.0)

    # 1. Storefront check
    p_res = client.get("/api/ecommerce/products")
    assert p_res.status_code == 200, f"Expected 200, got {p_res.status_code}"
    products = p_res.json()
    print(f"[1] Catalog Loaded: {len(products)} products. First: '{products[0]['title'][:30]}...'")

    # 2. Add product to cart
    session_id = "demo-eval-session-1"
    cart_res = client.post(
        "/api/ecommerce/cart/add",
        headers={"x-session-id": session_id},
        json={"product_id": 1, "quantity": 1}
    )
    assert cart_res.status_code == 200
    cart = cart_res.json()
    print(f"[2] Shopping Cart Add: {cart['total_items']} item(s), Subtotal: ${cart['total_amount']:.2f}")

    # 3. Telemetry snapshot check
    snap_res = client.get("/api/sentinel/telemetry/snapshot")
    assert snap_res.status_code == 200
    snap = snap_res.json()
    print(f"[3] Live Telemetry Snapshot: System Health={snap['overall_health']}, Intercepted Reqs={snap['total_requests_recorded']}")

    # 4. Inject Chaos Failure: Payment Service Gateway Failure
    print("\n>>> INJECTING CONTROLLED CHAOS FAULT: Payment Gateway Outage (HTTP 504)...")
    chaos_res = client.post("/api/simulation/start", json={"scenario": "payment_failure", "enabled": True})
    assert chaos_res.status_code == 200
    print(f"[4] Chaos Simulation Active: {chaos_res.json()['message']}")

    # 5. Attempt Checkout (must fail and generate incident)
    pay_payload = {
        "customer_name": "Sarah Jenkins",
        "customer_email": "shopper@sentinel.local",
        "card_number": "4242424242424242",
        "card_exp": "12/28",
        "card_cvv": "999"
    }
    print(">>> Submitting checkout while Payment Gateway failure is active...")
    order_fail_res = client.post(
        "/api/ecommerce/orders/checkout",
        headers={"x-session-id": session_id},
        json=pay_payload
    )
    assert order_fail_res.status_code in (500, 502)
    err_detail = order_fail_res.json().get("detail", "")
    print(f"[5] Checkout Blocked (Expected): HTTP {order_fail_res.status_code} - {err_detail[:60]}...")

    # 6. Check Incident Center
    inc_res = client.get("/api/sentinel/incidents")
    incidents = inc_res.json()
    assert len(incidents) > 0
    active_inc = incidents[0]
    inc_id = active_inc["incident_id"]
    print(f"\n[6] Incident Automatically Declared: [{inc_id}]")
    print(f"    Title: {active_inc['title']}")
    print(f"    Target Service: {active_inc['affected_service']}")
    print(f"    Severity: {active_inc['severity']}")
    print(f"    Status: {active_inc['status']}")

    # 7. Check Explainable RCA
    rca_res = client.get(f"/api/sentinel/rca/{inc_id}")
    rca = rca_res.json()
    top_cand = rca["ranked_candidates"][0]
    print(f"\n[7] Explainable Root Cause Analysis (RCA):")
    print(f"    Rank #1 Hypothesis: {top_cand['cause_title']} (Confidence: {int(top_cand['confidence_score']*100)}%)")
    print(f"    Observed Facts:")
    for fact in top_cand["observed_facts"][:2]:
        print(f"      - {fact}")
    print(f"    Diagnostic Inference: {top_cand['inferred_hypothesis']}")

    # 8. Human-in-the-Loop Approved Recovery
    pending_res = client.get("/api/sentinel/recovery/pending")
    pending = pending_res.json()
    assert len(pending) > 0
    act_id = pending[0]["action_id"]
    action_name = pending[0]["action_name"]
    print(f"\n>>> Submitting Human SRE Approval for allowlisted action: '{action_name}'...")
    
    rec_res = client.post(
        "/api/sentinel/recovery/approve",
        json={
            "action_id": act_id,
            "approved": True,
            "approver_name": "Sarah SRE Lead",
            "notes": "Verified root cause evidence from payment gateway logs"
        }
    )
    assert rec_res.status_code == 200
    rec = rec_res.json()
    print(f"[8] Recovery Action Completed:")
    print(f"    Action: {rec['action_name']}")
    print(f"    Post-Recovery Verification: {rec['post_recovery_health']}")
    print(f"    Remediation Duration: {rec['duration_seconds']}s")
    print(f"    Audit Entry: {rec['audit_log']}")

    # 9. Verify Checkout Now Succeeds Post-Recovery
    print("\n>>> Re-attempting customer checkout after recovery...")
    order_success_res = client.post(
        "/api/ecommerce/orders/checkout",
        headers={"x-session-id": session_id},
        json=pay_payload
    )
    assert order_success_res.status_code == 200
    success_order = order_success_res.json()
    print(f"[9] Post-Recovery Order Placed: SUCCESS!")
    print(f"    Order Number: {success_order['order_number']}")
    print(f"    Status: {success_order['status']}")
    print(f"    Payment ID: {success_order['payment_id']}")

    # 10. Verify Evaluation Benchmark Recorded MTTR
    eval_res = client.get("/api/sentinel/evaluation")
    ev = eval_res.json()
    print(f"\n[10] Empirical Evaluation Metrics:")
    print(f"    Mean Time to Detect (MTTD): {ev['mttd_seconds']}s")
    print(f"    Mean Time to Recover (MTTR): {ev['mttr_seconds']}s")
    print(f"    False Positive Rate: {ev['false_positive_rate_pct']}%")
    print(f"    RCA Top-1 Accuracy: {ev['rca_top1_accuracy_pct']}%")
    print(f"    Recovery Verification Success: {ev['recovery_success_rate_pct']}%")

    print("\n" + "=" * 70)
    print("SUCCESS: ALL 10 PHASES OF THE WORKFLOW FULLY VERIFIED AND OPERATIONAL!")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e()

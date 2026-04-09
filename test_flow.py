"""Quick test of the two-step decision confirmation flow."""
import requests, json

BASE = "http://127.0.0.1:8000"

# Step 1: Extract
print("=" * 60)
print("STEP 1: POST /schema  (extract decisions)")
print("=" * 60)
r = requests.post(f"{BASE}/schema", json={
    "requirements": "I need a multi-tenant SaaS for project management with soft deletes and audit logging."
})
print(f"Status: {r.status_code}")
d = r.json()

pending = d.get("pending_decisions", [])
request_id = d.get("request_id", "")
message = d.get("message", "")

print(f"Request ID: {request_id}")
print(f"Message: {message}")
print(f"Pending decisions: {len(pending)}")

for p in pending:
    print(f"  {p['decision_name']:20} → {p['recommended_choice']:15} (conf={p['confidence']:.2f})")
    print(f"    Alternatives: {p['alternative_choices']}")
    print(f"    Reasoning: {p['reasoning'][:80]}...")

if not pending:
    print("\nNo pending decisions — DDL returned directly.")
    print(f"Tables: {d.get('tables', [])}")
    print(f"DDL preview: {d.get('ddl', '')[:200]}")
else:
    # Step 2: Confirm with defaults
    print("\n" + "=" * 60)
    print("STEP 2: POST /schema/confirm  (confirm and generate)")
    print("=" * 60)
    
    overrides = [
        {"decision_name": p["decision_name"], "chosen_choice": p["recommended_choice"], "confidence": 0.95}
        for p in pending
    ]
    
    r2 = requests.post(f"{BASE}/schema/confirm", json={
        "request_id": request_id,
        "requirements": "I need a multi-tenant SaaS for project management with soft deletes and audit logging.",
        "decision_overrides": overrides
    })
    print(f"Status: {r2.status_code}")
    d2 = r2.json()
    
    if r2.status_code == 200:
        print(f"Tables: {d2.get('tables', [])}")
        ddl = d2.get("ddl", "")
        print(f"DDL length: {len(ddl)} chars")
        print(f"Has tenant_id: {'tenant_id' in ddl}")
        print(f"Has is_deleted: {'is_deleted' in ddl}")
        print(f"\nDDL preview:\n{ddl[:500]}")
    else:
        print(f"Error: {d2}")

print("\nDONE.")

import json
from pydantic import BaseModel, Field

# ── Closed concept set ─────────────────────────────────────────────────────────
CONCEPTS = {
    "user_authentication":  "User accounts, passwords, sessions, roles, permissions",
    "product_catalog":      "Products, categories, attributes, images, pricing",
    "e_commerce_orders":    "Shopping cart, checkout, order lifecycle, order items",
    "payment_processing":   "Payments, payment methods, refunds, reconciliation",
    "invoicing":            "Sales invoices, invoice items, tax line entries",
    "inventory_management": "Warehouses, stock entries, stock ledger, reorder levels",
    "customer_management":  "Customer records, addresses, groups, contacts",
    "gst_compliance":       "Indian GST tax categories, HSN codes, tax entries",
    "employee_management":  "Employee records, departments, designations",
    "project_tracking":     "Projects, tasks, time logs, milestones",
}

DECISIONS = {
    "pk_strategy": {
        "default":      "auto_increment",
        "alternatives": ["uuid"],
        "critical":     False
    },
    "delete_strategy": {
        "default":      "soft_delete",
        "alternatives": ["hard_delete"],
        "critical":     False
    },
    "tenancy_model": {
        "default":      "single_tenant",
        "alternatives": ["multi_tenant"],
        "critical":     True
    },
}

# ── Pydantic models ────────────────────────────────────────────────────────────
class ExtractedConcept(BaseModel):
    name:         str
    confidence:   float = Field(ge=0.0, le=1.0)
    matched_text: str

class ExtractedDecision(BaseModel):
    name:        str
    choice:      str
    confidence:  float = Field(ge=0.0, le=1.0)
    signal_text: str

class UnmatchedItem(BaseModel):
    raw_text: str
    category: str

class ExtractionResult(BaseModel):
    concepts:  list[ExtractedConcept]
    decisions: list[ExtractedDecision] = []
    unmatched: list[UnmatchedItem]     = []

# ── Mock extraction function ───────────────────────────────────────────────────
def extract(requirements: str) -> ExtractionResult:
    mock_responses = {
        "Online store with products, shopping cart, and payments": {
            "concepts": [
                {"name": "e_commerce_orders",  "confidence": 0.95, "matched_text": "shopping cart"},
                {"name": "product_catalog",    "confidence": 0.90, "matched_text": "products"},
                {"name": "payment_processing", "confidence": 0.95, "matched_text": "payments"},
            ],
            "decisions": [],
            "unmatched": []
        },
        "Indian retail with GST invoicing and inventory": {
            "concepts": [
                {"name": "gst_compliance",       "confidence": 0.95, "matched_text": "GST"},
                {"name": "invoicing",            "confidence": 0.95, "matched_text": "invoicing"},
                {"name": "inventory_management", "confidence": 0.90, "matched_text": "inventory"},
            ],
            "decisions": [],
            "unmatched": []
        },
        "IoT fleet management with telemetry dashboards": {
            "concepts":  [],
            "decisions": [],
            "unmatched": [
                {"raw_text": "IoT fleet management", "category": "potential_table"},
                {"raw_text": "telemetry dashboards", "category": "potential_table"},
            ]
        },
        "Multi-tenant SaaS for managing client subscriptions": {
            "concepts": [
                {"name": "customer_management", "confidence": 0.85, "matched_text": "client subscriptions"},
            ],
            "decisions": [
                {"name": "tenancy_model", "choice": "multi_tenant", "confidence": 0.95, "signal_text": "Multi-tenant"},
            ],
            "unmatched": []
        },
        "A cloud app for client data": {
            "concepts": [
                {"name": "customer_management", "confidence": 0.70, "matched_text": "client data"},
            ],
            "decisions": [
                {"name": "tenancy_model", "choice": "multi_tenant", "confidence": 0.60, "signal_text": "cloud app"},
            ],
            "unmatched": []
        },
    }

    raw = mock_responses.get(requirements, {
        "concepts":  [],
        "decisions": [],
        "unmatched": [{"raw_text": requirements, "category": "potential_table"}]
    })

    result = ExtractionResult(**raw)

    # Gatekeeper: reject hallucinated concepts
    valid = []
    for c in result.concepts:
        if c.name not in CONCEPTS:
            print(f"  REJECTED hallucinated: {c.name}")
            result.unmatched.append(
                UnmatchedItem(raw_text=c.matched_text, category="potential_table")
            )
        elif c.confidence < 0.5:
            print(f"  DROPPED low confidence: {c.name} ({c.confidence})")
        else:
            valid.append(c)
    result.concepts = valid

    # Critical decision gate
    for d in result.decisions:
        if d.name in DECISIONS and DECISIONS[d.name].get("critical"):
            if d.choice != DECISIONS[d.name]["default"] and d.confidence < 0.85:
                print(f"  HALTED: {d.name}={d.choice} "
                      f"(confidence {d.confidence} < 0.85)")
                print(f"  Would need user confirmation before applying!")

    return result

# ── Tests ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "Online store with products, shopping cart, and payments",
        "Indian retail with GST invoicing and inventory",
        "IoT fleet management with telemetry dashboards",
        "Multi-tenant SaaS for managing client subscriptions",
        "A cloud app for client data",
    ]

    for i, req in enumerate(tests, 1):
        print(f"\n{'='*60}")
        print(f"Test {i}: {req}")
        print(f"{'='*60}")

        r = extract(req)

        for c in r.concepts:
            print(f"  concept:   {c.name:30} confidence: {c.confidence:.2f} | '{c.matched_text}'")
        for d in r.decisions:
            print(f"  decision:  {d.name}={d.choice} ({d.confidence:.2f}) | '{d.signal_text}'")
        for u in r.unmatched:
            print(f"  unmatched: [{u.category}] {u.raw_text}")
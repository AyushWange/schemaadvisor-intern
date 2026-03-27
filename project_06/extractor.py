import os
import json
from pathlib import Path
from pydantic import BaseModel, Field

# Load .env from project root (safe no-op if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

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

# ── LLM Prompt ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a database schema advisor. Given a natural language business requirement, extract:
1. Which business CONCEPTS are needed (from the closed list below)
2. Any DESIGN DECISIONS implied by the text

CLOSED CONCEPT LIST (you may ONLY pick from these):
{concepts}

DESIGN DECISIONS (you may ONLY pick from these options):
- pk_strategy: "auto_increment" (default) or "uuid"
- delete_strategy: "soft_delete" (default) or "hard_delete"
- tenancy_model: "single_tenant" (default) or "multi_tenant"

Respond with ONLY a valid JSON object in this exact format:
{{
  "concepts": [
    {{"name": "<concept_name>", "confidence": <0.0-1.0>, "matched_text": "<phrase from input that triggered this>"}}
  ],
  "decisions": [
    {{"name": "<decision_name>", "choice": "<choice>", "confidence": <0.0-1.0>, "signal_text": "<phrase from input>"}}
  ],
  "unmatched": [
    {{"raw_text": "<phrase>", "category": "potential_table"}}
  ]
}}

Rules:
- Only include concepts with confidence >= 0.5
- Only include non-default decisions (skip if default choice)
- Put anything you cannot map to the closed concept list in "unmatched"
- Do not invent concept names not in the list above
"""

def _build_prompt() -> str:
    concept_lines = "\n".join(
        f'  "{name}": "{desc}"' for name, desc in CONCEPTS.items()
    )
    return SYSTEM_PROMPT.format(concepts=concept_lines)

# ── Real LLM call ──────────────────────────────────────────────────────────────
def _call_claude(requirements: str) -> dict:
    """Call Anthropic Claude API and return parsed JSON dict."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=_build_prompt(),
        messages=[
            {"role": "user", "content": f"Business requirement: {requirements}"}
        ]
    )

    raw_text = message.content[0].text.strip()

    # Strip markdown code fences if Claude wraps in ```json ... ```
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)

# ── Keyword-based mock fallback ────────────────────────────────────────────────
# Works for ANY input — no API key or credits needed.
KEYWORD_MAP = {
    "e_commerce_orders":    ["shop", "cart", "order", "checkout", "ecommerce", "e-commerce", "store", "buy", "purchase"],
    "product_catalog":      ["product", "catalog", "category", "item", "sku", "merchandise"],
    "payment_processing":   ["payment", "pay", "billing", "refund", "transaction", "stripe"],
    "invoicing":            ["invoic", "bill", "receipt"],
    "inventory_management": ["inventory", "stock", "warehouse", "reorder", "supply"],
    "customer_management":  ["customer", "client", "patient", "member", "contact", "user profile"],
    "user_authentication":  ["login", "auth", "account", "password", "session", "role", "permission"],
    "gst_compliance":       ["gst", "hsn", "indian tax", "india"],
    "employee_management":  ["employee", "staff", "hr", "payroll", "department", "onboard", "leave", "salary"],
    "project_tracking":     ["project", "task", "milestone", "sprint", "agile", "timelog", "schedule", "appointment"],
}

def _mock_extract(requirements: str) -> dict:
    req_lower = requirements.lower()
    found = []
    for concept, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in req_lower:
                found.append({
                    "name":         concept,
                    "confidence":   0.85,
                    "matched_text": kw,
                })
                break  # one hit per concept

    if found:
        return {"concepts": found, "decisions": [], "unmatched": []}

    return {
        "concepts":  [],
        "decisions": [],
        "unmatched": [{"raw_text": requirements, "category": "potential_table"}]
    }

# ── Main extraction function ────────────────────────────────────────────────────
def extract(requirements: str) -> ExtractionResult:
    """
    Extract business concepts from natural language requirements.
    Uses Claude API if ANTHROPIC_API_KEY is set, else falls back to keyword matching.
    """
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    if has_key:
        print("  [LLM] Calling Claude API...")
        try:
            raw = _call_claude(requirements)
        except Exception as e:
            print(f"  [LLM] API call failed ({e}), falling back to keyword match.")
            raw = _mock_extract(requirements)
    else:
        print("  [MOCK] No ANTHROPIC_API_KEY — using keyword matching.")
        raw = _mock_extract(requirements)

    result = ExtractionResult(**raw)

    # Gatekeeper: reject hallucinated concepts
    valid = []
    for c in result.concepts:
        if c.name not in CONCEPTS:
            print(f"  REJECTED hallucinated concept: {c.name}")
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
        "Hospital management with patient records and appointment scheduling",
        "HR platform for employee onboarding, payroll, and leave tracking",
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
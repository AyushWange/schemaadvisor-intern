import os
import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

# Load .env from project root (safe no-op if python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

# ── Closed concept set (15 per spec §4.1.1) ───────────────────────────────────
CONCEPTS = {
    # Commerce
    "user_authentication":  "User accounts, passwords, sessions, roles, permissions",
    "product_catalog":      "Products, categories, attributes, images, pricing",
    "e_commerce_orders":    "Shopping cart, checkout, order lifecycle, order items",
    "customer_management":  "Customer records, addresses, groups, contacts",
    # Finance
    "payment_processing":   "Payments, payment methods, refunds, reconciliation",
    "invoicing":            "Sales invoices, invoice items, tax line entries",
    "multi_currency":       "Currency definitions, exchange rates, conversions",
    "gst_compliance":       "Indian GST tax categories, HSN codes, tax entries",
    # Operations
    "inventory_management": "Warehouses, stock entries, stock ledger, reorder levels",
    "supplier_management":  "Supplier records, groups, payment terms, purchase orders",
    "employee_management":  "Employee records, departments, designations",
    "project_tracking":     "Projects, tasks, time logs, milestones",
    # Platform
    "file_attachments":     "File upload records, storage references, metadata",
    "notifications":        "Notification records, delivery channels, read status",
    "reporting_analytics":  "Aggregate tables, dashboard data sources, metrics",
}

# ── Design decisions (6 per spec §4.1.2) ──────────────────────────────────────
DECISIONS = {
    "pk_strategy": {
        "default":      "auto_increment",
        "alternatives": ["uuid"],
        "critical":     False,
        "description":  "Determines PK column type on every table",
    },
    "delete_strategy": {
        "default":      "soft_delete",
        "alternatives": ["hard_delete"],
        "critical":     False,
        "description":  "Adds is_deleted, deleted_at to applicable tables",
    },
    "tenancy_model": {
        "default":      "single_tenant",
        "alternatives": ["multi_tenant"],
        "critical":     True,
        "description":  "Adds tenant_id FK to every table (multi_tenant)",
    },
    "audit_policy": {
        "default":      "full_audit",
        "alternatives": ["no_audit"],
        "critical":     False,
        "description":  "Adds created_at, updated_at, created_by, updated_by",
    },
    "hierarchy_approach": {
        "default":      "adjacency_list",
        "alternatives": ["nested_set", "closure_table"],
        "critical":     False,
        "description":  "Determines tree structure modeling strategy",
    },
    "temporal_strategy": {
        "default":      "current_only",
        "alternatives": ["versioned"],
        "critical":     False,
        "description":  "Adds valid_from, valid_to, version columns when versioned",
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
    raw_text:       str
    category:       str   # potential_table | potential_column | unsupported_logic
    nearest_concept: Optional[str] = None

class ExtractionResult(BaseModel):
    concepts:  list[ExtractedConcept]
    decisions: list[ExtractedDecision] = []
    unmatched: list[UnmatchedItem]     = []

# ── LLM Prompt ─────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a database schema advisor. Given a natural language business requirement, extract:
1. Which business CONCEPTS are needed (from the closed list below)
2. Any DESIGN DECISIONS implied by the text
3. Anything you CANNOT map to the concept list goes in "unmatched"

CLOSED CONCEPT LIST (you may ONLY pick from these):
{concepts}

DESIGN DECISIONS (you may ONLY pick from these options):
- pk_strategy: "auto_increment" (default) or "uuid"
- delete_strategy: "soft_delete" (default) or "hard_delete"
- tenancy_model: "single_tenant" (default) or "multi_tenant"
- audit_policy: "full_audit" (default) or "no_audit"
- hierarchy_approach: "adjacency_list" (default) or "nested_set" or "closure_table"
- temporal_strategy: "current_only" (default) or "versioned"

Respond with ONLY a valid JSON object in this exact format:
{{
  "concepts": [
    {{"name": "<concept_name>", "confidence": <0.0-1.0>, "matched_text": "<phrase from input that triggered this>"}}
  ],
  "decisions": [
    {{"name": "<decision_name>", "choice": "<choice>", "confidence": <0.0-1.0>, "signal_text": "<phrase from input>"}}
  ],
  "unmatched": [
    {{"raw_text": "<phrase>", "category": "potential_table|potential_column|unsupported_logic", "nearest_concept": "<closest concept or null>"}}
  ]
}}

Rules:
- Only include concepts with confidence >= 0.5
- Only include non-default decisions (skip if default choice)
- Put anything you cannot map to the closed concept list in "unmatched"
- Category must be one of: potential_table, potential_column, unsupported_logic
- nearest_concept must be a key from the concept list above, or null
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

# ── Keyword-based mock fallback (15 concepts) ──────────────────────────────────
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
    # 5 new concepts
    "supplier_management":  ["supplier", "vendor", "purchase order", "procurement", "sourcing"],
    "multi_currency":       ["currency", "forex", "exchange rate", "multi-currency", "multicurrency", "foreign currency"],
    "file_attachments":     ["file", "attachment", "upload", "document", "pdf", "image upload", "storage", "s3"],
    "notifications":        ["notification", "alert", "email alert", "push notification", "notify", "inbox"],
    "reporting_analytics":  ["report", "dashboard", "analytics", "metric", "chart", "kpi", "aggregate"],
}

# ── Decision keyword signals ───────────────────────────────────────────────────
DECISION_SIGNALS = {
    "tenancy_model": {
        "multi_tenant": ["multi-tenant", "multi tenant", "saas", "isolated data", "tenant", "silo"],
    },
    "pk_strategy": {
        "uuid": ["uuid", "globally unique", "distributed id"],
    },
    "delete_strategy": {
        "hard_delete": ["hard delete", "permanent delete", "physical delete"],
    },
    "audit_policy": {
        "no_audit": ["no audit", "skip audit", "no logging"],
    },
    "hierarchy_approach": {
        "nested_set":    ["nested set", "lft rgt", "materialized path"],
        "closure_table": ["closure table", "ancestor table"],
    },
    "temporal_strategy": {
        "versioned": ["version history", "versioned", "audit trail", "temporal", "time series", "history"],
    },
}

def _mock_extract(requirements: str) -> dict:
    req_lower = requirements.lower()
    found = []

    # Extract concepts
    for concept, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in req_lower:
                found.append({
                    "name":         concept,
                    "confidence":   0.85,
                    "matched_text": kw,
                })
                break  # one hit per concept

    # Extract decisions (non-default only) — always run regardless of concepts
    decisions_found = []
    seen_decisions = set()
    for decision_name, choices in DECISION_SIGNALS.items():
        if decision_name in seen_decisions:
            continue
        for choice, signals in choices.items():
            matched = False
            for sig in signals:
                if sig in req_lower:
                    decisions_found.append({
                        "name":        decision_name,
                        "choice":      choice,
                        "confidence":  0.85,
                        "signal_text": sig,
                    })
                    seen_decisions.add(decision_name)
                    matched = True
                    break
            if matched:
                break

    if found:
        return {"concepts": found, "decisions": decisions_found, "unmatched": []}

    # Nothing matched — return structured unmatched
    return {
        "concepts":  [],
        "decisions": decisions_found,
        "unmatched": [{
            "raw_text":        requirements,
            "category":        "potential_table",
            "nearest_concept": None,
        }],
    }


# ── Nearest concept via TF-IDF (used for unmatched nearest_concept field) ──────
_search_cache = None

def _get_nearest_concept(raw_text: str) -> Optional[str]:
    """Return the closest CONCEPT key using TF-IDF, or None if below threshold."""
    global _search_cache
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return None

    if _search_cache is None:
        names, corpus = [], []
        for name, desc in CONCEPTS.items():
            names.append(name)
            corpus.append(desc)
        vec = TfidfVectorizer(stop_words="english")
        mat = vec.fit_transform(corpus)
        _search_cache = (names, vec, mat)

    names, vec, mat = _search_cache
    try:
        q   = vec.transform([raw_text])
        sim = cosine_similarity(q, mat)[0]
        best_idx, best_score = max(enumerate(sim), key=lambda x: x[1])
        return names[best_idx] if best_score >= 0.1 else None
    except Exception:
        return None

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

    # Normalise: ensure unmatched items have the 3-field structure
    for u in raw.get("unmatched", []):
        if "nearest_concept" not in u:
            u["nearest_concept"] = None
        if "category" not in u:
            u["category"] = "potential_table"

    result = ExtractionResult(**raw)

    # Gatekeeper: reject hallucinated concepts
    valid = []
    for c in result.concepts:
        if c.name not in CONCEPTS:
            print(f"  REJECTED hallucinated concept: {c.name}")
            nearest = _get_nearest_concept(c.matched_text)
            result.unmatched.append(
                UnmatchedItem(
                    raw_text=c.matched_text,
                    category="potential_table",
                    nearest_concept=nearest,
                )
            )
        elif c.confidence < 0.5:
            print(f"  DROPPED low confidence: {c.name} ({c.confidence})")
        else:
            valid.append(c)
    result.concepts = valid

    # Enrich unmatched items with nearest_concept where missing
    for u in result.unmatched:
        if u.nearest_concept is None:
            u.nearest_concept = _get_nearest_concept(u.raw_text)

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
        "SaaS analytics platform with multi-currency and supplier management",
        "Document management with file uploads and notifications",
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
            nc = f" → nearest: {u.nearest_concept}" if u.nearest_concept else ""
            print(f"  unmatched: [{u.category}] {u.raw_text}{nc}")
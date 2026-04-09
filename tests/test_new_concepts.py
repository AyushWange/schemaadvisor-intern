"""
test_new_concepts.py
Tests for the 5 new DomainConcepts, 3 new DesignDecisions,
structured unmatched capture, and updated_by audit pattern.
"""
import pytest
from project_06.extractor import _mock_extract, ExtractionResult, CONCEPTS, DECISIONS


def extract(req):
    return ExtractionResult(**_mock_extract(req))


# ── 1. All 15 concepts are registered ─────────────────────────────────────────

def test_all_15_concepts_registered():
    expected = {
        "user_authentication", "product_catalog", "e_commerce_orders",
        "customer_management", "payment_processing", "invoicing",
        "multi_currency", "gst_compliance", "inventory_management",
        "supplier_management", "employee_management", "project_tracking",
        "file_attachments", "notifications", "reporting_analytics",
    }
    assert expected == set(CONCEPTS.keys()), \
        f"Missing: {expected - set(CONCEPTS.keys())}"


# ── 2. All 6 decisions are registered ─────────────────────────────────────────

def test_all_6_decisions_registered():
    expected = {
        "pk_strategy", "delete_strategy", "tenancy_model",
        "audit_policy", "hierarchy_approach", "temporal_strategy",
    }
    assert expected == set(DECISIONS.keys()), \
        f"Missing: {expected - set(DECISIONS.keys())}"


def test_audit_policy_decision_defaults_to_full_audit():
    assert DECISIONS["audit_policy"]["default"] == "full_audit"
    assert "no_audit" in DECISIONS["audit_policy"]["alternatives"]
    assert DECISIONS["audit_policy"]["critical"] is False


def test_temporal_strategy_decision_defaults_to_current_only():
    assert DECISIONS["temporal_strategy"]["default"] == "current_only"
    assert "versioned" in DECISIONS["temporal_strategy"]["alternatives"]


def test_hierarchy_approach_has_closure_table():
    assert "closure_table" in DECISIONS["hierarchy_approach"]["alternatives"]


# ── 3. New concepts can be extracted by mock ──────────────────────────────────

def test_supplier_management_extracted():
    result = extract("Platform with supplier and vendor management")
    names = [c.name for c in result.concepts]
    assert "supplier_management" in names


def test_multi_currency_extracted():
    result = extract("Finance app with multi-currency and exchange rates")
    names = [c.name for c in result.concepts]
    assert "multi_currency" in names


def test_file_attachments_extracted():
    result = extract("App with file upload and document storage")
    names = [c.name for c in result.concepts]
    assert "file_attachments" in names


def test_notifications_extracted():
    result = extract("System with push notifications and alert inbox")
    names = [c.name for c in result.concepts]
    assert "notifications" in names


def test_reporting_analytics_extracted():
    result = extract("Business intelligence dashboard with analytics and KPI reports")
    names = [c.name for c in result.concepts]
    assert "reporting_analytics" in names


# ── 4. Decision signals extracted correctly ───────────────────────────────────

def test_temporal_strategy_signal_extracted():
    # 'versioned' is the direct signal keyword
    result = extract("App with versioned records for audit history")
    decision_names = [d.name for d in result.decisions]
    assert "temporal_strategy" in decision_names
    temporal = next(d for d in result.decisions if d.name == "temporal_strategy")
    assert temporal.choice == "versioned"


def test_no_audit_signal_extracted():
    # 'no audit' is the direct signal keyword
    result = extract("Lightweight app with no audit trail requirements")
    decision_names = [d.name for d in result.decisions]
    assert "audit_policy" in decision_names
    audit = next(d for d in result.decisions if d.name == "audit_policy")
    assert audit.choice == "no_audit"


# ── 5. Structured unmatched capture ──────────────────────────────────────────

def test_unmatched_has_category_field():
    result = extract("Custom blockchain ledger system")
    assert len(result.unmatched) > 0
    for u in result.unmatched:
        assert u.category in ("potential_table", "potential_column", "unsupported_logic")


def test_unmatched_has_nearest_concept_field():
    """nearest_concept can be None or a valid concept name."""
    result = extract("Custom blockchain ledger system")
    for u in result.unmatched:
        assert hasattr(u, "nearest_concept")
        if u.nearest_concept is not None:
            assert u.nearest_concept in CONCEPTS


# ── 6. Pipeline produces tables for new concepts ──────────────────────────────

def test_pipeline_supplier_management_tables():
    from project_12.pipeline import select_tables

    class C:
        def __init__(self, name, confidence=0.9):
            self.name = name
            self.confidence = confidence

    tables = select_tables([C("supplier_management")])
    names = [t["name"] for t in tables]
    assert "suppliers" in names
    assert "purchase_orders" in names


def test_pipeline_multi_currency_tables():
    from project_12.pipeline import select_tables

    class C:
        def __init__(self, name, confidence=0.9):
            self.name = name
            self.confidence = confidence

    tables = select_tables([C("multi_currency")])
    names = [t["name"] for t in tables]
    assert "currencies" in names
    assert "exchange_rates" in names


def test_pipeline_notifications_tables():
    from project_12.pipeline import select_tables

    class C:
        def __init__(self, name, confidence=0.9):
            self.name = name
            self.confidence = confidence

    tables = select_tables([C("notifications")])
    names = [t["name"] for t in tables]
    assert "notifications" in names


# ── 7. PATTERNS now includes updated_by and temporal_version ─────────────────

def test_audit_columns_includes_updated_by():
    from project_12.pipeline import PATTERNS
    col_names = [c["name"] for c in PATTERNS["audit_columns"]]
    assert "created_at"  in col_names
    assert "updated_at"  in col_names
    assert "created_by"  in col_names
    assert "updated_by"  in col_names  # was missing before spec fix


def test_temporal_version_pattern_exists():
    from project_12.pipeline import PATTERNS
    assert "temporal_version" in PATTERNS
    col_names = [c["name"] for c in PATTERNS["temporal_version"]]
    assert "valid_from" in col_names
    assert "valid_to"   in col_names
    assert "version"    in col_names


def test_system_tables_has_tenants():
    from project_12.pipeline import SYSTEM_TABLES
    assert "tenants" in SYSTEM_TABLES
    col_names = [c["name"] for c in SYSTEM_TABLES["tenants"]["columns"]]
    assert "id"        in col_names
    assert "slug"      in col_names
    assert "is_active" in col_names

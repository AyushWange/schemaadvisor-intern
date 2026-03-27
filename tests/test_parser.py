import pytest
import os
from project_03.parser import parse_doctype

# Fixture to provide the path to the sample doctype JSON
@pytest.fixture
def sample_json_path():
    # Use the actual sample file from project_03
    return os.path.join(os.path.dirname(__file__), "..", "project_03", "sample_doctype.json")

def test_doctype_parsing_overall(sample_json_path):
    known = {"customer", "sales_invoice"}
    result = parse_doctype(sample_json_path, known)
    
    assert result["name"] == "sales_invoice"
    assert result["module"] == "accounts"
    assert len(result["columns"]) > 0

def test_framework_columns_excluded(sample_json_path):
    result = parse_doctype(sample_json_path, set())
    col_names = [c["name"] for c in result["columns"]]
    
    # Framework fields that exist in the JSON but should be stripped
    assert "naming_series" not in col_names
    assert "parent" not in col_names
    assert "idx" not in col_names
    assert "docstatus" not in col_names

def test_layout_fields_excluded(sample_json_path):
    result = parse_doctype(sample_json_path, set())
    col_names = [c["name"] for c in result["columns"]]
    
    # Section Break and Column Break fields should be stripped
    assert "section_break_1" not in col_names

def test_primary_key_is_name(sample_json_path):
    result = parse_doctype(sample_json_path, set())
    
    # Find the 'name' column
    name_col = next(c for c in result["columns"] if c["name"] == "name")
    assert name_col["primary_key"] is True
    assert name_col["data_type"] == "VARCHAR(140)" # ERPNext Data field

def test_reference_classification(sample_json_path):
    known = {"customer", "sales_invoice"}
    result = parse_doctype(sample_json_path, known)
    
    # Check references
    refs = result["references"]
    
    # Check customer (required link, target known -> candidate_enforced)
    customer_ref = next(r for r in refs if r["to_table"] == "customer")
    assert customer_ref["ref_type"] == "candidate_enforced"
    assert customer_ref["required"] is True
    
    # Check sales_invoice (maybe not required or target known -> logical)
    # The JSON has it as a Link, let's verify how it was parsed
    sales_invoice_ref = next((r for r in refs if r["to_table"] == "sales_invoice"), None)
    if sales_invoice_ref:
        assert sales_invoice_ref["ref_type"] == "logical"

def test_pattern_detection(sample_json_path):
    result = parse_doctype(sample_json_path, set())
    
    patterns = [p["pattern_id"] for p in result["patterns_detected"]]
    
    # Assuming sample JSON has docstatus and audit fields
    assert "audit_columns" in patterns
    assert "status_workflow" in patterns

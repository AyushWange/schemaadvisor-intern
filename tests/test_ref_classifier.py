import pytest
from project_08.ref_classifier import pass1_classify, pass2_break_cycles

def test_pass1_counts():
    references = [
        ("orders", "customers", True),
        ("orders", "shipping_address", False),
        ("invoices", "sales_order", False),
    ]
    known_tables = {"customers", "orders", "shipping_address", "invoices", "sales_order"}
    
    candidate, logical = pass1_classify(references, known_tables)
    
    assert len(candidate) == 1
    assert candidate[0] == ("orders", "customers")
    
    # 2 logicals
    assert len(logical) == 2

def test_pass2_breaks_cycles():
    candidate_enforced = [
        ("purchase_order", "supplier"),
        ("supplier", "supplier_group"),
        ("supplier_group", "purchase_order"),
    ]
    
    final_enforced, downgrades = pass2_break_cycles(candidate_enforced)
    
    # One cycle, so one edge should be downgraded
    assert len(final_enforced) == 2
    assert len(downgrades) == 1
    
    # It downgrades purchase_order -> supplier because it has lowest inbound count
    assert downgrades[0]["from"] == "purchase_order"
    assert downgrades[0]["to"] == "supplier"

def test_no_false_downgrades():
    candidate_enforced = [
        ("orders", "customers"),
        ("order_items", "orders"),
        ("order_items", "products")
    ]
    
    final_enforced, downgrades = pass2_break_cycles(candidate_enforced)
    
    assert len(downgrades) == 0
    assert len(final_enforced) == 3

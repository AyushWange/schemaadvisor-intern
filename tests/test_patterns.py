import pytest
from project_04.patterns import apply_pattern, orders_table, legacy_table

def test_clean_table_all_patterns_added():
    # Apply all three patterns
    t1 = apply_pattern(orders_table, "audit_columns")
    t2 = apply_pattern(t1, "soft_delete")
    t3 = apply_pattern(t2, "status_workflow")
    
    col_names = [c["name"] for c in t3["columns"]]
    
    # Audit columns added
    assert "created_at" in col_names
    assert "updated_at" in col_names
    assert "created_by" in col_names
    
    # Soft delete columns added
    assert "is_deleted" in col_names
    assert "deleted_at" in col_names
    
    # Status workflow columns a status column is typically added if not present
    # orders_table already had a status column! Let's check status_changed_at
    assert "status_changed_at" in col_names

def test_legacy_table_semantic_dedup():
    # Legacy table has 'creation', 'modified', 'modified_by'
    t1 = apply_pattern(legacy_table, "audit_columns")
    
    col_names = [c["name"] for c in t1["columns"]]
    
    # Semantic equivalents should NOT be added
    assert "created_at" not in col_names
    assert "updated_at" not in col_names
    assert "updated_by" not in col_names
    
    # But created_by should be added (because modified_by != created_by)
    assert "created_by" in col_names
    assert "creation" in col_names # Kept existing

def test_no_duplicate_columns():
    t1 = apply_pattern(orders_table, "audit_columns")
    t2 = apply_pattern(t1, "soft_delete")
    t3 = apply_pattern(t2, "status_workflow")
    
    # Also test legacy table
    l1 = apply_pattern(legacy_table, "audit_columns")
    l2 = apply_pattern(l1, "soft_delete")
    
    for table in [t3, l2]:
        names = [c["name"] for c in table["columns"]]
        assert len(names) == len(set(names)), f"Duplicate columns found in table {table['name']}"

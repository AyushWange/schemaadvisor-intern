import copy

orders_table = {
    "name": "orders",
    "columns": [
        {"name": "id",           "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "customer_id",  "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "order_date",   "data_type": "TIMESTAMP",    "primary_key": False, "nullable": False},
        {"name": "total_amount", "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
        {"name": "status",       "data_type": "VARCHAR(50)",  "primary_key": False, "nullable": False},
    ]
}

legacy_table = {
    "name": "invoices",
    "columns": [
        {"name": "id",          "data_type": "BIGSERIAL",   "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",      "primary_key": False, "nullable": False},
        {"name": "creation",    "data_type": "TIMESTAMP",   "primary_key": False, "nullable": True},
        {"name": "modified",    "data_type": "TIMESTAMP",   "primary_key": False, "nullable": True},
        {"name": "modified_by", "data_type": "VARCHAR(140)","primary_key": False, "nullable": True},
    ]
}

PATTERNS = {
    "audit_columns": {
        "columns": [
            {"name": "created_at", "data_type": "TIMESTAMP",    "nullable": False, "default_value": "NOW()"},
            {"name": "updated_at", "data_type": "TIMESTAMP",    "nullable": True},
            {"name": "created_by", "data_type": "VARCHAR(140)", "nullable": True},
            {"name": "updated_by", "data_type": "VARCHAR(140)", "nullable": True},
        ],
        "semantic_equivalents": {
            "created_at": ["creation", "date_created", "created_date"],
            "updated_at": ["modified", "last_modified", "updated_date"],
            "created_by": ["owner", "creator"],
            "updated_by": ["modified_by", "last_modified_by"],
        }
    },
    "soft_delete": {
        "columns": [
            {"name": "is_deleted", "data_type": "BOOLEAN",      "nullable": False, "default_value": "false"},
            {"name": "deleted_at", "data_type": "TIMESTAMP",    "nullable": True},
            {"name": "deleted_by", "data_type": "VARCHAR(140)", "nullable": True},
        ],
        "semantic_equivalents": {
            "is_deleted": ["deleted", "is_removed"],
            "deleted_at": ["deletion_date"],
            "deleted_by": [],
        }
    },
    "status_workflow": {
        "columns": [
            {"name": "status",            "data_type": "VARCHAR(50)", "nullable": False, "default_value": "'draft'"},
            {"name": "status_changed_at", "data_type": "TIMESTAMP",  "nullable": True},
        ],
        "semantic_equivalents": {
            "status":            ["state", "workflow_state", "docstatus"],
            "status_changed_at": [],
        }
    },
}

def has_semantic_equivalent(existing_columns, pattern_col_name, equivalents):
    existing_set = set(existing_columns)
    
    # Check exact match first
    if pattern_col_name in existing_set:
        return pattern_col_name
    
    # Check semantic equivalents
    for equiv in equivalents.get(pattern_col_name, []):
        if equiv in existing_set:
            return equiv
    
    return None

def apply_pattern(table, pattern_name):
    result = copy.deepcopy(table)
    pattern = PATTERNS[pattern_name]
    existing = [c["name"] for c in result["columns"]]
    applied = []
    skipped = []

    for pat_col in pattern["columns"]:
        equiv = has_semantic_equivalent(
            existing,
            pat_col["name"],
            pattern["semantic_equivalents"]
        )

        if equiv:
            skipped.append(f"{pat_col['name']} (covered by '{equiv}')")
        else:
            result["columns"].append(pat_col)
            applied.append(pat_col["name"])
            existing.append(pat_col["name"])

    print(f"  Pattern '{pattern_name}' on '{table['name']}':")
    if applied:
        print(f"    Added:   {', '.join(applied)}")
    if skipped:
        print(f"    Skipped: {', '.join(skipped)}")

    return result


if __name__ == "__main__":

    print("=" * 50)
    print("Test 1: Clean table (no overlaps)")
    print("=" * 50)
    result1 = apply_pattern(orders_table, "audit_columns")
    result1 = apply_pattern(result1,      "soft_delete")
    result1 = apply_pattern(result1,      "status_workflow")
    print(f"\n  Final columns:")
    for col in result1["columns"]:
        print(f"    → {col['name']:20} {col['data_type']}")

    print()
    print("=" * 50)
    print("Test 2: Legacy table (ERPNext style columns)")
    print("=" * 50)
    result2 = apply_pattern(legacy_table, "audit_columns")
    result2 = apply_pattern(result2,      "soft_delete")
    print(f"\n  Final columns:")
    for col in result2["columns"]:
        print(f"    → {col['name']:20} {col['data_type']}")

    print()
    for t in [result1, result2]:
        names = [c["name"] for c in t["columns"]]
        assert len(names) == len(set(names)), f"Duplicates found in {t['name']}!"
    print("  No duplicate columns in any table!")
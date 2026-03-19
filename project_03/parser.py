import json

ERPNEXT_TO_POSTGRES = {
    "Data": "VARCHAR(140)", "Link": "VARCHAR(140)", "Select": "VARCHAR(140)",
    "Int": "INTEGER", "Float": "DOUBLE PRECISION", "Currency": "DECIMAL(18,6)",
    "Percent": "DECIMAL(5,2)", "Check": "BOOLEAN", "Date": "DATE",
    "Datetime": "TIMESTAMP", "Time": "TIME", "Text": "TEXT",
    "Long Text": "TEXT", "Small Text": "VARCHAR(140)", "Text Editor": "TEXT",
    "Code": "TEXT", "HTML Editor": "TEXT", "Password": "VARCHAR(140)",
    "Attach": "VARCHAR(280)", "Attach Image": "VARCHAR(280)",
    "Color": "VARCHAR(7)", "JSON": "JSONB", "Rating": "DECIMAL(3,2)",
    "Barcode": "VARCHAR(140)", "Geolocation": "TEXT", "Duration": "INTERVAL",
}

SKIP_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "Table", "Table MultiSelect"}

FRAMEWORK_COLUMNS = {
    "naming_series", "amended_from", "docstatus", "parent",
    "parenttype", "parentfield", "idx", "owner"
}

def parse_doctype(filepath: str, known_doctypes: set = None) -> dict:
    with open(filepath) as f:
        doctype = json.load(f)

    if known_doctypes is None:
        known_doctypes = set()

    table_name = doctype["name"].lower().replace(" ", "_")
    module = doctype.get("module", "unknown").lower()

    columns = []
    references = []

    for field in doctype["fields"]:
        fieldtype = field.get("fieldtype", "")
        fieldname = field.get("fieldname", "")

        # Skip layout fields
        if fieldtype in SKIP_FIELDTYPES:
            continue

        # Skip framework columns
        if fieldname in FRAMEWORK_COLUMNS:
            continue

        pg_type = ERPNEXT_TO_POSTGRES.get(fieldtype)
        if pg_type is None:
            continue

        column = {
            "name": fieldname,
            "data_type": pg_type,
            "nullable": field.get("reqd", 0) != 1,
            "primary_key": fieldname == "name",
        }

        if fieldtype == "Link":
            target = field.get("options", "").lower().replace(" ", "_")
            is_required = field.get("reqd", 0) == 1
            target_exists = target in known_doctypes or len(known_doctypes) == 0

            if is_required and target_exists:
                ref_type = "candidate_enforced"
            else:
                ref_type = "logical"

            column["foreign_key"] = {
                "table": target,
                "column": "name",
                "ref_type": ref_type,
            }

            references.append({
                "from_column": fieldname,
                "to_table": target,
                "ref_type": ref_type,
                "required": is_required,
            })

        columns.append(column)

    # Detect patterns
    patterns = []
    col_names = {c["name"] for c in columns}
    all_field_names = {f["fieldname"] for f in doctype["fields"]}

    audit_matches = col_names & {"creation", "modified", "modified_by", "created_at", "updated_at", "created_by"}
    if len(audit_matches) >= 2:
        patterns.append({
            "pattern_id": "audit_columns",
            "confidence": round(len(audit_matches) / 4, 2)
        })

    if "docstatus" in all_field_names:
        patterns.append({
            "pattern_id": "status_workflow",
            "confidence": 0.9
        })

    return {
        "name": table_name,
        "source": "erpnext",
        "module": module,
        "columns": columns,
        "references": references,
        "patterns_detected": patterns,
    }


if __name__ == "__main__":
    known = {"customer", "sales_invoice"}
    result = parse_doctype("sample_doctype.json", known)

    print(json.dumps(result, indent=2))

    col_names = [c["name"] for c in result["columns"]]

    # Assertions to verify correctness
    assert "naming_series" not in col_names, "Framework column leaked!"
    assert "amended_from" not in col_names, "Framework column leaked!"
    assert "parent" not in col_names, "Framework column leaked!"
    assert "section_break_1" not in col_names, "Layout field leaked!"
    assert result["columns"][0]["primary_key"], "name should be PK!"

    enforced = [r for r in result["references"] if r["ref_type"] == "candidate_enforced"]
    logical = [r for r in result["references"] if r["ref_type"] == "logical"]

    print(f"\n{len(result['columns'])} columns (framework excluded)")
    print(f"{len(enforced)} candidate enforced refs: {[r['to_table'] for r in enforced]}")
    print(f"{len(logical)} logical refs: {[r['to_table'] for r in logical]}")
    print(f"Patterns: {[p['pattern_id'] for p in result['patterns_detected']]}")
    print("\nAll assertions passed!")
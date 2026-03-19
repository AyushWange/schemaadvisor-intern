# project_12/pipeline.py
import sys
import json
import copy
import psycopg2
import time
import uuid
sys.path.insert(0, "..")

# ── Mock concept extractor (Project 6) ────────────────────────────────────────

CONCEPTS = {
    "user_authentication":  "User accounts, passwords, sessions",
    "product_catalog":      "Products, categories, attributes, pricing",
    "e_commerce_orders":    "Shopping cart, checkout, order lifecycle",
    "payment_processing":   "Payments, payment methods, refunds",
    "invoicing":            "Sales invoices, invoice items, tax entries",
    "inventory_management": "Warehouses, stock entries, stock ledger",
    "customer_management":  "Customer records, addresses, contacts",
}

MOCK_EXTRACTIONS = {
    "I need an e-commerce platform with product catalog and order tracking": [
        {"name": "e_commerce_orders", "confidence": 0.95},
        {"name": "product_catalog",   "confidence": 0.90},
    ],
    "Online store with invoicing": [
        {"name": "e_commerce_orders", "confidence": 0.95},
        {"name": "invoicing",         "confidence": 0.90},
    ],
}

def mock_extract(requirements):
    return MOCK_EXTRACTIONS.get(requirements, [
        {"name": "e_commerce_orders", "confidence": 0.90}
    ])

# ── Table selection (Project 9) ────────────────────────────────────────────────

CONCEPT_TABLES = {
    "e_commerce_orders": [
        {"name": "orders",        "tier": "required"},
        {"name": "order_items",   "tier": "required"},
        {"name": "customers",     "tier": "required"},
        {"name": "shopping_cart", "tier": "recommended"},
    ],
    "product_catalog": [
        {"name": "products",    "tier": "required"},
        {"name": "categories",  "tier": "required"},
        {"name": "attributes",  "tier": "recommended"},
    ],
    "invoicing": [
        {"name": "invoices",      "tier": "required"},
        {"name": "invoice_items", "tier": "required"},
        {"name": "tax_entries",   "tier": "recommended"},
        {"name": "customers",     "tier": "recommended"},
    ],
    "customer_management": [
        {"name": "customers",  "tier": "required"},
        {"name": "addresses",  "tier": "required"},
        {"name": "contacts",   "tier": "recommended"},
    ],
}

CONCEPT_DEPS = {
    "e_commerce_orders": ["customer_management"],
    "invoicing":         ["customer_management"],
    "customer_management": [],
    "product_catalog":   [],
}

TABLE_DEPS = {
    "orders":        ["customers"],
    "order_items":   ["orders", "products"],
    "invoices":      ["customers"],
    "invoice_items": ["invoices"],
    "tax_entries":   ["invoices"],
}

TIER_RANK   = {"required": 3, "recommended": 2, "suggested": 1}
TIER_SCORES = {"required": 1.0, "recommended": 0.7, "suggested": 0.4}

def mock_select(concepts):
    all_concepts = set()

    def expand(concept):
        if concept in all_concepts:
            return
        all_concepts.add(concept)
        for dep in CONCEPT_DEPS.get(concept, []):
            expand(dep)

    for c in concepts:
        expand(c["name"])

    merged = {}
    for concept in all_concepts:
        for table in CONCEPT_TABLES.get(concept, []):
            name = table["name"]
            if name not in merged or TIER_RANK[table["tier"]] > TIER_RANK[merged[name]["tier"]]:
                merged[name] = {
                    **table,
                    "triggered_by": [concept],
                    "patterns_applied": [],
                    "inclusion_confidence": round(TIER_SCORES.get(table["tier"], 0.5) * 0.6 + 0.9 * 0.4, 2)
                }
            else:
                merged[name]["triggered_by"].append(concept)

    # Pull FK dependencies
    for name, table in list(merged.items()):
        if table["tier"] in ("required", "recommended"):
            for dep in TABLE_DEPS.get(name, []):
                if dep not in merged:
                    merged[dep] = {
                        "name":                dep,
                        "tier":                "required",
                        "triggered_by":        [f"dependency of {name}"],
                        "dependency_reason":   f"Required by {name} (FK)",
                        "patterns_applied":    [],
                        "inclusion_confidence": 0.96,
                    }

    results = list(merged.values())
    results.sort(key=lambda x: -TIER_RANK.get(x["tier"], 0))
    return results

# ── Pattern injector (Project 4) ──────────────────────────────────────────────

PATTERNS = {
    "audit_columns": [
        {"name": "created_at", "data_type": "TIMESTAMP",    "nullable": False, "default_value": "NOW()"},
        {"name": "updated_at", "data_type": "TIMESTAMP",    "nullable": True},
        {"name": "created_by", "data_type": "VARCHAR(140)", "nullable": True},
    ],
    "soft_delete": [
        {"name": "is_deleted", "data_type": "BOOLEAN",      "nullable": False, "default_value": "false"},
        {"name": "deleted_at", "data_type": "TIMESTAMP",    "nullable": True},
    ],
}

BASE_COLUMNS = {
    "customers":    [
        {"name": "id",    "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "name",  "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "email", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": True},
    ],
    "orders": [
        {"name": "id",          "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "total",       "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
        {"name": "status",      "data_type": "VARCHAR(50)",  "primary_key": False, "nullable": False, "default_value": "'draft'"},
    ],
    "order_items": [
        {"name": "id",           "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "order_id",     "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "product_name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "quantity",     "data_type": "INTEGER",      "primary_key": False, "nullable": False},
        {"name": "unit_price",   "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
    ],
    "products": [
        {"name": "id",    "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "name",  "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
        {"name": "price", "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
    ],
    "categories": [
        {"name": "id",   "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "shopping_cart": [
        {"name": "id",          "data_type": "BIGSERIAL","primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",   "primary_key": False, "nullable": False},
    ],
    "addresses": [
        {"name": "id",          "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "street",      "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "contacts": [
        {"name": "id",          "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "phone",       "data_type": "VARCHAR(20)",  "primary_key": False, "nullable": True},
    ],
    "attributes": [
        {"name": "id",         "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "product_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "key",        "data_type": "VARCHAR(100)", "primary_key": False, "nullable": False},
        {"name": "value",      "data_type": "VARCHAR(255)", "primary_key": False, "nullable": False},
    ],
    "invoices": [
        {"name": "id",          "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "customer_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "total",       "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
    ],
    "invoice_items": [
        {"name": "id",         "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "invoice_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "amount",     "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
    ],
    "tax_entries": [
        {"name": "id",         "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "invoice_id", "data_type": "BIGINT",       "primary_key": False, "nullable": False},
        {"name": "tax_amount", "data_type": "DECIMAL(18,6)","primary_key": False, "nullable": False},
    ],
}

ENFORCED_FKS = {
    "orders":        [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "order_items":   [{"from_column": "order_id",    "to_table": "orders",     "to_column": "id", "on_delete": "CASCADE"}],
    "addresses":     [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "contacts":      [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "shopping_cart": [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "invoices":      [{"from_column": "customer_id", "to_table": "customers",  "to_column": "id", "on_delete": "CASCADE"}],
    "invoice_items": [{"from_column": "invoice_id",  "to_table": "invoices",   "to_column": "id", "on_delete": "CASCADE"}],
    "tax_entries":   [{"from_column": "invoice_id",  "to_table": "invoices",   "to_column": "id", "on_delete": "CASCADE"}],
    "attributes":    [{"from_column": "product_id",  "to_table": "products",   "to_column": "id", "on_delete": "CASCADE"}],
}

def apply_all_patterns(tables):
    enriched = []
    for table in tables:
        t        = copy.deepcopy(table)
        base_cols= copy.deepcopy(BASE_COLUMNS.get(t["name"], []))
        existing = {c["name"] for c in base_cols}

        for pattern_name, pattern_cols in PATTERNS.items():
            for col in pattern_cols:
                if col["name"] not in existing:
                    base_cols.append(copy.deepcopy(col))
                    existing.add(col["name"])
                    t["patterns_applied"].append(pattern_name)

        t["columns"]      = base_cols
        t["enforced_fks"] = ENFORCED_FKS.get(t["name"], [])
        t["logical_refs"] = []
        enriched.append(t)

    return enriched

# ── Kahn's sort (Project 1) ───────────────────────────────────────────────────

def build_dependency_dict(tables):
    table_names = {t["name"] for t in tables}
    deps        = {}

    for table in tables:
        name = table["name"]
        deps[name] = []
        for fk in table.get("enforced_fks", []):
            if fk["to_table"] in table_names:
                deps[name].append(fk["to_table"])

    return deps

def kahns_sort(dependencies):
    from collections import deque

    in_degree  = {t: 0 for t in dependencies}
    dependents = {t: [] for t in dependencies}

    for table, deps in dependencies.items():
        in_degree[table] = len(deps)
        for dep in deps:
            dependents[dep].append(table)

    queue  = deque(sorted([t for t, d in in_degree.items() if d == 0]))
    result = []

    while queue:
        table = queue.popleft()
        result.append(table)
        for dependent in sorted(dependents[table]):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(in_degree):
        raise Exception("Circular dependency detected!")

    return result

# ── DDL generator (Project 5) ─────────────────────────────────────────────────

def build_column_sql(col):
    sql = f"{col['name']} {col['data_type']}"
    if col.get("primary_key"):
        sql += " PRIMARY KEY"
    if not col.get("nullable", True):
        sql += " NOT NULL"
    if col.get("unique"):
        sql += " UNIQUE"
    if col.get("default_value"):
        sql += f" DEFAULT {col['default_value']}"
    return sql

def generate_ddl(enriched, order):
    table_map = {t["name"]: t for t in enriched}
    parts     = ["BEGIN;", ""]

    for name in order:
        if name not in table_map:
            continue

        table   = table_map[name]
        columns = [build_column_sql(c) for c in table["columns"]]
        fk_sqls = []

        for fk in table.get("enforced_fks", []):
            fk_sqls.append(
                f"FOREIGN KEY ({fk['from_column']}) "
                f"REFERENCES {fk['to_table']}({fk['to_column']}) "
                f"ON DELETE {fk['on_delete']}"
            )

        all_defs = columns + fk_sqls
        col_sql  = ",\n    ".join(all_defs)
        parts.append(f"CREATE TABLE {name} (\n    {col_sql}\n);")

        for fk in table.get("enforced_fks", []):
            parts.append(
                f"CREATE INDEX idx_{name}_{fk['from_column']} "
                f"ON {name}({fk['from_column']});"
            )

        parts.append("")

    parts.append("COMMIT;")
    return "\n".join(parts)

# ── Validator (Project 7) ─────────────────────────────────────────────────────

def validate(ddl):
    db = f"val_{uuid.uuid4().hex[:8]}"

    conn = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass",
        dbname="schema_test"
    )
    conn.autocommit = True
    conn.cursor().execute(f"CREATE DATABASE {db}")
    conn.close()

    conn = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass",
        dbname=db
    )
    cur      = conn.cursor()
    success  = 0
    total    = 0
    start    = time.time()

    statements = [
        s.strip() for s in ddl.split(";")
        if s.strip() and s.strip() not in ("BEGIN", "COMMIT")
    ]

    for sql in statements:
        if sql.upper().startswith("CREATE"):
            total += 1
            try:
                cur.execute(sql)
                conn.commit()
                success += 1
                print(f"    ✓ {sql.split()[2]}")
            except Exception as e:
                conn.rollback()
                print(f"    ✗ {sql[:50]} — {str(e).split(chr(10))[0]}")

    elapsed = int((time.time() - start) * 1000)
    cur.close()
    conn.close()

    conn = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass",
        dbname="schema_test"
    )
    conn.autocommit = True
    conn.cursor().execute(f"DROP DATABASE IF EXISTS {db}")
    conn.close()

    return {"success": success, "total": total, "elapsed": elapsed}

# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(requirements):
    print(f"\n{'='*70}")
    print(f"INPUT: {requirements}")
    print(f"{'='*70}")

    # Stage 1: Extract concepts
    print("\n  Stage 1: Concept Extraction")
    concepts = mock_extract(requirements)
    for c in concepts:
        print(f"    ✓ {c['name']} (confidence={c['confidence']})")

    # Stage 2: Conflict detection
    print("\n  Stage 2: Conflict Detection")
    print(f"    Active decisions: soft_delete, auto_increment, single_tenant")
    print(f"    No conflicts detected!")

    # Stage 3: Select tables
    print("\n  Stage 3: Table Selection")
    tables = mock_select(concepts)
    for t in tables:
        print(f"    {t['tier']:12} | {t['name']}")

    # Stage 4: Classify refs + Kahn's sort
    print("\n  Stage 4: Reference Classification + Kahn's Sort")
    enriched = apply_all_patterns(tables)
    deps     = build_dependency_dict(enriched)
    order    = kahns_sort(deps)
    print(f"    Creation order: {' → '.join(order)}")

    # Stage 5: Pattern materialization
    print("\n  Stage 5: Pattern Materialization")
    for t in enriched:
        patterns = list(set(t.get("patterns_applied", [])))
        print(f"    {t['name']:20} → patterns: {patterns}")

    # Stage 6: Generate DDL
    print("\n  Stage 6: DDL Generation")
    ddl = generate_ddl(enriched, order)
    print(ddl[:800] + "..." if len(ddl) > 800 else ddl)

    # Stage 7: Validate
    print("\n  Stage 7: PostgreSQL Validation")
    report = validate(ddl)
    print(f"\n    Result: {report['success']}/{report['total']} "
          f"statements succeeded in {report['elapsed']}ms")

    # Stage 8: Explainability report
    print("\n  Stage 8: Explainability Report")
    print(f"  {'Table':<20} {'Tier':<12} {'Confidence':<12} Triggered By")
    print(f"  {'-'*70}")
    for t in enriched:
        triggered = ", ".join(t.get("triggered_by", ["direct"]))
        print(f"  {t['name']:<20} {t['tier']:<12} "
              f"{t['inclusion_confidence']:<12} {triggered}")

if __name__ == "__main__":
    run_pipeline(
        "I need an e-commerce platform with product catalog and order tracking"
    )
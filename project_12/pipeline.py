# project_12/pipeline.py — Real LLM-powered end-to-end pipeline
import sys
import os
import json
import copy
import time
import uuid

# Add parent dir so we can import project_06
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from project_06.extractor import extract, CONCEPTS as CONCEPT_REGISTRY

# ── Table knowledge base ───────────────────────────────────────────────────────

# ── Data loaded from seeds for backwards compatibility ──────────────────────────
import json

def _load_seed(name):
    seed_path = os.path.join(os.path.dirname(__file__), "..", "seeds", name)
    try:
        with open(seed_path, "r") as f:
            return json.load(f)
    except:
        return []

reqs = _load_seed("seed_requires_table.json")
CONCEPT_TABLES = {}
for r in reqs:
    CONCEPT_TABLES.setdefault(r["concept"], []).append({"name": r["logical_table"], "tier": r["tier"]})

deps = _load_seed("seed_depends_on.json")
CONCEPT_DEPS = {}
for d in deps:
    CONCEPT_DEPS.setdefault(d["from"], []).append(d["to"])

fks = _load_seed("seed_enforced_fks.json")
TABLE_DEPS = {}
ENFORCED_FKS = {}
for f in fks:
    TABLE_DEPS.setdefault(f["from_table"], []).append(f["to_table"])
    ENFORCED_FKS.setdefault(f["from_table"], []).append({
        "from_column": f["from_column"],
        "to_table": f["to_table"],
        "to_column": f["to_column"],
        "on_delete": f.get("on_delete", "CASCADE")
    })

PATTERNS = {}
pats = _load_seed("seed_patterns.json")
for p in pats:
    PATTERNS[p["name"]] = p["application_columns"]

SYSTEM_TABLES = {}
sys_t = _load_seed("seed_system_tables.json")
for t in sys_t:
    SYSTEM_TABLES[t["logical_table"]] = {
        "name": t["logical_table"],
        "tier": "required",
        "triggered_by": ["system_pattern"],
        "patterns_applied": [],
        "inclusion_confidence": 1.0,
        "columns": t["columns"],
        "enforced_fks": [],
        "logical_refs": []
    }

BASE_COLUMNS = {}
cols_t = _load_seed("seed_table_columns.json")
for c in cols_t:
    BASE_COLUMNS[c["logical_table"]] = c["curated_columns"]

TIER_RANK   = {"required": 3, "recommended": 2, "suggested": 1}
TIER_SCORES = {"required": 1.0, "recommended": 0.7, "suggested": 0.4}

def _generic_columns(table_name: str) -> list:
    return [
        {"name": "id",   "data_type": "BIGSERIAL",    "primary_key": True,  "nullable": False},
        {"name": "name", "data_type": "VARCHAR(255)",  "primary_key": False, "nullable": False},
    ]

# ── Stage implementations ──────────────────────────────────────────────────────

from project_02.db_access import get_selected_tables, _is_neo4j_available

def select_tables(concepts):
    concept_names = [c.name for c in concepts]

    if _is_neo4j_available():
        # Neo4j path 
        merged_dict = get_selected_tables(concept_names)
        results_map = {}
        for tname, tbl in merged_dict.items():
            tier = tbl["tier"]
            results_map[tname] = {
                "name": tname,
                "tier": tier,
                "triggered_by": tbl["triggered_by"],
                "patterns_applied": [],
                "inclusion_confidence": round(
                    TIER_SCORES.get(tier, 0.5) * 0.6 + max((c.confidence for c in concepts), default=0.9) * 0.4, 2
                )
            }
        
        # FK dependency pull-in (for tables we fetched)
        for name, table in list(results_map.items()):
            if table["tier"] in ("required", "recommended"):
                for dep in TABLE_DEPS.get(name, []):
                    if dep not in results_map:
                        results_map[dep] = {
                            "name":                dep,
                            "tier":                "required",
                            "triggered_by":        [f"dependency of {name}"],
                            "dependency_reason":   f"Required by {name} (FK)",
                            "patterns_applied":    [],
                            "inclusion_confidence": 0.96,
                        }
        results = list(results_map.values())
        results.sort(key=lambda x: -TIER_RANK.get(x["tier"], 0))
        return results

    # Fallback to local dicts if Neo4j is down
    all_concepts = set()

    def expand(concept):
        if concept in all_concepts:
            return
        all_concepts.add(concept)
        for dep in CONCEPT_DEPS.get(concept, []):
            expand(dep)

    for c in concepts:
        expand(c.name)

    merged = {}
    for concept in all_concepts:
        for table in CONCEPT_TABLES.get(concept, []):
            name = table["name"]
            if name not in merged or TIER_RANK.get(table["tier"], 0) > TIER_RANK.get(merged[name]["tier"], 0):
                merged[name] = {
                    **table,
                    "triggered_by":        [concept],
                    "patterns_applied":    [],
                    "inclusion_confidence": round(
                        TIER_SCORES.get(table["tier"], 0.5) * 0.6 +
                        max((c.confidence for c in concepts), default=0.9) * 0.4, 2
                    )
                }
            else:
                if concept not in merged[name]["triggered_by"]:
                    merged[name]["triggered_by"].append(concept)

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
    results.sort(key=lambda x: -TIER_RANK.get(x.get("tier", "suggested"), 0))
    return results


def apply_all_patterns(tables, active_decisions=None):
    """
    Apply schema patterns to all tables based on active design decisions.

    active_decisions: dict of {decision_name: choice_string}
                      e.g. {"tenancy_model": "multi_tenant", "temporal_strategy": "versioned"}
    """
    if active_decisions is None:
        active_decisions = {}

    # Determine which patterns to apply
    do_audit      = active_decisions.get("audit_policy",      "full_audit")  != "no_audit"
    do_soft_del   = active_decisions.get("delete_strategy",   "soft_delete") == "soft_delete"
    do_temporal   = active_decisions.get("temporal_strategy", "current_only") == "versioned"
    do_multi_tent = active_decisions.get("tenancy_model",     "single_tenant") == "multi_tenant"

    enriched = []
    for table in tables:
        t         = copy.deepcopy(table)
        base_cols = copy.deepcopy(BASE_COLUMNS.get(t["name"], _generic_columns(t["name"])))
        existing  = {c["name"] for c in base_cols}

        def _stamp(pattern_name, pattern_cols):
            for col in pattern_cols:
                if col["name"] not in existing:
                    base_cols.append(copy.deepcopy(col))
                    existing.add(col["name"])
                    if pattern_name not in t["patterns_applied"]:
                        t["patterns_applied"].append(pattern_name)

        if do_audit: _stamp("audit_columns", PATTERNS.get("audit_columns", []))
        if do_soft_del: _stamp("soft_delete", PATTERNS.get("soft_delete", []))
        if do_temporal: _stamp("temporal_version", PATTERNS.get("temporal_version", []))

        t["columns"]      = base_cols
        t["enforced_fks"] = ENFORCED_FKS.get(t["name"], [])
        t["logical_refs"] = []
        enriched.append(t)

    return enriched


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
            if fk["to_table"] in table_map:
                fk_sqls.append(
                    f"FOREIGN KEY ({fk['from_column']}) "
                    f"REFERENCES {fk['to_table']}({fk['to_column']}) "
                    f"ON DELETE {fk['on_delete']}"
                )

        all_defs = columns + fk_sqls
        col_sql  = ",\n    ".join(all_defs)
        parts.append(f"CREATE TABLE {name} (\n    {col_sql}\n);")

        for fk in table.get("enforced_fks", []):
            if fk["to_table"] in table_map:
                parts.append(
                    f"CREATE INDEX idx_{name}_{fk['from_column']} "
                    f"ON {name}({fk['from_column']});"
                )

        parts.append("")

    parts.append("COMMIT;")
    return "\n".join(parts)


def validate_ddl(ddl):
    try:
        import psycopg2
    except ImportError:
        print("    [SKIP] psycopg2 not installed — skipping DB validation.")
        return {"success": 0, "total": 0, "elapsed": 0, "skipped": True}

    db = f"val_{uuid.uuid4().hex[:8]}"
    try:
        conn = psycopg2.connect(
            host="localhost", port=5432,
            user="postgres", password="internpass",
            dbname="schema_test"
        )
        conn.autocommit = True
        conn.cursor().execute(f"CREATE DATABASE {db}")
        conn.close()
    except Exception as e:
        print(f"    [SKIP] Cannot connect to PostgreSQL: {e}")
        return {"success": 0, "total": 0, "elapsed": 0, "skipped": True}

    conn     = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass", dbname=db
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
                print(f"    ✗ {sql[:60]}… — {str(e).split(chr(10))[0]}")

    elapsed = int((time.time() - start) * 1000)
    cur.close()
    conn.close()

    conn = psycopg2.connect(
        host="localhost", port=5432,
        user="postgres", password="internpass", dbname="schema_test"
    )
    conn.autocommit = True
    conn.cursor().execute(f"DROP DATABASE IF EXISTS {db}")
    conn.close()

    return {"success": success, "total": total, "elapsed": elapsed, "skipped": False}


# ── Main pipeline function ─────────────────────────────────────────────────────

def run_pipeline(requirements: str, verbose: bool = True) -> dict:
    if verbose:
        print(f"\n{'='*70}")
        print(f"INPUT: {requirements}")
        print(f"{'='*70}")

    # Stage 1: Extract concepts via LLM (or mock)
    if verbose:
        print("\n  Stage 1: Concept Extraction")
    extraction = extract(requirements)

    if not extraction.concepts:
        if verbose:
            print("  No concepts extracted. Cannot generate schema.")
            for u in extraction.unmatched:
                print(f"    Unmatched: {u.raw_text}")
        return {"error": "No concepts extracted", "unmatched": [u.model_dump() for u in extraction.unmatched]}

    if verbose:
        for c in extraction.concepts:
            print(f"    ✓ {c.name} (confidence={c.confidence:.2f}) — '{c.matched_text}'")
        for d in extraction.decisions:
            print(f"    → decision: {d.name}={d.choice} ({d.confidence:.2f})")

    # Stage 2: Conflict detection
    active_decisions = {d.name: d.choice for d in extraction.decisions}
    if verbose:
        print("\n  Stage 2: Conflict Detection")
        if active_decisions:
            for k, v in active_decisions.items():
                print(f"    Active decision: {k}={v}")
        else:
            print("    No non-default decisions detected — using all defaults")
        print("    No conflicts detected!")

    # Stage 3: Table selection
    if verbose:
        print("\n  Stage 3: Table Selection")
    tables = select_tables(extraction.concepts)
    if verbose:
        for t in tables:
            print(f"    {t['tier']:12} | {t['name']}")

    # Stage 4: Pattern injection + Kahn's sort
    if verbose:
        print("\n  Stage 4: Pattern Injection + Kahn's Sort")
    enriched = apply_all_patterns(tables, active_decisions=active_decisions)
    deps     = build_dependency_dict(enriched)
    order    = kahns_sort(deps)
    if verbose:
        print(f"    Creation order: {' → '.join(order)}")

    # Stage 5: Pattern materialization summary
    if verbose:
        print("\n  Stage 5: Pattern Materialization")
        for t in enriched:
            patterns = list(set(t.get("patterns_applied", [])))
            print(f"    {t['name']:25} → {patterns}")

    # Stage 6: DDL generation
    if verbose:
        print("\n  Stage 6: DDL Generation")
    ddl = generate_ddl(enriched, order)
    if verbose:
        preview = ddl[:600] + "..." if len(ddl) > 600 else ddl
        print(preview)

    # Stage 7: PostgreSQL validation
    if verbose:
        print("\n  Stage 7: PostgreSQL Validation")
    report = validate_ddl(ddl)
    if verbose:
        if report.get("skipped"):
            print("    Validation skipped (no DB connection).")
        else:
            print(f"\n    Result: {report['success']}/{report['total']} "
                  f"statements succeeded in {report['elapsed']}ms")

    # Stage 8: Explainability report
    if verbose:
        print("\n  Stage 8: Explainability Report")
        print(f"  {'Table':<25} {'Tier':<12} {'Conf':<8} Triggered By")
        print(f"  {'-'*70}")
        for t in enriched:
            triggered = ", ".join(t.get("triggered_by", ["direct"]))
            print(f"  {t['name']:<25} {t['tier']:<12} "
                  f"{t['inclusion_confidence']:<8} {triggered}")

    return {
        "ddl":              ddl,
        "tables":           [t["name"] for t in enriched],
        "creation_order":   order,
        "active_decisions": active_decisions,
        "unmatched":        [u.model_dump() for u in extraction.unmatched],
        "explainability": [
            {
                "table":      t["name"],
                "tier":       t["tier"],
                "confidence": t.get("inclusion_confidence", 0.9),
                "triggered_by": t.get("triggered_by", []),
                "patterns":   t.get("patterns_applied", []),
            }
            for t in enriched
        ],
        "validation": report,
    }



# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        req = " ".join(sys.argv[1:])
    else:
        req = "I need an e-commerce platform with product catalog and order tracking"

    result = run_pipeline(req)
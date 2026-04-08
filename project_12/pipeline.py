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
from project_08.table_selector import select_tables as _select_tables_raw
from project_10.conflicts import build_active_decisions, detect_conflicts

def select_tables(concepts):
    """Wrapper that accepts ExtractedConcept objects and delegates to table_selector."""
    concept_names = [c.name for c in concepts]
    max_conf = max((c.confidence for c in concepts), default=0.9)
    return _select_tables_raw(concept_names, concept_confidence=max_conf)



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

def run_pipeline(requirements: str, verbose: bool = True, user_overrides: dict = None) -> dict:
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
    if verbose:
        print("\n  Stage 2: Conflict Detection")

    # Build overrides dict with confidence scores for the critical-decision gate
    overrides = {}
    for d in extraction.decisions:
        overrides[d.name] = d.choice
        overrides[f"{d.name}_confidence"] = d.confidence

    # Apply user-confirmed overrides (from decision confirmation flow)
    if user_overrides:
        if verbose:
            print("    Applying user-confirmed decision overrides...")
        for decision_name, decision_info in user_overrides.items():
            if isinstance(decision_info, dict) and "choice" in decision_info:
                choice = decision_info.get("choice")
                confidence = decision_info.get("confidence", 0.95)
                overrides[decision_name] = choice
                overrides[f"{decision_name}_confidence"] = confidence
                if verbose:
                    print(f"      {decision_name}={choice} (confidence={confidence:.2f})")

    # build_active_decisions applies defaults + critical halt gate
    active_map   = build_active_decisions(overrides)
    # Flatten to {decision_name: choice} for downstream stages (non-halted only)
    active_decisions = {
        k: v["choice"]
        for k, v in active_map.items()
        if v.get("source") != "halted"
    }

    if verbose:
        if active_decisions:
            for k, v in active_decisions.items():
                src = active_map[k].get("source", "")
                if src != "default":
                    print(f"    Active decision: {k}={v} ({src})")
        else:
            print("    No non-default decisions detected — using all defaults")

        halted = [k for k, v in active_map.items() if v.get("source") == "halted"]
        for h in halted:
            print(f"    ⚠ HALTED: {h}={active_map[h]['choice']} "
                  f"(confidence {active_map[h]['confidence']:.2f} < 0.85, "
                  f"critical decision — reverting to default)")

    # Run conflict detection against the resolved active decisions
    conflicts = detect_conflicts(active_map)
    warnings  = []
    hard_blocks = []

    for conflict in conflicts:
        if conflict["category"] == "hard_incompatibility":
            hard_blocks.append(conflict)
            if verbose:
                print(f"\n    ✗ HARD INCOMPATIBILITY: "
                      f"{conflict['decision_a']}={conflict['choice_a']} "
                      f"× {conflict['decision_b']}={conflict['choice_b']}")
                print(f"      Reason:     {conflict['reason']}")
                print(f"      Resolution: {conflict['resolution']}")
        else:  # preference_tradeoff
            warnings.append(conflict)
            if verbose:
                print(f"\n    ⚠ WARNING: "
                      f"{conflict['decision_a']}={conflict['choice_a']} "
                      f"× {conflict['decision_b']}={conflict['choice_b']}")
                print(f"      Reason:     {conflict['reason']}")
                print(f"      Resolution: {conflict['resolution']}")

    # Hard incompatibilities block the pipeline entirely
    if hard_blocks:
        if verbose:
            print("\n    Pipeline halted — resolve hard incompatibilities before continuing.")
        return {
            "error":    "Hard incompatibility detected",
            "conflicts": hard_blocks,
            "unmatched": [u.model_dump() for u in extraction.unmatched],
        }

    if verbose and not conflicts:
        print("    No conflicts detected!")
    elif verbose and warnings:
        print("\n    Continuing with warnings...")

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
        "conflicts":        warnings,   # preference_tradeoff warnings surfaced to frontend
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
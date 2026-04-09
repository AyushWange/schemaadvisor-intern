# project_08/table_selector.py — Table Selection Algorithm
# The "brain" of SchemaAdvisor: concept expansion → table selection →
# FK dependency resolution → suggested-table pruning → explainability.
#
# Usage:
#     from project_08.table_selector import select_tables
#     tables = select_tables(["e_commerce_orders", "invoicing"])

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Neo4j access (optional) ───────────────────────────────────────────────────
from project_02.db_access import _is_neo4j_available

_NEO4J_URI  = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
_NEO4J_USER = os.environ.get("NEO4J_USER",     "neo4j")
_NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", "internpassword")

TIER_RANK   = {"required": 3, "recommended": 2, "suggested": 1}
TIER_SCORES = {"required": 1.0, "recommended": 0.7, "suggested": 0.4}

# ── Seed-based fallback data ──────────────────────────────────────────────────
SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seeds")

def _load_seed(name):
    try:
        with open(os.path.join(SEED_DIR, name), "r") as f:
            return json.load(f)
    except Exception:
        return []

def _build_local_data():
    """Build in-memory lookup dicts from seed JSON files."""
    reqs = _load_seed("seed_requires_table.json")
    concept_tables = {}
    for r in reqs:
        concept_tables.setdefault(r["concept"], []).append(
            {"name": r["logical_table"], "tier": r["tier"]}
        )

    deps = _load_seed("seed_depends_on.json")
    concept_deps = {}
    for d in deps:
        concept_deps.setdefault(d["from"], []).append(d["to"])

    fks = _load_seed("seed_enforced_fks.json")
    table_deps = {}
    for f in fks:
        table_deps.setdefault(f["from_table"], []).append(f["to_table"])

    return concept_tables, concept_deps, table_deps


# Cache the data so we don't re-read on every call
_LOCAL_CONCEPT_TABLES, _LOCAL_CONCEPT_DEPS, _LOCAL_TABLE_DEPS = _build_local_data()

# ── Co-occurrence scores for pruning ──────────────────────────────────────────
# These represent COMMONLY_PAIRED_WITH frequencies derived from how often
# TableTemplates appear together in the same source database.
# Key: (suggested_table, required_or_recommended_table) → frequency 0.0–1.0

COOCCURRENCE = {
    # wishlists frequently co-occur with orders/customers
    ("wishlists",      "orders"):    0.6,
    ("wishlists",      "customers"): 0.7,
    # gift_cards rarely co-occur
    ("gift_cards",     "orders"):    0.3,
    ("gift_cards",     "customers"): 0.2,
    # customer_notes strongly co-occur with customers
    ("customer_notes", "customers"): 0.8,
    # credit_notes often co-occur with invoices
    ("credit_notes",   "invoices"):  0.7,
    # milestones moderately co-occur with projects
    ("milestones",     "projects"):  0.6,
    ("milestones",     "tasks"):     0.5,
    # currency_ledger moderately co-occurs
    ("currency_ledger","currencies"):0.5,
    # permissions moderately co-occur with users/roles
    ("permissions",    "users"):     0.6,
    ("permissions",    "roles"):     0.7,
    # report_filters moderately co-occur with reports
    ("report_filters", "reports"):   0.6,
}


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — Concept Expansion
# ══════════════════════════════════════════════════════════════════════════════

def _expand_concepts_neo4j(concept_names):
    """Use Neo4j DEPENDS_ON traversal to expand the concept set."""
    from neo4j import GraphDatabase
    query = """
    UNWIND $concepts AS cname
    MATCH (dc:DomainConcept {name: cname})-[:DEPENDS_ON*0..]->(dep:DomainConcept)
    RETURN DISTINCT dep.name AS name
    """
    driver = GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASS))
    expanded = set()
    with driver.session() as session:
        for rec in session.run(query, concepts=list(concept_names)):
            expanded.add(rec["name"])
    driver.close()
    return expanded


def _expand_concepts_local(concept_names):
    """Use local seed_depends_on.json to expand the concept set."""
    all_concepts = set()

    def _expand(concept):
        if concept in all_concepts:
            return
        all_concepts.add(concept)
        for dep in _LOCAL_CONCEPT_DEPS.get(concept, []):
            _expand(dep)

    for c in concept_names:
        _expand(c)
    return all_concepts


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — Table Collection & Tier Merging
# ══════════════════════════════════════════════════════════════════════════════

def _collect_tables_neo4j(expanded_concepts):
    """Query Neo4j for REQUIRES_TABLE edges and merge by highest tier."""
    from neo4j import GraphDatabase
    query = """
    UNWIND $concepts AS cname
    MATCH (dc:DomainConcept {name: cname})-[r:REQUIRES_TABLE]->(lt:LogicalTable)
    RETURN lt.name AS table_name,
           r.tier  AS tier,
           dc.name AS concept
    """
    driver = GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASS))
    merged = {}
    with driver.session() as session:
        for rec in session.run(query, concepts=list(expanded_concepts)):
            name = rec["table_name"]
            tier = rec["tier"]
            concept = rec["concept"]
            if name not in merged or TIER_RANK.get(tier, 0) > TIER_RANK.get(merged[name]["tier"], 0):
                merged[name] = {
                    "name": name,
                    "tier": tier,
                    "triggered_by": [concept],
                }
            else:
                if concept not in merged[name]["triggered_by"]:
                    merged[name]["triggered_by"].append(concept)
    driver.close()
    return merged


def _collect_tables_local(expanded_concepts):
    """Use local seed data to collect tables and merge by highest tier."""
    merged = {}
    for concept in expanded_concepts:
        for table in _LOCAL_CONCEPT_TABLES.get(concept, []):
            name = table["name"]
            tier = table["tier"]
            if name not in merged or TIER_RANK.get(tier, 0) > TIER_RANK.get(merged[name]["tier"], 0):
                merged[name] = {
                    "name": name,
                    "tier": tier,
                    "triggered_by": [concept],
                }
            else:
                if concept not in merged[name]["triggered_by"]:
                    merged[name]["triggered_by"].append(concept)
    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — FK Dependency Resolution
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_fk_deps_neo4j(merged):
    """Traverse enforced REFERENCES edges in Neo4j to pull missing deps."""
    from neo4j import GraphDatabase
    table_names = list(merged.keys())
    if not table_names:
        return merged

    query = """
    UNWIND $tables AS tname
    MATCH (a:LogicalTable {name: tname})-[r:REFERENCES {ref_type: 'enforced'}]->(b:LogicalTable)
    RETURN DISTINCT a.name AS from_table, b.name AS to_table
    """
    driver = GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASS))
    with driver.session() as session:
        for rec in session.run(query, tables=table_names):
            dep = rec["to_table"]
            parent = rec["from_table"]
            if dep not in merged:
                merged[dep] = {
                    "name":              dep,
                    "tier":              "required",
                    "triggered_by":      [f"dependency of {parent}"],
                    "dependency_reason": f"Required by {parent} (FK)",
                }
    driver.close()
    return merged


def _resolve_fk_deps_local(merged):
    """Use local seed_enforced_fks.json to pull in missing FK dependencies."""
    for name, table in list(merged.items()):
        if table["tier"] in ("required", "recommended"):
            for dep in _LOCAL_TABLE_DEPS.get(name, []):
                if dep not in merged:
                    merged[dep] = {
                        "name":              dep,
                        "tier":              "required",
                        "triggered_by":      [f"dependency of {name}"],
                        "dependency_reason": f"Required by {name} (FK)",
                    }
    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — Suggested Table Pruning (COMMONLY_PAIRED_WITH < 0.5)
# ══════════════════════════════════════════════════════════════════════════════

def _prune_suggested(merged, threshold=0.5):
    """
    Remove 'suggested' tables whose COMMONLY_PAIRED_WITH frequency
    is below `threshold` relative to ALL required/recommended tables.
    """
    required_recommended = {
        n for n, t in merged.items()
        if t["tier"] in ("required", "recommended")
    }

    pruned = []
    for name, table in list(merged.items()):
        if table["tier"] == "suggested":
            max_freq = 0
            for rr in required_recommended:
                freq = COOCCURRENCE.get((name, rr),
                       COOCCURRENCE.get((rr, name), 0))
                max_freq = max(max_freq, freq)

            if max_freq < threshold:
                pruned.append(f"{name} (max_freq={max_freq})")
                del merged[name]

    if pruned:
        print(f"    Pruned suggested tables: {pruned}")
    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 5 — Explainability (confidence scoring)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_explainability(merged, concept_confidence=0.9):
    """
    For each table, compute inclusion_confidence based on tier weight (60%)
    and concept extraction confidence (40%).
    Returns a sorted list of table dicts with explainability fields.
    """
    results = []
    for name, table in merged.items():
        tier_score = TIER_SCORES.get(table["tier"], 0.5)
        confidence = round(tier_score * 0.6 + concept_confidence * 0.4, 2)
        table["inclusion_confidence"] = confidence
        table["patterns_applied"]     = []
        results.append(table)

    results.sort(key=lambda x: -TIER_RANK.get(x["tier"], 0))
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API — select_tables()
# ══════════════════════════════════════════════════════════════════════════════

def select_tables(active_concepts, concept_confidence=0.9):
    """
    Main entry point for the Table Selection Algorithm.

    Parameters
    ----------
    active_concepts : list[str]
        Concept name strings (e.g. ["e_commerce_orders", "invoicing"]).
    concept_confidence : float
        Max extraction confidence from the extractor stage (used in scoring).

    Returns
    -------
    list[dict]
        Sorted list of table dicts, each with:
        - name, tier, triggered_by, inclusion_confidence, patterns_applied
    """
    use_neo4j = _is_neo4j_available()

    # Step 1: Concept expansion
    if use_neo4j:
        expanded = _expand_concepts_neo4j(active_concepts)
    else:
        expanded = _expand_concepts_local(active_concepts)
    print(f"    Expanded concepts: {sorted(expanded)}")

    # Step 2: Table collection & tier merging
    if use_neo4j:
        merged = _collect_tables_neo4j(expanded)
    else:
        merged = _collect_tables_local(expanded)
    print(f"    Merged {len(merged)} tables from concepts")

    # Step 3: FK dependency resolution
    if use_neo4j:
        merged = _resolve_fk_deps_neo4j(merged)
    else:
        merged = _resolve_fk_deps_local(merged)

    added_deps = [n for n, t in merged.items() if t.get("dependency_reason")]
    if added_deps:
        print(f"    Added FK dependencies: {added_deps}")

    # Step 4: Prune suggested tables below co-occurrence threshold
    merged = _prune_suggested(merged, threshold=0.5)

    # Step 5: Compute explainability scores
    results = _compute_explainability(merged, concept_confidence)

    return results


# ── Standalone test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Input: 'E-commerce platform with invoicing'")
    print("=" * 60)
    print()

    tables = select_tables(["e_commerce_orders", "invoicing"])

    print()
    print("=" * 60)
    print(f"Final Selection: {len(tables)} tables")
    print("=" * 60)
    for t in tables:
        triggered = ", ".join(t.get("triggered_by", []))
        dep = f" [FK DEP: {t['dependency_reason']}]" if t.get("dependency_reason") else ""
        print(f"  {t['tier']:12} | {t['name']:20} | "
              f"conf={t['inclusion_confidence']} | from: {triggered}{dep}")

    # Assertions matching test_selector.py expectations
    names = [t["name"] for t in tables]
    assert "gift_cards" not in names, "gift_cards should be pruned!"
    assert "wishlists"  in names,     "wishlists should be kept!"
    assert "customers"  in names,     "customers must be included!"
    assert "products"   in names,     "products must be pulled as FK dep!"

    print()
    print("All assertions passed!")

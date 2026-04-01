"""
project_02/graph_loader.py
Loads all DomainConcepts, DesignDecisions, LogicalTables, SchemaPatterns,
REQUIRES_TABLE edges, and DEPENDS_ON edges into Neo4j.

Run standalone:
    python project_02/graph_loader.py

Or call load_full_graph() from the pipeline on startup.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from neo4j import GraphDatabase
from project_06.extractor import CONCEPTS, DECISIONS
from project_12.pipeline import (
    CONCEPT_TABLES, CONCEPT_DEPS, TABLE_DEPS,
    ENFORCED_FKS, PATTERNS, SYSTEM_TABLES,
)

URI  = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER",     "neo4j")
PASS = os.environ.get("NEO4J_PASSWORD", "internpassword")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run(tx, q, **params):
    return list(tx.run(q, **params))


def clear_graph(session):
    session.execute_write(_run, "MATCH (n) DETACH DELETE n")
    print("  ✓ Graph cleared")


# ── Load nodes ─────────────────────────────────────────────────────────────────

def load_domain_concepts(session):
    for name, desc in CONCEPTS.items():
        session.execute_write(_run, """
            MERGE (c:DomainConcept {name: $name})
            SET c.description = $desc,
                c.category    = $cat
        """,
        name=name,
        desc=desc,
        cat=_concept_category(name),
        )
    print(f"  ✓ {len(CONCEPTS)} DomainConcepts loaded")


def _concept_category(name):
    cats = {
        "user_authentication":  "platform",
        "product_catalog":      "commerce",
        "e_commerce_orders":    "commerce",
        "customer_management":  "commerce",
        "payment_processing":   "finance",
        "invoicing":            "finance",
        "multi_currency":       "finance",
        "gst_compliance":       "finance",
        "inventory_management": "operations",
        "supplier_management":  "operations",
        "employee_management":  "hr",
        "project_tracking":     "operations",
        "file_attachments":     "platform",
        "notifications":        "platform",
        "reporting_analytics":  "platform",
    }
    return cats.get(name, "platform")


def load_design_decisions(session):
    for name, config in DECISIONS.items():
        session.execute_write(_run, """
            MERGE (d:DesignDecision {name: $name})
            SET d.default_choice = $default,
                d.critical       = $critical,
                d.description    = $desc
        """,
        name=name,
        default=config["default"],
        critical=config.get("critical", False),
        desc=config.get("description", ""),
        )
    print(f"  ✓ {len(DECISIONS)} DesignDecisions loaded")


def load_logical_tables(session):
    """Collect all unique table names across all concepts and create LogicalTable nodes."""
    all_tables = {}   # name → tier (highest across all concepts)
    for concept, tables in CONCEPT_TABLES.items():
        for t in tables:
            n = t["name"]
            tier_map = {"required": 3, "recommended": 2, "suggested": 1}
            if n not in all_tables or tier_map[t["tier"]] > tier_map[all_tables[n]]:
                all_tables[n] = t["tier"]

    # Also add system tables
    for name in SYSTEM_TABLES:
        all_tables[name] = "required"

    for name, tier in all_tables.items():
        session.execute_write(_run, """
            MERGE (t:LogicalTable {name: $name})
            SET t.tier   = $tier,
                t.system = $system
        """,
        name=name,
        tier=tier,
        system=(name in SYSTEM_TABLES),
        )
    print(f"  ✓ {len(all_tables)} LogicalTables loaded")


def load_schema_patterns(session):
    for name, cols in PATTERNS.items():
        col_names = [c["name"] for c in cols]
        session.execute_write(_run, """
            MERGE (p:SchemaPattern {name: $name})
            SET p.column_names = $cols
        """,
        name=name,
        cols=col_names,
        )
    print(f"  ✓ {len(PATTERNS)} SchemaPatterns loaded")


# ── Load edges ─────────────────────────────────────────────────────────────────

def load_requires_table_edges(session):
    count = 0
    for concept, tables in CONCEPT_TABLES.items():
        for t in tables:
            session.execute_write(_run, """
                MATCH (c:DomainConcept  {name: $concept})
                MATCH (t:LogicalTable   {name: $table})
                MERGE (c)-[r:REQUIRES_TABLE]->(t)
                SET r.tier = $tier
            """,
            concept=concept,
            table=t["name"],
            tier=t["tier"],
            )
            count += 1
    print(f"  ✓ {count} REQUIRES_TABLE edges loaded")


def load_depends_on_edges(session):
    count = 0
    for concept, deps in CONCEPT_DEPS.items():
        for dep in deps:
            session.execute_write(_run, """
                MATCH (a:DomainConcept {name: $a})
                MATCH (b:DomainConcept {name: $b})
                MERGE (a)-[:DEPENDS_ON]->(b)
            """,
            a=concept, b=dep,
            )
            count += 1
    print(f"  ✓ {count} DEPENDS_ON edges loaded")


def load_table_fk_edges(session):
    count = 0
    for table, deps in TABLE_DEPS.items():
        for dep in deps:
            session.execute_write(_run, """
                MATCH (a:LogicalTable {name: $a})
                MATCH (b:LogicalTable {name: $b})
                MERGE (a)-[:FK_DEPENDS_ON]->(b)
            """,
            a=table, b=dep,
            )
            count += 1
    print(f"  ✓ {count} FK_DEPENDS_ON edges loaded")


def load_enforced_fk_edges(session):
    count = 0
    for table, fks in ENFORCED_FKS.items():
        for fk in fks:
            session.execute_write(_run, """
                MATCH (a:LogicalTable {name: $a})
                MATCH (b:LogicalTable {name: $b})
                MERGE (a)-[r:REFERENCES]->(b)
                SET r.from_column = $from_col,
                    r.to_column   = $to_col,
                    r.on_delete   = $on_delete,
                    r.ref_type    = 'enforced'
            """,
            a=table,
            b=fk["to_table"],
            from_col=fk["from_column"],
            to_col=fk["to_column"],
            on_delete=fk.get("on_delete", "CASCADE"),
            )
            count += 1
    print(f"  ✓ {count} REFERENCES (enforced FK) edges loaded")


# ── Constraints & indexes ──────────────────────────────────────────────────────

def create_constraints(session):
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:DomainConcept)  REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:DesignDecision) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:LogicalTable)   REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:SchemaPattern)  REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (cc:CandidateConcept) REQUIRE cc.name IS UNIQUE",
    ]
    for c in constraints:
        session.execute_write(_run, c)
    print(f"  ✓ {len(constraints)} constraints created")


# ── Verify load ────────────────────────────────────────────────────────────────

def verify(session):
    result = session.execute_read(_run, """
        MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt
        ORDER BY cnt DESC
    """)
    print("\n  Node counts:")
    for r in result:
        print(f"    {r['label']:25} {r['cnt']}")

    result2 = session.execute_read(_run, """
        MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt
        ORDER BY cnt DESC
    """)
    print("  Edge counts:")
    for r in result2:
        print(f"    {r['rel']:25} {r['cnt']}")


# ── Main entry point ───────────────────────────────────────────────────────────

def load_full_graph(clear=True, verbose=True):
    """
    Load the full knowledge graph into Neo4j.
    Call this from the pipeline or run standalone.
    Returns True if successful, False if Neo4j is not available.
    """
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASS))
        driver.verify_connectivity()
    except Exception as e:
        if verbose:
            print(f"  [Neo4j] Not available ({e}). Falling back to in-memory mode.")
        return False

    if verbose:
        print(f"\n{'='*55}")
        print("Loading SchemaAdvisor Knowledge Graph into Neo4j...")
        print(f"{'='*55}")

    with driver.session() as session:
        if clear:
            clear_graph(session)
        create_constraints(session)
        load_domain_concepts(session)
        load_design_decisions(session)
        load_logical_tables(session)
        load_schema_patterns(session)
        load_requires_table_edges(session)
        load_depends_on_edges(session)
        load_table_fk_edges(session)
        load_enforced_fk_edges(session)
        if verbose:
            verify(session)

    driver.close()
    if verbose:
        print("\n  ✅ Graph loaded successfully!\n")
    return True


if __name__ == "__main__":
    load_full_graph(clear=True, verbose=True)

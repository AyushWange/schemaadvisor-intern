import os
import json
import logging
from neo4j import GraphDatabase
from project_02.cache_manager import cache_manager, make_cache_key

logger = logging.getLogger(__name__)

URI  = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER",     "neo4j")
PASS = os.environ.get("NEO4J_PASSWORD", "internpassword")

SEED_DIR = os.path.join(os.path.dirname(__file__), "..", "seeds")

def _load_json(filename):
    with open(os.path.join(SEED_DIR, filename), "r") as f:
        return json.load(f)

# Helper for fallback when neo4j is down
_USE_NEO4J = None

def _is_neo4j_available():
    global _USE_NEO4J
    if _USE_NEO4J is not None:
        return _USE_NEO4J
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASS))
        driver.verify_connectivity()
        driver.close()
        _USE_NEO4J = True
    except:
        _USE_NEO4J = False
    return _USE_NEO4J


def get_selected_tables(concept_names):
    """
    Returns dict: table_name -> {tier, triggered_by, inclusion_confidence}
    Uses Cypher to traverse dependencies and requires_table edges.
    Results are cached for CACHE_TTL_SECONDS (default 1 hour).
    """
    if not _is_neo4j_available():
        raise Exception("Neo4j is required according to spec")

    # ── Cache lookup ──────────────────────────────────────────────────────────
    cache_key = make_cache_key("selected_tables", "|".join(sorted(concept_names)))
    cached = cache_manager.get(cache_key)
    if cached is not None:
        logger.info("Cache HIT for selected_tables key=%s", cache_key)
        return cached

    logger.info("Cache MISS for selected_tables — querying Neo4j")

    query = """
    MATCH (dc:DomainConcept)-[:DEPENDS_ON*0..]->(dep:DomainConcept)
    WHERE dc.name IN $concepts
    MATCH (dep)-[r:REQUIRES_TABLE]->(lt:LogicalTable)
    RETURN lt.name AS table,
           max(CASE r.tier WHEN 'required' THEN 3 WHEN 'recommended' THEN 2 ELSE 1 END) AS max_tier,
           collect(DISTINCT dep.name) AS triggered_by
    """

    driver = GraphDatabase.driver(URI, auth=(USER, PASS))
    results = {}
    with driver.session() as session:
        records = session.run(query, concepts=concept_names)
        for rec in records:
            tname = rec["table"]
            tier_val = rec["max_tier"]
            tier = "required" if tier_val == 3 else ("recommended" if tier_val == 2 else "suggested")
            results[tname] = {
                "name": tname,
                "tier": tier,
                "triggered_by": rec["triggered_by"]
            }
    driver.close()

    # ── Cache store ───────────────────────────────────────────────────────────
    cache_manager.set(cache_key, results)
    return results

def get_enforced_fks(table_names):
    """
    Cypher: MATCH (a)-[r:REFERENCES {ref_type: 'enforced'}]->(b)
    Results are cached for CACHE_TTL_SECONDS (default 1 hour).
    """
    # ── Cache lookup ──────────────────────────────────────────────────────────
    cache_key = make_cache_key("enforced_fks", "|".join(sorted(table_names)))
    cached = cache_manager.get(cache_key)
    if cached is not None:
        logger.info("Cache HIT for enforced_fks key=%s", cache_key)
        return cached

    logger.info("Cache MISS for enforced_fks — querying Neo4j")

    query = """
    MATCH (a:LogicalTable)-[r:REFERENCES {ref_type: 'enforced'}]->(b:LogicalTable)
    WHERE a.name IN $table_names AND b.name IN $table_names
    RETURN a.name AS from_table, b.name AS to_table, r.from_column AS from_column, r.to_column AS to_column, r.on_delete AS on_delete
    """
    driver = GraphDatabase.driver(URI, auth=(USER, PASS))
    fks = []
    with driver.session() as session:
        records = session.run(query, table_names=list(table_names))
        for rec in records:
            fks.append({
                "from_table": rec["from_table"],
                "to_table": rec["to_table"],
                "from_column": rec["from_column"],
                "to_column": rec["to_column"],
                "on_delete": rec["on_delete"]
            })
    driver.close()

    # ── Cache store ───────────────────────────────────────────────────────────
    cache_manager.set(cache_key, fks)
    return fks

def get_patterns_config():
    return _load_json("seed_patterns.json")

def get_table_columns_config():
    cols_data = _load_json("seed_table_columns.json")
    mapping = {}
    for item in cols_data:
        mapping[item["logical_table"]] = item["curated_columns"]
    return mapping

def get_system_tables_config():
    sys_data = _load_json("seed_system_tables.json")
    mapping = {}
    for item in sys_data:
        mapping[item["logical_table"]] = {
            "name": item["logical_table"],
            "tier": "required",
            "triggered_by": ["system_pattern"],
            "patterns_applied": [],
            "inclusion_confidence": 1.0,
            "columns": item["columns"],
            "enforced_fks": [],
            "logical_refs": [],
        }
    return mapping

def map_candidate(raw_text, concept, table):
    """
    Creates a provisional REQUIRES_TABLE edge in Neo4j from a Discovery UI mapping.
    Also removes the candidate concept node.
    """
    if not _is_neo4j_available():
        return False
        
    query = """
    MATCH (cc:CandidateConcept {name: $raw_text})
    MATCH (c:DomainConcept {name: $concept})
    MERGE (t:LogicalTable {name: $table})
    ON CREATE SET t.tier = 'suggested', t.system = false
    MERGE (c)-[r:REQUIRES_TABLE]->(t)
    SET r.tier = 'suggested',
        r.source = 'user_mapping',
        r.provisional = true
    DETACH DELETE cc
    """
    driver = GraphDatabase.driver(URI, auth=(USER, PASS))
    try:
        with driver.session() as session:
            session.run(query, raw_text=raw_text, concept=concept, table=table)
        return True
    except Exception as e:
        print(f"Failed to map candidate: {e}")
        return False
    finally:
        driver.close()

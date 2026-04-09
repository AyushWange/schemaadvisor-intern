"""
project_02/candidate_logger.py
Logs unmatched items from the LLM extractor as CandidateConcept nodes in Neo4j.
Increments frequency on repeat encounters.

Usage:
    from project_02.candidate_logger import log_candidates
    log_candidates(result.unmatched, source_scenario="e-commerce SaaS")
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

URI  = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
USER = os.environ.get("NEO4J_USER",     "neo4j")
PASS = os.environ.get("NEO4J_PASSWORD", "internpassword")

_driver = None   # module-level singleton


def _get_driver():
    global _driver
    if _driver is None:
        try:
            from neo4j import GraphDatabase
            d = GraphDatabase.driver(URI, auth=(USER, PASS))
            d.verify_connectivity()
            _driver = d
        except Exception:
            _driver = False   # mark as unavailable so we don't retry every call
    return _driver


def log_candidates(unmatched_items, source_scenario: str = "unknown"):
    """
    Persist a list of UnmatchedItem objects to Neo4j as CandidateConcept nodes.
    Only logs items with category == 'potential_table'.

    Args:
        unmatched_items: list of UnmatchedItem (from ExtractionResult.unmatched)
        source_scenario: description of the requirements that produced them

    Returns:
        int: number of candidates logged (0 if Neo4j unavailable)
    """
    driver = _get_driver()
    if not driver:
        return 0   # Neo4j not available — silent fail

    today = datetime.utcnow().strftime("%Y-%m-%d")
    logged = 0

    with driver.session() as session:
        for item in unmatched_items:
            # Only persist potential_table candidates (spec §7.1.1)
            if getattr(item, "category", "") != "potential_table":
                continue

            raw  = item.raw_text.strip()
            name = _normalize(raw)
            if not name:
                continue

            nearest = getattr(item, "nearest_concept", None) or ""

            session.execute_write(_upsert_candidate,
                name=name,
                raw_text=raw,
                first_seen=today,
                scenario=source_scenario,
                nearest=nearest,
            )
            logged += 1

    return logged


def _upsert_candidate(tx, name, raw_text, first_seen, scenario, nearest):
    """
    MERGE on name — increments frequency, appends scenario to list.
    """
    tx.run("""
        MERGE (cc:CandidateConcept {name: $name})
        ON CREATE SET
            cc.raw_text        = $raw_text,
            cc.frequency       = 1,
            cc.first_seen_date = $first_seen,
            cc.nearest_concept = $nearest,
            cc.source_scenarios = [$scenario]
        ON MATCH SET
            cc.frequency        = cc.frequency + 1,
            cc.source_scenarios = CASE
                WHEN $scenario IN cc.source_scenarios THEN cc.source_scenarios
                ELSE cc.source_scenarios + [$scenario]
            END
    """,
    name=name,
    raw_text=raw_text,
    first_seen=first_seen,
    scenario=scenario,
    nearest=nearest,
    )


def _normalize(raw: str) -> str:
    """Convert raw text to a clean snake_case concept name."""
    import re
    s = raw.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = s[:80]   # cap length
    return s


def get_all_candidates():
    """
    Retrieve all CandidateConcept nodes from Neo4j.
    Returns list of dicts, or empty list if Neo4j unavailable.
    """
    driver = _get_driver()
    if not driver:
        return []

    with driver.session() as session:
        result = session.execute_read(lambda tx: list(tx.run("""
            MATCH (cc:CandidateConcept)
            RETURN cc.name            AS name,
                   cc.raw_text        AS raw_text,
                   cc.frequency       AS frequency,
                   cc.first_seen_date AS first_seen_date,
                   cc.nearest_concept AS nearest_concept,
                   cc.source_scenarios AS source_scenarios
            ORDER BY cc.frequency DESC
        """)))
        return [dict(r) for r in result]


if __name__ == "__main__":
    # Quick smoke test
    class FakeItem:
        def __init__(self, raw, cat, nearest=None):
            self.raw_text = raw
            self.category = cat
            self.nearest_concept = nearest

    items = [
        FakeItem("blockchain ledger",        "potential_table", "invoicing"),
        FakeItem("IoT telemetry data",       "potential_table", "reporting_analytics"),
        FakeItem("patient medical records",  "potential_table", "customer_management"),
        FakeItem("calculate tax rate",       "unsupported_logic"),  # should NOT be logged
    ]

    n = log_candidates(items, source_scenario="demo test run")
    print(f"Logged {n} candidates to Neo4j")

    all_c = get_all_candidates()
    print(f"Total candidates in graph: {len(all_c)}")
    for c in all_c:
        print(f"  {c['name']:30} freq={c['frequency']}  nearest={c['nearest_concept']}")

import pytest
from project_12.pipeline import (
    select_tables, 
    apply_all_patterns, 
    build_dependency_dict, 
    kahns_sort, 
    generate_ddl
)

class MockConcept:
    def __init__(self, name, confidence):
        self.name = name
        self.confidence = confidence

def test_pipeline_core_succeeds():
    # End-to-end test skipping LLM and PostgreSQL execution
    concepts = [MockConcept("e_commerce_orders", 0.95), MockConcept("invoicing", 0.90)]
    
    # 1. Selection
    tables = select_tables(concepts)
    
    # 2. Pattern Application
    enriched = apply_all_patterns(tables)
    
    # 3. Dependency DAG
    deps = build_dependency_dict(enriched)
    
    # 4. Sorting
    order = kahns_sort(deps)
    
    # 5. DDL Generation
    ddl = generate_ddl(enriched, order)
    
    # Verifications
    assert len(tables) > 5
    assert len(order) == len(enriched)
    assert "BEGIN;" in ddl
    assert "CREATE TABLE customers (" in ddl
    assert "CREATE TABLE orders (" in ddl
    assert "COMMIT;" in ddl

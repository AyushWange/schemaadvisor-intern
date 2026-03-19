from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "internpassword")

CREATE_CONCEPTS = """
CREATE (inv:DomainConcept {
    name: 'invoicing', category: 'finance',
    description: 'Sales invoices, invoice items, tax line entries',
    aliases: ['invoices', 'billing', 'accounts receivable']
})
CREATE (cust:DomainConcept {
    name: 'customer_management', category: 'commerce',
    description: 'Customer records, addresses, groups, contacts',
    aliases: ['customers', 'CRM', 'client management']
})
CREATE (inv_mgmt:DomainConcept {
    name: 'inventory_management', category: 'operations',
    description: 'Warehouses, stock entries, stock ledger',
    aliases: ['inventory', 'stock', 'warehouse']
})
"""

CREATE_TABLES = """
CREATE (:LogicalTable {name: 'invoices',       description: 'Sales invoice header'})
CREATE (:LogicalTable {name: 'invoice_items',  description: 'Line items per invoice'})
CREATE (:LogicalTable {name: 'tax_entries',    description: 'Tax breakdown per invoice'})
CREATE (:LogicalTable {name: 'customers',      description: 'Core customer records'})
CREATE (:LogicalTable {name: 'addresses',      description: 'Customer addresses'})
CREATE (:LogicalTable {name: 'contacts',       description: 'Contact persons'})
CREATE (:LogicalTable {name: 'warehouses',     description: 'Physical warehouse locations'})
CREATE (:LogicalTable {name: 'stock_entries',  description: 'Stock movement transactions'})
CREATE (:LogicalTable {name: 'stock_ledger',   description: 'Running balance per item'})
CREATE (:LogicalTable {name: 'products',       description: 'Product/item master'})
"""

CREATE_EDGES = [
    "MATCH (c:DomainConcept {name: 'invoicing'}), (t:LogicalTable {name: 'invoices'})        CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'invoicing'}), (t:LogicalTable {name: 'invoice_items'})   CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'invoicing'}), (t:LogicalTable {name: 'tax_entries'})     CREATE (c)-[:REQUIRES_TABLE {tier: 'recommended'}]->(t)",
    "MATCH (c:DomainConcept {name: 'customer_management'}), (t:LogicalTable {name: 'customers'}) CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'customer_management'}), (t:LogicalTable {name: 'addresses'}) CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'customer_management'}), (t:LogicalTable {name: 'contacts'})  CREATE (c)-[:REQUIRES_TABLE {tier: 'recommended'}]->(t)",
    "MATCH (c:DomainConcept {name: 'inventory_management'}), (t:LogicalTable {name: 'warehouses'})    CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'inventory_management'}), (t:LogicalTable {name: 'stock_entries'}) CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'inventory_management'}), (t:LogicalTable {name: 'stock_ledger'})  CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (c:DomainConcept {name: 'inventory_management'}), (t:LogicalTable {name: 'products'})      CREATE (c)-[:REQUIRES_TABLE {tier: 'required'}]->(t)",
    "MATCH (a:DomainConcept {name: 'invoicing'}), (b:DomainConcept {name: 'customer_management'}) CREATE (a)-[:DEPENDS_ON {reason: 'Invoices reference customers'}]->(b)",
]

CREATE_DECISION = """
CREATE (dd:DesignDecision {
    name: 'audit_policy', default_choice: 'full_audit',
    alternatives: ['no_audit'], critical: false,
    description: 'Adds created_at, updated_at, created_by, updated_by to all tables'
})
"""

CREATE_PATTERN = """
CREATE (sp:SchemaPattern {
    name: 'audit_columns',
    description: 'Audit trail columns',
    introduces_fk: false
})
"""

LINK_DECISION_PATTERN = """
MATCH (dd:DesignDecision {name: 'audit_policy'}), (sp:SchemaPattern {name: 'audit_columns'})
CREATE (dd)-[:ACTIVATES_PATTERN {when_choice: 'full_audit', introduces_fk: false}]->(sp)
"""

def get_full_plan(tx, concept_name):
    query = """
    MATCH (c:DomainConcept {name: $name})-[:DEPENDS_ON*0..]->(dep:DomainConcept)
    MATCH (dep)-[r:REQUIRES_TABLE]->(t:LogicalTable)
    RETURN t.name AS table, r.tier AS tier, dep.name AS source
    ORDER BY dep.name, r.tier
    """
    return [record for record in tx.run(query, name=concept_name)]

def get_direct_tables(tx, concept_name):
    query = """
    MATCH (c:DomainConcept {name: $name})-[r:REQUIRES_TABLE]->(t:LogicalTable)
    RETURN t.name AS table, r.tier AS tier
    ORDER BY r.tier
    """
    return [record for record in tx.run(query, name=concept_name)]

def get_concepts_for_table(tx, table_name):
    query = """
    MATCH (c:DomainConcept)-[r:REQUIRES_TABLE]->(t:LogicalTable {name: $name})
    RETURN c.name AS concept, r.tier AS tier
    """
    return [record for record in tx.run(query, name=table_name)]

def get_activated_patterns(tx):
    query = """
    MATCH (dd:DesignDecision)-[a:ACTIVATES_PATTERN]->(sp:SchemaPattern)
    RETURN dd.name AS decision, a.when_choice AS when_choice, sp.name AS pattern
    """
    return [record for record in tx.run(query)]

def clear_db(tx):
    tx.run("MATCH (n) DETACH DELETE n")

def setup_graph(session):
    print("Setting up graph...")
    session.execute_write(clear_db)
    session.execute_write(lambda tx: tx.run(CREATE_CONCEPTS))
    session.execute_write(lambda tx: tx.run(CREATE_TABLES))
    for edge in CREATE_EDGES:
        session.execute_write(lambda tx, e=edge: tx.run(e))
    session.execute_write(lambda tx: tx.run(CREATE_DECISION))
    session.execute_write(lambda tx: tx.run(CREATE_PATTERN))
    session.execute_write(lambda tx: tx.run(LINK_DECISION_PATTERN))
    print("Graph ready.\n")

if __name__ == "__main__":
    driver = GraphDatabase.driver(URI, auth=AUTH)

    with driver.session() as session:
        setup_graph(session)

        print("=== Query 1: Direct tables for 'invoicing' ===")
        rows = session.execute_read(get_direct_tables, "invoicing")
        for r in rows:
            print(f"  Table: {r['table']:20} | Tier: {r['tier']}")

        print("\n=== Query 2: Full plan for 'invoicing' (with dependencies) ===")
        rows = session.execute_read(get_full_plan, "invoicing")
        for r in rows:
            print(f"  Table: {r['table']:20} | Tier: {r['tier']:12} | Source: {r['source']}")

        print("\n=== Query 3: Concepts that trigger 'customers' ===")
        rows = session.execute_read(get_concepts_for_table, "customers")
        for r in rows:
            print(f"  Concept: {r['concept']:25} | Tier: {r['tier']}")

        print("\n=== Query 4: Activated patterns ===")
        rows = session.execute_read(get_activated_patterns)
        for r in rows:
            print(f"  Decision: {r['decision']:15} | Choice: {r['when_choice']:12} | Pattern: {r['pattern']}")

    driver.close()
import asyncio
import json
import os
from neo4j import AsyncGraphDatabase

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASS", "internpassword")

class AsyncGraphLoader:
    def __init__(self, uri, user, password):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    async def create_constraints(self):
        """1. Create constraints for unique IDs"""
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:DomainConcept) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:DesignDecision) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sp:SchemaPattern) REQUIRE sp.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (lt:LogicalTable) REQUIRE lt.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (tt:TableTemplate) REQUIRE tt.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (st:SystemTable) REQUIRE st.id IS UNIQUE"
        ]
        
        async with self.driver.session() as session:
            for query in queries:
                await session.run(query)
            print("✓ Unique identity constraints created.")

    async def load_logical_and_system_tables(self, tables_data):
        """2a. Load Logical/System tables & 2b. IMPLEMENTED_BY edges"""
        query = """
        UNWIND $data AS row
        MERGE (l:LogicalTable {id: row.logical_id})
        ON CREATE SET l.name = row.logical_name
        
        MERGE (s:SystemTable {id: row.system_id})
        ON CREATE SET s.name = row.system_name
        
        MERGE (l)-[:IMPLEMENTED_BY]->(s)
        """
        async with self.driver.session() as session:
            await session.run(query, parameters={"data": tables_data})
            print("✓ Logical/System Tables and IMPLEMENTED_BY edges loaded.")

    async def load_references(self, references_data):
        """2c. Create REFERENCES edges with enforcement distinctions"""
        query = """
        UNWIND $data AS row
        MATCH (a:SystemTable {id: row.from_id})
        MATCH (b:SystemTable {id: row.to_id})
        
        MERGE (a)-[r:REFERENCES]->(b)
        SET r.ref_type = row.ref_type
        """
        async with self.driver.session() as session:
            await session.run(query, parameters={"data": references_data})
            print("✓ REFERENCES edges loaded.")

    async def connect_concepts_to_tables(self, concept_data):
        """2d. Connect DomainConcept to LogicalTable via REQUIRES_TABLE"""
        query = """
        UNWIND $data AS row
        MERGE (c:DomainConcept {id: row.concept_id})
        MERGE (l:LogicalTable {id: row.logical_id})
        
        MERGE (c)-[r:REQUIRES_TABLE]->(l)
        SET r.tier = row.tier
        """
        async with self.driver.session() as session:
            await session.run(query, parameters={"data": concept_data})
            print("✓ REQUIRES_TABLE edges loaded.")

async def main():
    loader = AsyncGraphLoader(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
    
    try:
        await loader.create_constraints()
        # In a real scenario, you'd load parsed JSON records rather than inline data.
        print("Async setup complete. Add data loading below.")
    finally:
        await loader.close()

if __name__ == "__main__":
    asyncio.run(main())

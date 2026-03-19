# SchemaAdvisor: Intern Pre-Joining Implementation Guide
**Completed by:** Ayush Wange 
**Company:** Shivom Labs  
**Duration:** Pre-joining preparation  
**Language:** Python 3.10  

---

## What is SchemaAdvisor?

SchemaAdvisor is a system that takes natural language input like:

> "I need an online store with invoicing"

And automatically produces a validated PostgreSQL database schema with correct table ordering, foreign key constraints, standard columns, and indexes.

---

## Full Pipeline
```
User types natural language
        ↓
[Project 6]  LLM extracts concepts
        ↓
[Project 10] Conflict detection
        ↓
[Project 9]  Table selection
        ↓
[Project 8]  Reference classification
        ↓
[Project 1]  Kahn's topological sort
        ↓
[Project 4]  Pattern injection
        ↓
[Project 5]  DDL generation
        ↓
[Project 7]  PostgreSQL validation
        ↓
Working database schema!

Supporting:
[Project 2]  Neo4j knowledge graph
[Project 3]  ERPNext parser
[Project 11] Semantic proximity search
[Project 12] End-to-end pipeline
```

---

## Projects

---

### Project 1 — Dependency Resolver
**Concept:** Kahn's Topological Sort Algorithm  
**File:** `project_01/resolver.py`

**What it does:**  
Figures out the correct order to create database tables so PostgreSQL never throws foreign key errors. For example, `customers` must be created before `orders` because `orders` references `customers`.

**Key features:**
- Implements Kahn's algorithm from scratch
- Detects circular dependencies and raises errors
- Deterministic output (alphabetical sorting)

**Output:**
```
=== Test 1: Simple E-commerce ===
customers -> products -> orders -> order_items -> payments -> shipping
All dependencies satisfied!

=== Test 2: Circular Dependency ===
Correctly detected: Circular dependency detected!

=== Test 3: ERP System ===
companies -> currencies -> users -> customers -> departments -> ...
All 13 tables ordered successfully!
```

---

### Project 2 — Graph Taxonomy Modeling
**Concept:** Neo4j Property Graphs & Cypher Query Language  
**File:** `project_02/query_graph.py`  
**Requires:** Docker Desktop, Neo4j

**What it does:**  
Stores business knowledge in a graph database. Business concepts like "invoicing" are connected to the database tables they need via typed relationships. Asking for "invoicing" automatically pulls in `customer_management` tables too because of the `DEPENDS_ON` relationship.

**Key features:**
- Creates DomainConcept, LogicalTable, DesignDecision, SchemaPattern nodes
- REQUIRES_TABLE edges with tier properties (required/recommended/suggested)
- DEPENDS_ON edges for automatic concept expansion
- 4 traversal queries for different use cases

**Output:**
```
=== Query 2: Full plan for 'invoicing' (with dependencies) ===
  Table: customers      | Tier: required    | Source: customer_management
  Table: addresses      | Tier: required    | Source: customer_management
  Table: contacts       | Tier: recommended | Source: customer_management
  Table: invoices       | Tier: required    | Source: invoicing
  Table: invoice_items  | Tier: required    | Source: invoicing
  Table: tax_entries    | Tier: recommended | Source: invoicing
```

---

### Project 3 — ERPNext Parser
**Concept:** JSON Parsing, Type Mapping & Reference Classification  
**Files:** `project_03/parser.py`, `project_03/sample_doctype.json`

**What it does:**  
Reads ERPNext's JSON DocType files and converts them into clean PostgreSQL-ready table structures. Removes framework columns, translates field types, and classifies Link fields as enforced or logical foreign keys.

**Key features:**
- Type mapping (Currency → DECIMAL(18,6), Check → BOOLEAN, etc.)
- Filters layout fields (Section Break, Column Break)
- Filters framework columns (naming_series, parent, idx, etc.)
- Classifies references as candidate_enforced or logical
- Detects audit_columns and status_workflow patterns

**Output:**
```
12 columns (framework excluded)
1 candidate enforced refs: ['customer']
1 logical refs: ['sales_invoice']
Patterns: ['audit_columns', 'status_workflow']
All assertions passed!
```

---

### Project 4 — Pattern Injector
**Concept:** Schema Materialization & Semantic Deduplication  
**File:** `project_04/patterns.py`

**What it does:**  
Automatically adds standard columns to every table (audit trail, soft delete, status workflow). Uses semantic equivalents to avoid adding duplicate columns — if a table already has `creation`, it won't add `created_at` again.

**Key features:**
- 3 patterns: audit_columns, soft_delete, status_workflow
- Semantic deduplication dictionary
- Handles ERPNext-style column names (creation, modified, modified_by)
- Assertion checks for zero duplicates

**Output:**
```
Pattern 'audit_columns' on 'invoices':
  Added:   created_by
  Skipped: created_at (covered by 'creation')
  Skipped: updated_at (covered by 'modified')
  Skipped: updated_by (covered by 'modified_by')

No duplicate columns in any table!
```

---

### Project 5 — DDL Generation with Jinja2
**Concept:** Template-Based Code Generation  
**Files:** `project_05/ddl_gen.py`, `project_05/create_table.sql.j2`, `project_05/output.sql`  
**Install:** `pip install jinja2`

**What it does:**  
Converts Python table definitions into real executable PostgreSQL SQL using Jinja2 templates. Generates CREATE TABLE statements with FK constraints, indexes for both enforced and logical refs, and COMMENT ON for logical references.

**Key features:**
- Jinja2 template separates SQL structure from data
- BEGIN/COMMIT transaction wrapping
- FK constraints for enforced refs
- CREATE INDEX for all refs
- COMMENT ON for logical refs (explainability)

**Output:**
```sql
BEGIN;
CREATE TABLE customers (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    customer_id BIGINT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
COMMIT;
```

---

### Project 6 — Guardrailed LLM Extraction
**Concept:** Prompt Engineering, Closed-Set Classification, Pydantic Validation  
**File:** `project_06/extractor.py`  
**Install:** `pip install anthropic pydantic`

**What it does:**  
Uses an LLM (or mock) to extract structured database concepts from natural language. The LLM can ONLY pick from a predefined closed concept list — it cannot invent new concepts. Includes a critical decision gate that halts when confidence is too low.

**Key features:**
- Closed concept set with 10 business domains
- Pydantic models for type-safe validation
- Gatekeeper rejects hallucinated concepts
- Critical decision gate (confidence < 0.85 → HALT)
- Mock version included (no API key needed)

**Output:**
```
Test 1: Online store with products, shopping cart, and payments
  concept: e_commerce_orders    confidence: 0.95
  concept: product_catalog      confidence: 0.90
  concept: payment_processing   confidence: 0.95

Test 5: A cloud app for client data
  HALTED: tenancy_model=multi_tenant (confidence 0.6 < 0.85)
  Would need user confirmation before applying!
```

---

### Project 7 — PostgreSQL Validation
**Concept:** Execution-Based Testing of Generated SQL  
**File:** `project_07/validator.py`  
**Install:** `pip install psycopg2-binary`, Docker

**What it does:**  
Proves that generated SQL actually works by executing it against a real PostgreSQL database. Creates a fresh test database, runs every statement, reports results, then cleans up. Also proves that Kahn's ordering is essential by showing what happens with wrong order.

**Key features:**
- Creates isolated test database per run
- Tests correct vs wrong table ordering
- Automatic cleanup after each test
- Timing measurements

**Output:**
```
Test 1: Correct order (Kahn's output)
  Results (3/3 in 48ms):
    ✓ customers
    ✓ orders
    ✓ order_items

Test 2: Wrong order (should fail)
  Results (1/3 in 40ms):
    ✗ order_items — relation "orders" does not exist
    ✗ orders — relation "customers" does not exist
    ✓ customers
```

---

### Project 8 — Two-Pass Reference Classification
**Concept:** Enforced vs Logical FK Classification with Cycle Breaking  
**File:** `project_08/ref_classifier.py`

**What it does:**  
Classifies foreign key references in two passes. Pass 1 does basic classification (required + target exists = enforced). Pass 2 detects circular dependencies and breaks them by downgrading the weakest edge to logical using strength scoring.

**Key features:**
- Pass 1: Static classification based on field properties
- Pass 2: DFS cycle detection
- Strength scoring (hub tables score higher)
- Shadow Edge Protocol (downgraded edges flagged)
- Assertion verifies acyclic result

**Output:**
```
Pass 1: 8 candidate enforced, 2 logical

Pass 2: Cycle Resolution
  Iteration 1: Downgraded purchase_order → supplier (strength=0.4)
               Cycle: purchase_order → supplier → supplier_group → purchase_order

Enforced graph is acyclic!
8 edges survived!
```

---

### Project 9 — Table Selection Algorithm
**Concept:** Tier-Based Selection, Dependency Pull-In, Co-occurrence Pruning  
**File:** `project_09/selector.py`

**What it does:**  
Selects exactly the right tables for a given set of concepts. Expands concept dependencies, merges duplicate tables (highest tier wins), pulls in FK dependencies automatically, prunes suggested tables by co-occurrence threshold, and scores inclusion confidence.

**Key features:**
- Automatic concept dependency expansion
- Tier merging (highest tier wins for duplicates)
- FK dependency pull-in
- Co-occurrence pruning (threshold 0.5)
- Inclusion confidence scoring

**Output:**
```
Step 1: Expanded concepts: {'e_commerce_orders', 'invoicing', 'customer_management'}
Step 2: Merged 11 tables
Step 3: Added FK dependencies: ['products']
Step 4: Pruned suggested tables: ['gift_cards (max_freq=0.3)']

Final Selection: 11 tables
  required     | customers    | conf=0.96
  required     | orders       | conf=0.96
  suggested    | wishlists    | conf=0.60

All assertions passed!
```

---

### Project 10 — Conflict Detection & Design Decisions
**Concept:** Cross-Decision Conflict Resolution, Critical Decision Halting  
**File:** `project_10/conflicts.py`

**What it does:**  
Detects when two design decisions clash with each other. Some combinations are preference tradeoffs (warning issued), others are hard incompatibilities (blocked). Critical decisions with low confidence are halted and require human confirmation.

**Key features:**
- 5 design decisions with defaults
- 3 conflict rules (2 tradeoffs, 1 incompatibility)
- Critical decision gate (confidence < 0.85 → HALT)
- Clear resolution guidance for each conflict

**Output:**
```
Scenario: Nested set + multi-tenant
  ✗ CONFLICT DETECTED!
    hierarchy_approach=nested_set × tenancy_model=multi_tenant
    Category:   hard_incompatibility
    Reason:     Nested set lft/rgt must be scoped per tenant
    Resolution: Recommend adjacency_list.

Scenario: Ambiguous tenancy (low confidence)
  HALT: tenancy_model=multi_tenant needs confirmation
        (confidence 0.6 < 0.85, critical decision)
```

---

### Project 11 — Semantic Proximity Search
**Concept:** TF-IDF Cosine Similarity for Concept Matching  
**File:** `project_11/proximity.py`  
**Install:** `pip install scikit-learn`

**What it does:**  
Finds the nearest concept when user input doesn't exactly match the taxonomy. Uses TF-IDF to convert concepts and queries into numerical vectors, then finds the closest match using cosine similarity. Cannot hallucinate — can only return concepts from the predefined list.

**Key features:**
- TF-IDF vectorizer built from concept descriptions and aliases
- Cosine similarity scoring
- Confidence levels (high/medium/low)
- Correctly returns no matches for out-of-domain queries

**Output:**
```
Query: 'logistics management'
  → inventory_management   similarity=0.412 (high)

Query: 'IoT device telemetry'
  → No matches above threshold

Query: 'task tracking and sprints'
  → project_tracking       similarity=0.614 (high)
```

---

### Project 12 — End-to-End Mini Pipeline
**Concept:** Full Pipeline Integration  
**File:** `project_12/pipeline.py`

**What it does:**  
Wires all 11 projects together into a single pipeline. Takes natural language input and produces a fully validated PostgreSQL schema with explainability report for every table.

**Key features:**
- All 8 stages integrated
- Full explainability report
- 15/15 SQL statements validated against real PostgreSQL
- Traces every table back to its source concept

**Output:**
```
INPUT: I need an e-commerce platform with product catalog and order tracking

  Stage 1: Concept Extraction
    ✓ e_commerce_orders (confidence=0.95)
    ✓ product_catalog   (confidence=0.90)

  Stage 4: Kahn's Sort
    categories → customers → products → orders → order_items

  Stage 7: PostgreSQL Validation
    Result: 15/15 statements succeeded in 173ms

  Stage 8: Explainability Report
    customers    required   0.96   e_commerce_orders
    orders       required   0.96   e_commerce_orders
    products     required   0.96   product_catalog
```

---

## Setup

### Prerequisites
```
Python 3.10+
Docker Desktop
VS Code
```

### Install all dependencies
```bash
pip install neo4j jinja2 anthropic pydantic psycopg2-binary scikit-learn
```

### Start Docker containers
```bash
# Neo4j
docker run -d --name neo4j-intern \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/internpassword \
  neo4j:latest

# PostgreSQL
docker run -d --name postgres-intern \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=internpass \
  -e POSTGRES_DB=schema_test \
  postgres:16-alpine
```

---

## What I Learned
```
✓ Kahn's topological sort algorithm
✓ Neo4j graph database and Cypher query language
✓ JSON parsing and data cleaning
✓ Schema materialization and semantic deduplication
✓ Jinja2 template-based code generation
✓ LLM prompt engineering with guardrails
✓ Pydantic data validation
✓ PostgreSQL execution-based testing
✓ Two-pass reference classification with cycle breaking
✓ Tier-based table selection with co-occurrence pruning
✓ Cross-decision conflict detection
✓ TF-IDF cosine similarity search
✓ Full pipeline integration
```

---

## Tech Stack
```
Language:  Python 3.10
Graph DB:  Neo4j 5.x
SQL DB:    PostgreSQL 16
Templates: Jinja2
AI:        Anthropic Claude API
Validation:Pydantic
ML:        scikit-learn (TF-IDF)
Container: Docker Desktop
```

---

*Prepared as part of Shivom Labs pre-joining internship program*
```

---

**To put this on GitHub:**
```
1. Create new repository on github.com
   Name: schemaadvisor-intern

2. Add this as README.md in root folder

3. Push all your project folders

4. Your repo structure:
   schemaadvisor-intern/
   ├── README.md
   ├── project_01/
   ├── project_02/
   ...
   └── project_12/
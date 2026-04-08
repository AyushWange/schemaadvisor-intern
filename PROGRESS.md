# SchemaAdvisor Project Progress & Context

This file serves as the definitive state-tracker for SchemaAdvisor to optimize token usage and maintain context across sessions.

## Project Overview
**SchemaAdvisor** is an intelligent database recommendation engine that converts natural language business requirements into valid, optimized PostgreSQL schemas using a Neo4j Knowledge Graph and LLM-powered extraction.

## Current Maturity: Phase 3 Complete (Intelligence & Selection)
The system is now capable of reasoning about database design using graph-based expansion, merging, and dependency resolution.

---

## Technical Stack
- **Backend**: FastAPI (Python)
- **Graph Knowledge Base**: Neo4j (Cypher)
- **LLM**: Claude (Anthropic API)
- **Frontend**: Vanilla HTML/JS/CSS (Glassmorphic Design)
- **Validation**: Psycopg2 (PostgreSQL)

---

## Core Architecture & Key Modules
| Module | Responsibility |
| :--- | :--- |
| **`project_02/db_access.py`** | Bridging Neo4j connections with pipeline orchestration. |
| **`project_02/graph_loader.py`** | Loading seed JSON data into Neo4j (Sync & Async versions). |
| **`project_06/extractor.py`** | LLM orchestrator for Concept and Design Decision extraction. |
| **`project_08/table_selector.py`** | **The Brain**: Handles expansion, tier-merging, FK resolution, and pruning. |
| **`project_12/pipeline.py`** | The master orchestrator connecting all stages (S1-S8). |
| **`api.py`** | FastAPI entry point and admin route handling. |

---

## Latest Advancements (2026-04-08)
- **Intelligent Selection**: Fully integrated `project_08/table_selector.py` into the main pipeline.
- **Dependency Propagation**: The system now automatically pulls in "required" tables via enforced FK traversal in the graph.
- **Smart Pruning**: Implemented `COMMONLY_PAIRED_WITH` pruning (frequency < 0.5) to keep "suggested" tables from bloating the schema.
- **Data Expansion**: Updated `seed_requires_table.json` with new suggested tables (`wishlists`, `gift_cards`, etc.) for robust testing.
- **Verification**: All 11+ project modules and 13 gold standard scenarios pass 100% via `pytest`.

---

## Next Steps
- [ ] Implement advanced Design Decision conflict resolution.
- [ ] Enhance explainability visualization in the frontend.
- [ ] Production-readiness preparation.

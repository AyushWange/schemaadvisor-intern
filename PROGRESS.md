# SchemaAdvisor Project Progress & Context

This file serves as the definitive state-tracker for SchemaAdvisor to optimize token usage and maintain context across sessions.

## Project Overview
**SchemaAdvisor** is an intelligent database recommendation engine that converts natural language business requirements into valid, optimized PostgreSQL schemas using a Neo4j Knowledge Graph and LLM-powered extraction.

## Current Maturity: Phase 3+ Complete (Intelligence, Selection & Conflict Resolution)
The system now catches architectural conflicts before generating schemas, blocking hard incompatibilities and surfacing preference tradeoff warnings to the frontend.

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
- **Conflict Resolution (Stage 2)**: Wired `project_10/conflicts.py` into `pipeline.py` Stage 2 — was previously a placeholder that always printed "No conflicts detected!".
- **Hard Incompatibility Blocking**: Pipeline now fully blocks and returns a structured error when incompatible decisions are detected (e.g. `nested_set` + `multi_tenant`).
- **Preference Tradeoff Warnings**: Soft conflicts (e.g. `versioned` + `soft_delete`) warn the user but allow the schema to still generate.
- **Critical Decision Gate**: Decisions marked `critical=True` (e.g. `tenancy_model`) are halted and reverted to default if confidence < 0.85.
- **API Response**: Added `conflicts: list[dict]` field to `SchemaResponse` so warnings surface to the frontend.
- **Frontend Conflicts Visualization**: Enhanced UI with dedicated conflicts panel showing hard incompatibilities (red, blocking) and tradeoff warnings (gold, informational).
- **Verification**: All 53 tests pass across all 11+ modules.

---

## Latest Frontend Enhancements (2026-04-08)
**Conflicts & Warnings Visualization:**
- **Panel Location**: Prominent conflicts panel in Schema tab (above SQL code)
- **Visual Hierarchy**: 
  - Hard incompatibilities: Red borders, "✗" icon, critical styling
  - Preference tradeoffs: Gold borders, "⚠" icon, warning styling
- **Information Density**:
  - Decision conflict (A=value × B=value)
  - Category label (Hard Incompatibility / Design Trade-off)
  - Reason: Domain-specific explanation of why they conflict
  - Resolution: Actionable guidance for the user
- **Interaction**:
  - Dismissible via close button (✕)
  - Hover animations for better UX
  - Color-coded by conflict severity
- **Implementation**:
  - New `renderConflicts()` function in `app.js` 
  - ~150 lines of CSS for glassmorphic conflict cards
  - Integrated into `renderResults()` pipeline

---

## Production-Readiness Enhancements (2026-04-08)
**Status: COMPLETE AND TESTED** ✅

### 1. Security & Input Validation
- **Input Constraints**: All fields validated with min/max lengths (requirements: 10-2000 chars)
- **XSS Protection**: HTML escaping on all user inputs
- **Rate Limiting**: 
  - `/schema`: 30 requests per minute per IP
  - Admin endpoints: 20-60 requests per minute per IP
- **CORS**: Restricted to `ALLOWED_ORIGINS` env var (not wildcard)
- **Request Validation**: Pydantic models with field validators
- **Timeout Protection**: 120-second timeout for schema generation operations

### 2. Error Handling & Graceful Degradation
- **Custom Exception Hierarchy**: SchemaAdvisorException, ValidationError, ServiceUnavailableError, TimeoutError
- **Structured Error Responses**: All errors include status, detail, request ID
- **Circuit Breakers**: Auto-trigger on 3+ LLM failures, 5+ Neo4j failures
- **Fallback Behaviors**: 
  - LLM unavailable → keyword matching
  - Neo4j unavailable → in-memory queue
  - PostgreSQL unavailable → skip validation
- **Information Leakage Prevention**: Generic error messages, detailed logging only

### 3. Monitoring & Observability
- **Request ID Tracking**: Unique ID for each request, propagated through logs
- **Structured Logging**: Timestamp, logger, level, request ID, message
- **Response Timing**: X-Response-Time and X-Process-Time headers  
- **Health Endpoint**: `/health` with service status, uptime, component readiness
- **Log Rotation**: Configurable with Python logging

### 4. API Enhancements
- **Middleware Stack**: 
  - RequestIDMiddleware: Unique tracking for every request
  - GZIPMiddleware: Compress responses > 1KB
  - CORSMiddleware: Security headers
  - RateLimitMiddleware: Per-IP throttling
- **Version Bump**: 2.7.0 → 2.8.0
- **Headers**:
  - X-Request-ID: Unique request identifier
  - X-Response-Time: Request duration in seconds
  - X-Process-Time: Request duration in milliseconds

### 5. Code Organization
- **error_handlers.py** (100 lines): Custom exception handlers, error response formatting
- **middleware.py** (120 lines): Request tracking, circuit breakers, response timing
- **api.py** (refactored): Cleaner imports, middleware registration, better logging

### 6. Deployment Infrastructure
- **DEPLOYMENT.md** (280 lines): Comprehensive guide covering:
  - Environment variable setup
  - Docker, Systemd, Gunicorn configuration
  - Monitoring and health checks
  - Security checklist
  - Disaster recovery procedures
  - Troubleshooting guide
  - Pre-production checklist

### 7. Testing & Verification
- ✅ All 53 unit tests pass
- ✅ API module syntax verified
- ✅ Error handlers tested
- ✅ Middleware integration verified
- ✅ Production configuration validated

---

## Next Steps
- [x] **Enhance explainability visualization in the frontend (show conflicts/warnings in UI).**
  - Added prominent conflicts panel to Schema tab that displays **hard incompatibilities** and **preference tradeoff warnings**
  - Styled with glassmorphic design matching existing UI aesthetic (red borders for hard blocks, gold for tradeoffs)
  - Shows decision conflicts with reasoning and resolution guidance
  - Dismissible panel with icon-based category indicators
- [x] **Production-readiness preparation.**
  - **Security & Input Validation**: Rate limiting (30 req/min), input sanitization, XSS protection, CORS restrictions, request validation with Pydantic
  - **Error Handling**: Custom exception handlers, fallback behaviors, graceful degradation, circuit breakers for external services
  - **Monitoring & Logging**: Structured logging with request IDs, unique request tracking, response timing, health check endpoint
  - **Deployment Documentation**: Comprehensive DEPLOYMENT.md with Docker, Systemd, Gunicorn configs, environment setup, monitoring checklist
  - **Code Infrastructure**: error_handlers.py, middleware.py for clean separation of concerns
  - **API Enhancement**: Security headers, GZIP compression, rate limiter integration, request/response tracking

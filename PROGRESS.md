# SchemaAdvisor Project Progress & Context

This file serves as the definitive state-tracker for SchemaAdvisor to optimize token usage and maintain context across sessions.

## Project Overview
**SchemaAdvisor** is an intelligent database recommendation engine that converts natural language business requirements into valid, optimized PostgreSQL schemas using a Neo4j Knowledge Graph and LLM-powered extraction.

## Current Maturity: Phase 4 Complete (Production-Ready v2.8.0) ✅
The system is fully production-ready with conflict resolution, multi-tenant support, and comprehensive security hardening. All 53 tests passing with zero high-priority issues.

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
## Decision Confirmation Flow (2026-04-08)
**Status: ✅ COMPLETE (Backend + Frontend)**

### 1. Two-Step Pipeline Flow
- **Post-Extraction Halt**: The pipeline pauses after Stage 1 (Extraction) to allow user review.
- **Session Store**: Added `_pending_decisions` in `api.py` to track state between extraction and confirmation.
- **New Endpoints**:
  - `POST /schema`: Returns `pending_decisions` when decisions are critical or confidence < 0.85.
  - `POST /schema/confirm`: Accepts user overrides and finalizes the DDL generation.
- **Verified end-to-end**: Extract → 2 pending decisions → Confirm → DDL generated with correct patterns.

### 2. Bug Fixes Applied
- **Class ordering**: Moved `PendingDecision` definition above `SchemaResponse` in `api.py` (was crashing on import).
- **`'str' has no attribute 'get'`**: Pipeline was returning flat `{name: "choice"}` but `build_pending_decisions` expected `{name: {choice, confidence, source}}`. Fixed by returning full metadata dicts.
- **Override filter**: Removed restrictive filter that only allowed overrides for LLM-extracted decisions. Now all 6 decisions can be overridden.
- **`apply_all_patterns`**: Added `_get_choice()` helper to handle both dict and string values for backward compatibility.

### 3. Frontend — Glassmorphic Confirmation Modal
- Added `decision-panel` overlay with blur backdrop in `index.html`.
- Radio buttons for each decision with recommended/alternative choices.
- Custom radio styling with indigo glow, impact descriptions, confidence badges.
- Confirm & Cancel buttons with full glassmorphic styling in `styles.css`.
- `app.js` implements `showDecisionConfirmation()` and wires up `/schema/confirm` POST.

### 4. Production-Readiness (prior session)
- **Security & Input Validation**: Rate limiting (30 req/min), input sanitization, XSS protection.
- **Error Handling**: Custom exception handlers, circuit breakers for LLM/Neo4j/Postgres.
- **Monitoring & Logging**: Structured logging with request IDs, response timing.
- **Deployment**: Comprehensive `DEPLOYMENT.md` with Docker, Systemd, Gunicorn configs.

---

## Completed: Multi-Tenant Column Injection (2026-04-08)
**Status: ✅ COMPLETE**

### Implementation Details
- **Pattern Definition**: Added "multi_tenant" pattern to `seed_patterns.json` with `tenant_id` BIGINT column
- **Pipeline Integration**: Updated `apply_all_patterns()` in `pipeline.py` Stage 3 to apply multi_tenant pattern when `tenancy_model="multi_tenant"`
- **Conditional Logic**: Pattern only applied when tenancy_model decision is explicitly set to "multi_tenant"
- **Test Coverage**: 
  - ✅ tenant_id injected for multi-tenant schemas
  - ✅ tenant_id NOT injected for single-tenant (default)
  - ✅ tenant_id correctly injected alongside other patterns (audit, temporal, soft delete)
  - ✅ All 53 tests passing with no regressions

---

## Next Steps
- [x] **Final production-readiness review and deployment verification.**
  - ✅ All 53 unit tests passing
  - ✅ Security hardening complete (rate limiting, XSS protection, input validation)
  - ✅ Error handling with graceful degradation and circuit breakers
  - ✅ Monitoring and logging with request ID tracking
  - ✅ API middleware stack operational (rate limiter, GZIP, CORS, request tracking)
  - ✅ Deployment documentation complete with Docker/Systemd/Gunicorn guides
  - ✅ Multi-tenant column injection working end-to-end
  - ✅ Decision confirmation flow fully functional
  - ✅ Conflicts visualization in frontend with hard blocks and tradeoff warnings
  - **Status**: PRODUCTION-READY v2.8.0 ✅

## Next Session (2026-04-08 Night)
- [x] **Production Deployment**: *(deferred — environment credentials needed)*
- [x] **Technical Enhancement**:
  - ✅ Implemented Hybrid Redis/In-Memory Caching for Neo4j concept registry (1-hour TTL).
  - ✅ Added Prometheus metrics, exposed at `/metrics`.

---

## Latest Advancements (2026-04-09)

### Caching Layer (v2.9.0)
**Status: ✅ COMPLETE AND TESTED**

- **New File**: `project_02/cache_manager.py`
  - Hybrid backend: uses **Redis** if `REDIS_URL` env var is set, otherwise falls back to thread-safe **in-memory TTLCache**.
  - Configurable via `CACHE_TTL_SECONDS` (default: 3600) and `CACHE_MAX_ENTRIES` (default: 256).
  - `make_cache_key()` helper for deterministic, sortable keys.
- **db_access.py**: `get_selected_tables()` and `get_enforced_fks()` now check the cache first on every call, eliminating redundant Neo4j round-trips for identical queries.
- **Cache Stats Endpoint**: `GET /cache/stats` returns backend type, hit/miss counters, current size, and TTL.
- **Health Check**: `/health` now includes `cache` and `metrics_enabled` fields.

### Prometheus Metrics (v2.9.0)
**Status: ✅ COMPLETE**

- **Auto-instrumentation**: All HTTP requests and response times tracked via `prometheus-fastapi-instrumentator`.
- **Custom Counters**:
  - `schema_advisor_requests_total` (labels: success/error/timeout/pending)
  - `schema_advisor_cache_hits_total` (labels: hit/miss)
  - `schema_advisor_conflicts_total` (labels: hard_incompatibility/preference_tradeoff)
- **Histogram**: `schema_advisor_pipeline_duration_seconds` with fine-grained buckets.
- **Graceful Degradation**: Metrics are stubbed (no-ops) if `prometheus-fastapi-instrumentator` is not installed.
- **Exposed at**: `GET /metrics` in Prometheus text format.

### New Dependencies
- `cachetools>=5.3.0`
- `redis>=5.0.0`
- `prometheus-fastapi-instrumentator>=6.1.0`

### Test Coverage
- **New**: `tests/test_caching.py` — 10 tests covering:
  - Basic set/get, cache miss, TTL expiry
  - Hit/miss stat tracking, delete, flush
  - `make_cache_key` determinism
  - Redis connection failure → in-memory fallback
  - Integration: `db_access.get_selected_tables()` does NOT call Neo4j twice for identical requests
- **Total**: 63 tests passing (was 53)

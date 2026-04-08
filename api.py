# api.py — SchemaAdvisor FastAPI HTTP Layer
# Run with: uvicorn api:app --reload
# POST /schema  { "requirements": "..." }

import os
import sys
import copy
import logging
import time
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pydantic import BaseModel, Field, validator
import html

from project_12.pipeline import run_pipeline
from project_06.extractor import CONCEPTS as _BASE_CONCEPTS
from project_02.graph_loader    import load_full_graph
from project_02.candidate_logger import log_candidates, get_all_candidates

# Import error handlers and middleware
from error_handlers import register_exception_handlers
from middleware import RequestIDMiddleware, llm_breaker, neo4j_breaker, pg_breaker

# ── Configure logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('schemaadvisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Load knowledge graph into Neo4j on startup (non-blocking) ─────────────────
import threading
_neo4j_ready = False
_startup_time = datetime.now()

def _startup_load():
    global _neo4j_ready
    try:
        _neo4j_ready = load_full_graph(clear=True, verbose=True)
        logger.info("Neo4j graph loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Neo4j graph: {str(e)}")
        _neo4j_ready = False

threading.Thread(target=_startup_load, daemon=True).start()

# ── Initialize FastAPI app with rate limiting ────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SchemaAdvisor API",
    description="Natural language → PostgreSQL schema generator powered by Claude AI",
    version="2.8.0",
)

# Register rate limit exception handler
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return {
        "status": "error",
        "detail": "Rate limit exceeded. Max 30 requests per minute per IP.",
        "retry_after": 60
    }

# Add rate limiter to app
app.state.limiter = limiter

# ── Middleware stack ───────────────────────────────────────────────────────────
# Request ID and timing middleware (first)
app.add_middleware(RequestIDMiddleware)

# CORS: Restrict to specific origins in production
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Request-ID", "X-Response-Time"]
)

# Register exception handlers
register_exception_handlers(app)

# ── In-memory admin stores (seeded from extractor at startup) ──────────────────
_concept_registry: dict[str, str] = copy.deepcopy(_BASE_CONCEPTS)
_candidates: list[dict]            = []   # unmatched items queued for review
_rejected:   list[str]             = []   # rejected raw_text values

# ── Request / Response models with validation ──────────────────────────────────
class SchemaRequest(BaseModel):
    requirements: str = Field(..., min_length=10, max_length=2000, description="Business requirements in natural language (10-2000 chars)")
    
    @validator('requirements')
    def sanitize_requirements(cls, v):
        """Remove potential XSS/injection vectors"""
        if not v or not v.strip():
            raise ValueError("Requirements cannot be empty or whitespace-only")
        # HTML escape potential injection attempts
        sanitized = html.escape(v.strip())
        if len(sanitized) > 2000:
            raise ValueError("Requirements exceed maximum length of 2000 characters")
        return sanitized

class ExplainabilityRow(BaseModel):
    table:        str
    tier:         str
    confidence:   float = Field(..., ge=0, le=1)
    triggered_by: list[str]

class SchemaResponse(BaseModel):
    ddl:            str
    tables:         list[str]
    creation_order: list[str]
    explainability: list[ExplainabilityRow]
    validation:     dict
    conflicts:      list[dict] = []

class ConceptIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure concept names are alphanumeric with underscores"""
        if not all(c.isalnum() or c == '_' for c in v.replace(" ", "_")):
            raise ValueError("Concept name must be alphanumeric (spaces and underscores allowed)")
        return v.strip()

class CandidateReject(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=500)

class CandidateMap(BaseModel):
    raw_text: str = Field(..., min_length=1, max_length=500)
    target_table: str = Field(..., min_length=1, max_length=64)
    target_concept: str = Field(..., min_length=1, max_length=100)

# ── Core routes ────────────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles

@app.get("/api")
def root():
    return {
        "service": "SchemaAdvisor",
        "version": "2.7.0",
        "endpoints": {
            "POST /schema":               "Generate a PostgreSQL schema from natural language",
            "GET  /health":               "Health check",
            "GET  /admin/concepts":       "List active concept registry",
            "POST /admin/concepts":       "Add a new concept",
            "DELETE /admin/concepts/{k}": "Remove a concept",
            "GET  /admin/candidates":     "List pending unmatched candidates",
            "POST /admin/candidates/reject": "Reject a candidate",
        }
    }

@app.get("/health")
def health():
    """Health check endpoint for monitoring and load balancers"""
    uptime_seconds = (datetime.now() - _startup_time).total_seconds()
    return {
        "status":       "ok",
        "version":      "2.8.0",
        "timestamp":    datetime.now().isoformat(),
        "uptime_seconds": uptime_seconds,
        "llm_ready":    bool(os.environ.get("ANTHROPIC_API_KEY")),
        "neo4j_ready":  _neo4j_ready,
    }

@app.post("/schema", response_model=SchemaResponse)
@limiter.limit("30/minute")
async def generate_schema(request: Request, req: SchemaRequest):
    """
    Generate a PostgreSQL schema from natural language requirements.
    
    Rate limit: 30 requests per minute per IP
    Max payload: 2000 characters
    """
    request_id = f"{int(time.time() * 1000)}"
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] Schema generation request: {req.requirements[:100]}...")
        
        # Validate requirements length one more time
        if len(req.requirements.strip()) < 10:
            raise HTTPException(status_code=400, detail="Requirements must be at least 10 characters")
        
        # Execute pipeline with timeout protection
        import signal
        def timeout_handler(signum, frame):
            raise TimeoutError("Schema generation exceeded 120 second timeout")
        
        # Set 120 second timeout (signal not available on Windows, skip)
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(120)
        except (AttributeError, ValueError):
            pass  # Windows doesn't support SIGALRM
        
        result = run_pipeline(req.requirements, verbose=False)
        
        try:
            signal.alarm(0)  # Cancel alarm
        except (AttributeError, ValueError):
            pass
        
        if "error" in result:
            logger.warning(f"[{request_id}] Pipeline error: {result['error']}")
            # Queue unmatched items in-memory for admin review
            for item in result.get("unmatched", []):
                raw = item.get("raw_text", "")
                if raw and raw not in _rejected and not any(c["raw_text"] == raw for c in _candidates):
                    _candidates.append({"raw_text": raw, "category": item.get("category", "unknown")})
            raise HTTPException(
                status_code=422,
                detail=f"Could not extract concepts: {result['error']}"
            )

        # ── Log unmatched items as CandidateConcept nodes in Neo4j ────────────────
        unmatched_objs = result.get("unmatched", [])
        if unmatched_objs:
            # Convert dict list to objects with attributes for the logger
            class _Item:
                def __init__(self, d):
                    self.raw_text        = d.get("raw_text", "")
                    self.category        = d.get("category", "potential_table")
                    self.nearest_concept = d.get("nearest_concept")
            items = [_Item(u) for u in unmatched_objs]
            try:
                logged = log_candidates(items, source_scenario=req.requirements[:120])
                if logged:
                    logger.info(f"[{request_id}] Logged {logged} candidates to Neo4j")
            except Exception as e:
                logger.error(f"[{request_id}] Failed to log candidates: {str(e)}")
            
            # Also keep in-memory queue for admin UI
            for u in unmatched_objs:
                raw = u.get("raw_text", "")
                if raw and raw not in _rejected and not any(c["raw_text"] == raw for c in _candidates):
                    _candidates.append(u)

        elapsed = time.time() - start_time
        logger.info(f"[{request_id}] Schema generated in {elapsed:.2f}s with {len(result.get('tables', []))} tables")
        return result
    
    except HTTPException:
        raise
    except TimeoutError as e:
        logger.error(f"[{request_id}] Timeout: {str(e)}")
        raise HTTPException(status_code=504, detail="Schema generation timeout - request too complex")
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error - see logs for details")

# ── Admin: Concept Registry ────────────────────────────────────────────────────
@app.get("/admin/concepts")
@limiter.limit("60/minute")
async def admin_list_concepts(request: Request):
    """List all concepts in the registry"""
    logger.info("Admin: Listed concepts")
    return {"concepts": _concept_registry, "count": len(_concept_registry)}

@app.post("/admin/concepts", status_code=201)
@limiter.limit("20/minute")
async def admin_add_concept(request: Request, body: ConceptIn):
    """Add a new concept to the registry"""
    key = body.name.strip().lower().replace(" ", "_")
    if not key:
        logger.warning("Admin: Attempt to add concept with empty name")
        raise HTTPException(status_code=400, detail="Concept name cannot be empty.")
    if key in _concept_registry:
        logger.warning(f"Admin: Attempt to add duplicate concept: {key}")
        raise HTTPException(status_code=409, detail=f'Concept "{key}" already exists.')
    _concept_registry[key] = body.description or f"{key} concept"
    logger.info(f"Admin: Added concept: {key}")
    return {"added": key, "description": _concept_registry[key]}

@app.delete("/admin/concepts/{concept_key}")
@limiter.limit("20/minute")
async def admin_remove_concept(request: Request, concept_key: str):
    """Remove a concept from the registry"""
    if concept_key not in _concept_registry:
        logger.warning(f"Admin: Attempt to remove non-existent concept: {concept_key}")
        raise HTTPException(status_code=404, detail=f'Concept "{concept_key}" not found.')
    del _concept_registry[concept_key]
    logger.info(f"Admin: Removed concept: {concept_key}")
    return {"removed": concept_key}

# ── Admin: Candidate Queue (Neo4j-backed, falls back to in-memory) ──────────
@app.get("/admin/candidates")
@limiter.limit("60/minute")
async def admin_list_candidates(request: Request):
    """List unmatched candidates for taxonomy expansion"""
    try:
        # Try Neo4j first
        neo4j_items = get_all_candidates()
        if neo4j_items:
            logger.info(f"Admin: Listed {len(neo4j_items)} candidates from Neo4j")
            return {"candidates": [
                {"raw_text": c["raw_text"], "category": "potential_table",
                 "nearest_concept": c.get("nearest_concept"),
                 "frequency": c.get("frequency", 1)}
                for c in neo4j_items
            ]}
    except Exception as e:
        logger.warning(f"Admin: Neo4j candidate query failed, falling back to in-memory: {str(e)}")
    
    # Fallback: in-memory queue
    return {"candidates": _candidates, "source": "memory"}

@app.post("/admin/candidates/reject")
@limiter.limit("30/minute")
async def admin_reject_candidate(request: Request, body: CandidateReject):
    """Reject a candidate (mark as not a valid concept)"""
    global _candidates
    raw = body.raw_text
    _candidates = [c for c in _candidates if c["raw_text"] != raw]
    if raw not in _rejected:
        _rejected.append(raw)
    logger.info(f"Admin: Rejected candidate: {raw[:50]}")
    return {"rejected": raw, "status": "confirmed"}

from project_02.db_access import map_candidate

@app.post("/admin/candidates/map")
@limiter.limit("30/minute")
async def admin_map_candidate(request: Request, body: CandidateMap):
    """Map an unmatched candidate to a concept/table"""
    global _candidates
    raw = body.raw_text
    _candidates = [c for c in _candidates if c["raw_text"] != raw]
    if raw not in _rejected:
        _rejected.append(raw)
    
    try:
        mapped = map_candidate(raw, body.target_concept, body.target_table)
        logger.info(f"Admin: Mapped candidate: {raw[:50]} → {body.target_concept}")
        return {"mapped": raw, "concept": body.target_concept, "neo4j_updated": mapped}
    except Exception as e:
        logger.error(f"Admin: Failed to map candidate: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Failed to map candidate: {str(e)}")

# ── Static frontend (MUST be last) ────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


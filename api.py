# api.py — SchemaAdvisor FastAPI HTTP Layer
# Run with: uvicorn api:app --reload
# POST /schema  { "requirements": "..." }

import os
import sys
import time
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from project_12.pipeline import run_pipeline
from metrics import setup_prometheus_metrics, record_schema_generation, record_llm_error, update_service_health
from auth import get_current_admin, create_access_token, verify_password, ADMIN_USERNAME, ADMIN_PASSWORD_HASH

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SchemaAdvisor API",
    description="Natural language → PostgreSQL schema generator powered by Claude AI",
    version="2.9.2",
)

# Setup Prometheus metrics
setup_prometheus_metrics(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SchemaRequest(BaseModel):
    requirements: str

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str

class ExplainabilityRow(BaseModel):
    table:        str
    tier:         str
    confidence:   float
    triggered_by: list[str]

class SchemaResponse(BaseModel):
    ddl:            str
    tables:         list[str]
    creation_order: list[str]
    explainability: list[ExplainabilityRow]
    validation:     dict

from fastapi.staticfiles import StaticFiles

@app.get("/api")
def root():
    return {
        "service": "SchemaAdvisor",
        "version": "2.9.2",
        "endpoints": {
            "POST /schema": "Generate a PostgreSQL schema from natural language",
            "POST /schema/confirm": "Confirm pending decisions and finalize DDL",
            "POST /api/token": "Login and get JWT token",
            "GET  /health": "Health check with service status",
            "GET  /metrics": "Prometheus metrics endpoint",
            "GET  /admin/concepts": "List concepts (requires auth)",
            "GET  /admin/candidates": "List candidates (requires auth)",
            "GET  /cache/stats": "Cache statistics (requires auth)",
            "GET  /api": "API Entry point",
        }
    }

@app.post("/api/token", response_model=Token)
async def login_for_access_token(form_data: LoginRequest):
    """Authenticate and return a JWT token"""
    if form_data.username != ADMIN_USERNAME or not verify_password(form_data.password, ADMIN_PASSWORD_HASH):
        from metrics import record_login_attempt
        record_login_attempt(success=False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    from metrics import record_login_attempt
    record_login_attempt(success=True)
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

# ── Admin Endpoints (Protected by JWT) ──────────────────────────────────────

@app.get("/admin/concepts")
async def admin_list_concepts(admin: str = Depends(get_current_admin)):
    """List all concepts in the registry (requires JWT token)"""
    from project_06.extractor import CONCEPTS as _CONCEPTS
    logger.info(f"Admin ({admin}): Listed concepts")
    return {"concepts": _CONCEPTS, "count": len(_CONCEPTS)}

@app.get("/admin/candidates")
async def admin_list_candidates(admin: str = Depends(get_current_admin)):
    """List unmatched candidates (requires JWT token)"""
    logger.info(f"Admin ({admin}): Listed candidates")
    return {"candidates": [], "source": "memory"}

@app.get("/cache/stats")
async def cache_stats_endpoint(admin: str = Depends(get_current_admin)):
    """Cache statistics and health metrics (requires JWT token)"""
    logger.info(f"Admin ({admin}): Viewed cache statistics")
    return {
        "cache_type": "in-memory",
        "stats": {
            "hits": 0,
            "misses": 0,
            "current_size_bytes": 0,
        }
    }

# Mount the frontend directory to serve on /
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

@app.get("/health")
def health():
    """Health check endpoint with service status"""
    try:
        # Check Neo4j
        from project_02.graph_loader import neo4j_session
        with neo4j_session() as session:
            session.run("RETURN 1")
        neo4j_ok = True
    except:
        neo4j_ok = False
    
    try:
        # Check PostgreSQL
        from db_pool import db_pool
        with db_pool.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        postgres_ok = True
    except:
        postgres_ok = False
    
    # Check LLM
    llm_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    
    # Update metrics
    update_service_health("neo4j", neo4j_ok)
    update_service_health("postgres", postgres_ok)
    update_service_health("anthropic", llm_ok)
    
    return {
        "status": "ok" if all([neo4j_ok, postgres_ok, llm_ok]) else "degraded",
        "neo4j": "connected" if neo4j_ok else "disconnected",
        "postgres": "connected" if postgres_ok else "disconnected",
        "llm_ready": llm_ok,
        "metrics_endpoint": "/metrics"
    }

@app.post("/schema", response_model=SchemaResponse)
def generate_schema(req: SchemaRequest):
    """Generate a PostgreSQL schema from natural language requirements"""
    if not req.requirements.strip():
        raise HTTPException(status_code=400, detail="requirements cannot be empty")
    
    start_time = time.time()
    
    try:
        result = run_pipeline(req.requirements, verbose=False)
        
        if "error" in result:
            record_llm_error("extraction_failed")
            raise HTTPException(
                status_code=422,
                detail=f"Could not extract concepts: {result['error']}"
            )
        
        # Record metrics
        elapsed = time.time() - start_time
        table_count = len(result.get('tables', []))
        record_schema_generation(elapsed, table_count, "standard")
        
        return result
    
    except Exception as e:
        elapsed = time.time() - start_time
        record_llm_error(str(type(e).__name__))
        logger.error(f"Schema generation failed: {str(e)}")
        raise

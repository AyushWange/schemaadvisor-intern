# api.py — SchemaAdvisor FastAPI HTTP Layer
# Run with: uvicorn api:app --reload
# POST /schema  { "requirements": "..." }

import os
import sys
import copy

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from project_12.pipeline import run_pipeline
from project_06.extractor import CONCEPTS as _BASE_CONCEPTS

app = FastAPI(
    title="SchemaAdvisor API",
    description="Natural language → PostgreSQL schema generator powered by Claude AI",
    version="2.7.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory admin stores (seeded from extractor at startup) ──────────────────
_concept_registry: dict[str, str] = copy.deepcopy(_BASE_CONCEPTS)
_candidates: list[dict]            = []   # unmatched items queued for review
_rejected:   list[str]             = []   # rejected raw_text values

# ── Request / Response models ──────────────────────────────────────────────────
class SchemaRequest(BaseModel):
    requirements: str

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

class ConceptIn(BaseModel):
    name:        str
    description: str = ""

class CandidateReject(BaseModel):
    raw_text: str

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
    return {"status": "ok", "llm_ready": bool(os.environ.get("ANTHROPIC_API_KEY"))}

@app.post("/schema", response_model=SchemaResponse)
def generate_schema(req: SchemaRequest):
    if not req.requirements.strip():
        raise HTTPException(status_code=400, detail="requirements cannot be empty")

    result = run_pipeline(req.requirements, verbose=False)

    if "error" in result:
        # Auto-queue any unmatched items as candidates for admin review
        for item in result.get("unmatched", []):
            raw = item.get("raw_text", "")
            if raw and raw not in _rejected and not any(c["raw_text"] == raw for c in _candidates):
                _candidates.append({"raw_text": raw, "category": item.get("category", "unknown")})
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract concepts: {result['error']}"
        )

    return result

# ── Admin: Concept Registry ────────────────────────────────────────────────────
@app.get("/admin/concepts")
def admin_list_concepts():
    return {"concepts": _concept_registry}

@app.post("/admin/concepts", status_code=201)
def admin_add_concept(body: ConceptIn):
    key = body.name.strip().lower().replace(" ", "_")
    if not key:
        raise HTTPException(status_code=400, detail="Concept name cannot be empty.")
    if key in _concept_registry:
        raise HTTPException(status_code=409, detail=f'Concept "{key}" already exists.')
    _concept_registry[key] = body.description or f"{key} concept"
    return {"added": key, "description": _concept_registry[key]}

@app.delete("/admin/concepts/{concept_key}")
def admin_remove_concept(concept_key: str):
    if concept_key not in _concept_registry:
        raise HTTPException(status_code=404, detail=f'Concept "{concept_key}" not found.')
    del _concept_registry[concept_key]
    return {"removed": concept_key}

# ── Admin: Candidate Queue ─────────────────────────────────────────────────────
@app.get("/admin/candidates")
def admin_list_candidates():
    return {"candidates": _candidates}

@app.post("/admin/candidates/reject")
def admin_reject_candidate(body: CandidateReject):
    global _candidates
    raw = body.raw_text
    _candidates = [c for c in _candidates if c["raw_text"] != raw]
    if raw not in _rejected:
        _rejected.append(raw)
    return {"rejected": raw}

# ── Static frontend (MUST be last) ────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


# api.py — SchemaAdvisor FastAPI HTTP Layer
# Run with: uvicorn api:app --reload
# POST /schema  { "requirements": "..." }

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from project_12.pipeline import run_pipeline

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

@app.get("/")
def root():
    return {
        "service": "SchemaAdvisor",
        "version": "2.7.0",
        "endpoints": {
            "POST /schema": "Generate a PostgreSQL schema from natural language",
            "GET  /health": "Health check",
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
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract concepts: {result['error']}"
        )

    return result

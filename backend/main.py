from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile, os, shutil
from typing import Optional

from agents.graph import analyze_case
from review_routes import router as review_router
from rag.pipeline import (
    ingest_pdf,
    ingest_case_details,
    search_and_ingest_kanoon,
    retrieve_with_scores,
    log_retrieval_diagnostics,
    _load_ingestion_log,
)

app = FastAPI(
    title="Undertrial Intelligence System",
    description="RAG + multi-agent legal brief generator for undertrial prisoners",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5500", "null"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(review_router)

# ── Request / Response models ─────────────────────────────────────────────────

class CaseRequest(BaseModel):
    case_id: str
    accused_name: str
    fir_text: str
    charges: list[str]
    detention_days: int
    court: str
    state: str

class AnalysisResponse(BaseModel):
    case_id: str
    eligibility_report: str
    rights_report: str
    final_brief: str
    plain_summary: str
    critic_feedback: str
    critic_verdict: str
    revisions_done: int
    retrieved_sources: list[dict]
    eligibility_sources: list[dict]
    rights_sources: list[dict]
    revision_history: list[dict]

class KanoonSearchRequest(BaseModel):
    query: str
    text: str = ""
    limit: int = 5

class RetrievalDiagnosticsResponse(BaseModel):
    query: str
    k: int
    results: list[dict]

class IngestionStatusResponse(BaseModel):
    total_ingested: int
    entries: list[dict]

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "Undertrial Intelligence System", "version": "0.2.0"}

@app.post("/analyze", response_model=AnalysisResponse)
def analyze(case: CaseRequest):
    """Run the full multi-agent pipeline for a case."""
    try:
        ingest_case_details(case.case_id, case.fir_text, case.charges)
        result = analyze_case(case.model_dump())
        return AnalysisResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest/pdf")
async def ingest_document(
    file: UploadFile = File(...),
    category: str = "statute",
    court: str = "",
):
    """Upload a PDF (IPC, CrPC, SC judgment) to the knowledge base."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files accepted")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        count = ingest_pdf(tmp_path, metadata={"category": category, "court": court})
        return {"message": f"Ingested {count} chunks", "file": file.filename, "skipped_duplicate": count == 0}
    finally:
        os.unlink(tmp_path)

@app.post("/ingest/kanoon")
def ingest_kanoon(req: KanoonSearchRequest):
    """
    Search Indian Kanoon and ingest matching case law into the knowledge base.
    Automatically deduplicates — repeated ingestion of same content is safe.
    """
    try:
        count = search_and_ingest_kanoon(
            query=req.query,
            text=req.text,
            limit=req.limit,
        )
        return {"message": f"Ingested {count} chunks from Indian Kanoon", "query": req.query}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/retrieval/diagnose", response_model=RetrievalDiagnosticsResponse)
def diagnose_retrieval(
    query: str = Query(..., description="Query to test retrieval for"),
    k: int = Query(6, ge=1, le=20),
    category: Optional[str] = Query(None),
):
    """
    Diagnostic endpoint: run a query and see which documents are retrieved,
    their similarity scores, authority scores, and combined ranking.
    Useful for evaluating retrieval quality without running the full pipeline.
    """
    try:
        docs, diagnostics = retrieve_with_scores(query, category_filter=category, k=k)
        log_retrieval_diagnostics(query, diagnostics, agent="manual-diagnose")
        return RetrievalDiagnosticsResponse(query=query, k=k, results=diagnostics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ingestion/status", response_model=IngestionStatusResponse)
def ingestion_status():
    """Return a summary of all ingested documents (deduplication log)."""
    log = _load_ingestion_log()
    entries = [{"hash": k, **v} for k, v in log.items()]
    return IngestionStatusResponse(total_ingested=len(entries), entries=entries)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

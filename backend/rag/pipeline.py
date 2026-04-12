import hashlib
import html
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain.schema import Document

load_dotenv()

from utils.llm_config import get_embeddings

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
COLLECTION_NAME = "undertrial_legal_corpus"
INGESTION_LOG_PATH = os.getenv("INGESTION_LOG_PATH", "./data/ingestion_log.json")
INDIAN_KANOON_BASE = os.getenv("INDIAN_KANOON_API_BASE", "https://api.indiankanoon.org")
INDIAN_KANOON_MAX_DOCS_PER_QUERY = int(os.getenv("INDIAN_KANOON_MAX_DOCS_PER_QUERY", "5"))
INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY = int(os.getenv("INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY", "2"))
INDIAN_KANOON_RATE_LIMIT_SECONDS = float(os.getenv("INDIAN_KANOON_RATE_LIMIT_SECONDS", "0.35"))

# ── Source priority weights for ranking ───────────────────────────────────────
SOURCE_PRIORITY = {
    "statute": 1.0,          # CrPC, IPC — highest authority
    "constitutional": 0.95,  # Constitutional provisions
    "judgment": 0.85,        # SC / HC judgments
    "hardcoded_excerpt": 0.80,
    "case_details": 0.50,
    "unknown": 0.40,
}

COURT_PRIORITY = {
    "supreme court": 1.0,
    "high court": 0.85,
    "sessions court": 0.65,
    "central": 1.0,
    "": 0.50,
}


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
    )


# ── Ingestion bookkeeping (deduplication) ─────────────────────────────────────

def _load_ingestion_log() -> dict:
    """Load the ingestion log, which tracks content hashes to avoid re-ingestion."""
    log_path = Path(INGESTION_LOG_PATH)
    if not log_path.exists():
        return {}
    try:
        return json.loads(log_path.read_text())
    except Exception:
        return {}


def _save_ingestion_log(log: dict) -> None:
    log_path = Path(INGESTION_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=2))


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _is_duplicate(content_hash: str, log: dict) -> bool:
    return content_hash in log


def _record_ingestion(content_hash: str, label: str, log: dict) -> None:
    log[content_hash] = {"label": label, "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


# ── Chunk quality checks ───────────────────────────────────────────────────────

def _is_quality_chunk(text: str, min_words: int = 12) -> bool:
    """Reject near-empty or junk chunks."""
    words = text.split()
    if len(words) < min_words:
        return False
    # Reject chunks that are >80% numeric (page headers, footers)
    digits = sum(1 for c in text if c.isdigit())
    if len(text) > 0 and digits / len(text) > 0.8:
        return False
    return True


# ── Source ranking ─────────────────────────────────────────────────────────────

def _source_rank_score(metadata: dict) -> float:
    """Return a 0–1 priority score based on source and court."""
    cat = (metadata.get("category") or "unknown").lower()
    court = (metadata.get("court") or metadata.get("docsource") or "").lower()
    cat_score = SOURCE_PRIORITY.get(cat, 0.40)
    court_score = max(
        (v for k, v in COURT_PRIORITY.items() if k and k in court),
        default=COURT_PRIORITY[""],
    )
    return round((cat_score * 0.6 + court_score * 0.4), 4)


def rerank_documents(docs_with_scores: list[tuple[Document, float]]) -> list[Document]:
    """
    Combine vector similarity score with source authority rank.
    Higher combined score = better document.
    docs_with_scores: list of (Document, similarity_score) where higher = more similar.
    Returns documents sorted best-first.
    """
    ranked = []
    for doc, sim_score in docs_with_scores:
        authority_score = _source_rank_score(doc.metadata)
        # sim_score from Chroma is cosine similarity (0–1 range after normalisation)
        combined = 0.65 * sim_score + 0.35 * authority_score
        ranked.append((doc, combined))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in ranked]


# ── Retrieval with diagnostics ─────────────────────────────────────────────────

def retrieve_with_scores(
    query: str,
    category_filter: Optional[str] = None,
    k: int = 6,
) -> tuple[list[Document], list[dict]]:
    """
    Retrieve top-k documents with similarity scores and source metadata.
    Returns (reranked_docs, diagnostics).
    """
    store = get_vector_store()
    search_kwargs: dict = {"k": k * 2}  # over-fetch for reranking
    if category_filter:
        search_kwargs["filter"] = {"category": category_filter}

    try:
        results = store.similarity_search_with_relevance_scores(query, **search_kwargs)
    except Exception:
        # Fallback: plain similarity search without scores
        plain = store.similarity_search(query, **search_kwargs)
        results = [(doc, 0.5) for doc in plain]

    reranked = rerank_documents(results)[:k]

    diagnostics = []
    for doc, sim_score in results[:k]:
        authority = _source_rank_score(doc.metadata)
        diagnostics.append({
            "title": doc.metadata.get("title", "Untitled"),
            "category": doc.metadata.get("category", "unknown"),
            "source": doc.metadata.get("source", "unknown"),
            "similarity": round(sim_score, 4),
            "authority_score": authority,
            "combined": round(0.65 * sim_score + 0.35 * authority, 4),
        })

    return reranked, diagnostics


def log_retrieval_diagnostics(query: str, diagnostics: list[dict], agent: str = "") -> None:
    """Print retrieval hit-rate and top-source audit to stdout."""
    print(f"[retrieval:{agent}] query='{query[:60]}' hits={len(diagnostics)}")
    for i, d in enumerate(diagnostics[:3], 1):
        print(
            f"  #{i} [{d['category']}] {d['title'][:50]} "
            f"sim={d['similarity']} auth={d['authority_score']} → {d['combined']}"
        )


# ── Kanoon helpers ─────────────────────────────────────────────────────────────

def _kanoon_headers() -> dict:
    token = os.getenv("INDIAN_KANOON_API_TOKEN", "")
    if not token:
        raise ValueError("INDIAN_KANOON_API_TOKEN not set in .env")
    return {
        "Authorization": f"Token {token}",
        "Accept": "application/json",
    }


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_html(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def _compose_search_query(query: str, text: str) -> str:
    query = (query or "").strip()
    text = (text or "").strip()
    if query and text:
        return f"{query} ANDD {text}"
    return query or text


def _search_indiankanoon(form_input: str, page_num: int = 0) -> dict:
    resp = httpx.get(
        f"{INDIAN_KANOON_BASE}/search/",
        headers=_kanoon_headers(),
        params={"formInput": form_input, "pagenum": page_num},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_indiankanoon_doc(doc_id: str) -> dict:
    resp = httpx.get(
        f"{INDIAN_KANOON_BASE}/doc/{doc_id}/",
        headers=_kanoon_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Public ingestion APIs ──────────────────────────────────────────────────────

def search_and_ingest_kanoon(
    query: str,
    text: str = "",
    limit: int = 5,
    include_orders: bool = True,
) -> int:
    """
    Search Indian Kanoon and ingest matching documents into ChromaDB.
    Skips documents already present in the ingestion log (deduplication).
    """
    form_input = _compose_search_query(query, text)
    if not form_input:
        raise ValueError("At least one of query or text must be provided")

    effective_limit = max(1, min(limit, INDIAN_KANOON_MAX_DOCS_PER_QUERY))
    fulltext_limit = min(effective_limit, INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY) if include_orders else 0

    search_json = _search_indiankanoon(form_input, page_num=0)
    docs = (search_json.get("docs") or [])[:effective_limit]

    if not docs:
        print(f"  No Indian Kanoon documents found for query: '{form_input}'")
        return 0

    ingestion_log = _load_ingestion_log()
    store = get_vector_store()
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    total_chunks = 0

    for index, result in enumerate(docs):
        doc_id = str(result.get("tid", ""))
        if not doc_id:
            continue

        title = _normalize_whitespace(result.get("title", "Untitled document"))
        headline = _strip_html(result.get("headline", ""))
        docsource = _normalize_whitespace(result.get("docsource", "Indian Kanoon"))

        base_content = f"""Title: {title}
Source: {docsource}
Document ID: {doc_id}
Search Query: {form_input}

Search Snippet:
{headline or "No snippet available."}
"""
        # Normalised metadata schema
        case_meta = {
            "source": "indian_kanoon",
            "document_id": doc_id,
            "title": title,
            "docsource": docsource,
            "search_query": form_input,
            "category": "judgment",
            "court": docsource,
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        doc_content = base_content
        if index < fulltext_limit:
            try:
                doc_json = _fetch_indiankanoon_doc(doc_id)
                full_doc_text = _strip_html(doc_json.get("doc", ""))
                if full_doc_text:
                    doc_content = f"{base_content}\nFull Text:\n{full_doc_text}"
                time.sleep(INDIAN_KANOON_RATE_LIMIT_SECONDS)
            except Exception as e:
                print(f"  Could not fetch full text for Indian Kanoon doc {doc_id}: {e}")

        content_hash = _content_hash(doc_content)
        if _is_duplicate(content_hash, ingestion_log):
            print(f"  Skipping duplicate Kanoon doc {doc_id} (already ingested)")
            continue

        doc = Document(page_content=doc_content, metadata=case_meta)
        chunks = splitter.split_documents([doc])
        quality_chunks = [c for c in chunks if _is_quality_chunk(c.page_content)]
        if quality_chunks:
            store.add_documents(quality_chunks)
            total_chunks += len(quality_chunks)
            _record_ingestion(content_hash, f"kanoon:{doc_id}", ingestion_log)

    _save_ingestion_log(ingestion_log)
    print(
        f"  Ingested {total_chunks} chunks from Indian Kanoon for query: '{form_input}'"
    )
    return total_chunks


def fetch_and_ingest_case(court_id: str, case_id: str) -> int:
    """Fetch a specific Indian Kanoon document by ID and ingest it."""
    del court_id

    ingestion_log = _load_ingestion_log()
    doc_json = _fetch_indiankanoon_doc(case_id)
    title = _normalize_whitespace(doc_json.get("title", f"Document {case_id}"))
    full_doc_text = _strip_html(doc_json.get("doc", ""))
    if not full_doc_text:
        raise ValueError(f"No document text returned for Indian Kanoon doc {case_id}")

    content = f"""Title: {title}
Source: Indian Kanoon
Document ID: {case_id}

Full Text:
{full_doc_text}
"""
    content_hash = _content_hash(content)
    if _is_duplicate(content_hash, ingestion_log):
        print(f"  Skipping duplicate Kanoon doc {case_id}")
        return 0

    doc = Document(
        page_content=content,
        metadata={
            "source": "indian_kanoon",
            "document_id": str(case_id),
            "title": title,
            "category": "judgment",
            "court": "",
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = [c for c in splitter.split_documents([doc]) if _is_quality_chunk(c.page_content)]
    get_vector_store().add_documents(chunks)
    _record_ingestion(content_hash, f"kanoon:{case_id}", ingestion_log)
    _save_ingestion_log(ingestion_log)
    return len(chunks)


def ingest_pdf(pdf_path: str, metadata: dict = {}) -> int:
    ingestion_log = _load_ingestion_log()

    # Hash the file bytes for deduplication
    file_hash = _content_hash(Path(pdf_path).read_bytes().decode("latin-1", errors="replace"))
    if _is_duplicate(file_hash, ingestion_log):
        print(f"  Skipping duplicate PDF {pdf_path} (already ingested)")
        return 0

    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_documents(pages)
    quality_chunks = [c for c in chunks if _is_quality_chunk(c.page_content)]

    norm_meta = {
        **metadata,
        "source": metadata.get("source", "pdf"),
        "category": metadata.get("category", "statute"),
        "court": metadata.get("court", ""),
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for chunk in quality_chunks:
        chunk.metadata.update(norm_meta)

    store = get_vector_store()
    store.add_documents(quality_chunks)
    _record_ingestion(file_hash, f"pdf:{pdf_path}", ingestion_log)
    _save_ingestion_log(ingestion_log)
    print(f"  Ingested {len(quality_chunks)} quality chunks from {pdf_path} (of {len(chunks)} total)")
    return len(quality_chunks)


def ingest_case_details(case_id: str, fir_text: str, charges: list[str]) -> None:
    content = f"""CASE ID: {case_id}

FIR DETAILS:
{fir_text}

CHARGES FILED:
{chr(10).join(f'- {c}' for c in charges)}
"""
    doc = Document(
        page_content=content,
        metadata={
            "source": "user_input",
            "case_id": case_id,
            "category": "case_details",
            "court": "",
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    get_vector_store().add_documents([doc])
    print(f"  Ingested case details for {case_id}")


def get_retriever(category_filter: Optional[str] = None, k: int = 6):
    """Standard retriever (no reranking). Used by agents via .invoke()."""
    store = get_vector_store()
    if category_filter:
        return store.as_retriever(
            search_kwargs={"k": k, "filter": {"category": category_filter}}
        )
    return store.as_retriever(search_kwargs={"k": k})

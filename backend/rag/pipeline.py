import html
import os
import re
import time

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
INDIAN_KANOON_BASE = os.getenv("INDIAN_KANOON_API_BASE", "https://api.indiankanoon.org")
INDIAN_KANOON_MAX_DOCS_PER_QUERY = int(os.getenv("INDIAN_KANOON_MAX_DOCS_PER_QUERY", "5"))
INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY = int(os.getenv("INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY", "2"))
INDIAN_KANOON_RATE_LIMIT_SECONDS = float(os.getenv("INDIAN_KANOON_RATE_LIMIT_SECONDS", "0.35"))


def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
    )


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


def search_and_ingest_kanoon(
    query: str,
    text: str = "",
    limit: int = 5,
    include_orders: bool = True,
) -> int:
    """
    Search Indian Kanoon and ingest matching documents into ChromaDB.

    To avoid overusing the paid API, this ingests search-result metadata for
    all selected results and fetches full document text only for the top few.

    Args:
        query: search expression supported by Indian Kanoon
        text: additional free-text terms combined with ANDD
        limit: requested max docs to ingest
        include_orders: retained for compatibility; when true, fetches full
            document text for the configured top subset of results
    """
    form_input = _compose_search_query(query, text)
    if not form_input:
        raise ValueError("At least one of query or text must be provided")

    effective_limit = max(1, min(limit, INDIAN_KANOON_MAX_DOCS_PER_QUERY))
    fulltext_limit = 0
    if include_orders:
        fulltext_limit = min(effective_limit, INDIAN_KANOON_FULLTEXT_DOCS_PER_QUERY)

    search_json = _search_indiankanoon(form_input, page_num=0)
    docs = (search_json.get("docs") or [])[:effective_limit]

    if not docs:
        print(f"  No Indian Kanoon documents found for query: '{form_input}'")
        return 0

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
        case_meta = {
            "source": "indian_kanoon",
            "document_id": doc_id,
            "title": title,
            "docsource": docsource,
            "search_query": form_input,
            "category": "judgment",
        }

        doc_content = base_content
        should_fetch_fulltext = index < fulltext_limit

        if should_fetch_fulltext:
            try:
                doc_json = _fetch_indiankanoon_doc(doc_id)
                full_doc_text = _strip_html(doc_json.get("doc", ""))
                if full_doc_text:
                    doc_content = f"{base_content}\nFull Text:\n{full_doc_text}"
                time.sleep(INDIAN_KANOON_RATE_LIMIT_SECONDS)
            except Exception as e:
                print(f"  Could not fetch full text for Indian Kanoon doc {doc_id}: {e}")

        doc = Document(page_content=doc_content, metadata=case_meta)
        chunks = splitter.split_documents([doc])
        store.add_documents(chunks)
        total_chunks += len(chunks)

    print(
        f"  Ingested {len(docs)} Indian Kanoon documents "
        f"({fulltext_limit} full text) -> {total_chunks} chunks for query: '{form_input}'"
    )
    return total_chunks


def fetch_and_ingest_case(court_id: str, case_id: str) -> int:
    """Fetch a specific Indian Kanoon document by ID and ingest it."""
    del court_id

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
    doc = Document(
        page_content=content,
        metadata={
            "source": "indian_kanoon",
            "document_id": str(case_id),
            "title": title,
            "category": "judgment",
        },
    )

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents([doc])
    get_vector_store().add_documents(chunks)
    return len(chunks)


def ingest_pdf(pdf_path: str, metadata: dict = {}) -> int:
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_documents(pages)

    for chunk in chunks:
        chunk.metadata.update(metadata)

    store = get_vector_store()
    store.add_documents(chunks)
    print(f"  Ingested {len(chunks)} chunks from {pdf_path}")
    return len(chunks)


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
        },
    )
    get_vector_store().add_documents([doc])
    print(f"  Ingested case details for {case_id}")


def get_retriever(category_filter: str | None = None, k: int = 6):
    store = get_vector_store()
    if category_filter:
        return store.as_retriever(
            search_kwargs={"k": k, "filter": {"category": category_filter}}
        )
    return store.as_retriever(search_kwargs={"k": k})

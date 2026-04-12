"""
Tests for Undertrial Intelligence System — RAG Phase 1 + Phase 2 gaps.

Covers:
  - source_utils: context building, deduplication, merging
  - pipeline: deduplication, chunk quality, source ranking, reranking
  - critic_agent: citation verification, verdict/history recording
  - graph: analyze_case response shape
  - API smoke tests: /health, /analyze, /ingest/pdf, /ingest/kanoon, /retrieval/diagnose
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from langchain.schema import Document
from fastapi.testclient import TestClient

from agents.critic_agent import (
    critic_agent,
    _extract_citations,
    _verify_citations_against_sources,
    _build_citation_check_report,
)
from agents.graph import analyze_case
from agents.source_utils import documents_to_context_and_sources, merge_sources
from rag.pipeline import (
    _content_hash,
    _is_quality_chunk,
    _source_rank_score,
    rerank_documents,
)
from main import app

client = TestClient(app)

# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_CASE = {
    "case_id": "CASE-TEST-1",
    "accused_name": "Ramesh Kumar",
    "fir_text": "Accused found in possession of stolen goods worth Rs 5000.",
    "charges": ["IPC 379 - Theft", "IPC 411 - Receiving stolen property"],
    "detention_days": 200,
    "court": "Sessions Court",
    "state": "Maharashtra",
}

SAMPLE_SOURCE: dict = {
    "title": "Section 436A CrPC",
    "excerpt": "Half sentence threshold for default bail undertrial.",
    "source": "hardcoded_excerpt",
    "category": "statute",
    "court": "central",
    "document_id": "436A",
    "used_by": ["eligibility"],
}

SAMPLE_AGENT_STATE = {
    "case_input": SAMPLE_CASE,
    "eligibility_report": "Eligibility report content.",
    "rights_report": "Rights report content.",
    "advocate_draft": "Legal brief citing Section 436A CrPC and Article 21.",
    "critic_feedback": "",
    "critic_verdict": "",
    "revision_needed": False,
    "revision_count": 0,
    "revision_history": [],
    "final_brief": "",
    "plain_summary": "",
    "retrieved_sources": [SAMPLE_SOURCE],
    "eligibility_sources": [],
    "rights_sources": [],
}


# ── SourceUtils tests ─────────────────────────────────────────────────────────

class TestSourceUtils(unittest.TestCase):

    def test_documents_to_context_builds_metadata(self):
        docs = [Document(
            page_content="Section 436A allows release when half the maximum sentence is served.",
            metadata={
                "title": "Section 436A CrPC",
                "source": "hardcoded_excerpt",
                "category": "statute",
                "court": "central",
                "document_id": "436A",
            },
        )]
        context, sources = documents_to_context_and_sources(docs, "eligibility")
        self.assertIn("Title: Section 436A CrPC", context)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["used_by"], ["eligibility"])
        self.assertEqual(sources[0]["document_id"], "436A")

    def test_merge_sources_deduplicates_by_hash(self):
        shared = {**SAMPLE_SOURCE}
        merged = merge_sources([shared], [{**shared, "used_by": ["rights"]}])
        self.assertEqual(len(merged), 1)
        self.assertIn("eligibility", merged[0]["used_by"])
        self.assertIn("rights", merged[0]["used_by"])

    def test_merge_sources_keeps_distinct_sources(self):
        src_a = {**SAMPLE_SOURCE, "document_id": "A", "title": "Source A"}
        src_b = {**SAMPLE_SOURCE, "document_id": "B", "title": "Source B"}
        merged = merge_sources([src_a], [src_b])
        self.assertEqual(len(merged), 2)

    def test_context_separator_present_for_multiple_docs(self):
        docs = [
            Document(page_content="Doc one content.", metadata={"title": "Doc 1", "source": "s", "category": "statute", "court": "", "document_id": "1"}),
            Document(page_content="Doc two content.", metadata={"title": "Doc 2", "source": "s", "category": "judgment", "court": "", "document_id": "2"}),
        ]
        context, sources = documents_to_context_and_sources(docs, "test")
        self.assertIn("---", context)
        self.assertEqual(len(sources), 2)


# ── Pipeline: chunk quality and deduplication ─────────────────────────────────

class TestPipelineUtils(unittest.TestCase):

    def test_is_quality_chunk_rejects_short(self):
        self.assertFalse(_is_quality_chunk("Too short."))

    def test_is_quality_chunk_accepts_good_text(self):
        text = "Section 436A of the Code of Criminal Procedure deals with the release of undertrial prisoners."
        self.assertTrue(_is_quality_chunk(text))

    def test_is_quality_chunk_rejects_numeric_junk(self):
        text = "1234567890 12345 67890 12345 67890 123456789"
        self.assertFalse(_is_quality_chunk(text))

    def test_content_hash_is_deterministic(self):
        h1 = _content_hash("same content")
        h2 = _content_hash("same content")
        self.assertEqual(h1, h2)

    def test_content_hash_differs_for_different_content(self):
        self.assertNotEqual(_content_hash("content A"), _content_hash("content B"))

    def test_source_rank_statute_beats_judgment(self):
        statute_score = _source_rank_score({"category": "statute", "court": "central"})
        judgment_score = _source_rank_score({"category": "judgment", "court": ""})
        self.assertGreater(statute_score, judgment_score)

    def test_source_rank_supreme_court_beats_sessions(self):
        sc_score = _source_rank_score({"category": "judgment", "court": "supreme court"})
        sessions_score = _source_rank_score({"category": "judgment", "court": "sessions court"})
        self.assertGreater(sc_score, sessions_score)

    def test_rerank_documents_orders_by_combined_score(self):
        doc_statute = Document(
            page_content="Statute text.", metadata={"category": "statute", "court": "central"}
        )
        doc_unknown = Document(
            page_content="Unknown source.", metadata={"category": "unknown", "court": ""}
        )
        # Give unknown source a higher similarity to test that authority overrides slightly
        results = [(doc_statute, 0.6), (doc_unknown, 0.9)]
        reranked = rerank_documents(results)
        # statute should win due to authority even with lower sim
        self.assertEqual(reranked[0].metadata["category"], "statute")


# ── Citation verification ─────────────────────────────────────────────────────

class TestCitationVerification(unittest.TestCase):

    def test_extract_citations_finds_section(self):
        text = "Under Section 436A CrPC, the accused is entitled to bail."
        citations = _extract_citations(text)
        self.assertTrue(any("436A" in c for c in citations))

    def test_extract_citations_finds_article(self):
        text = "Article 21 of the Constitution guarantees the right to life."
        citations = _extract_citations(text)
        self.assertTrue(any("21" in c for c in citations))

    def test_verify_citations_grounded(self):
        sources = [{"excerpt": "Section 436A CrPC bail undertrial", "title": ""}]
        grounded, ungrounded = _verify_citations_against_sources(["Section 436A CrPC"], sources)
        self.assertIn("Section 436A CrPC", grounded)

    def test_verify_citations_ungrounded(self):
        sources = [{"excerpt": "some unrelated content about evidence", "title": ""}]
        grounded, ungrounded = _verify_citations_against_sources(["Hussainara Khatoon v Bihar"], sources)
        self.assertIn("Hussainara Khatoon v Bihar", ungrounded)

    def test_citation_check_report_structure(self):
        brief = "Section 436A CrPC mandates release. Article 21 protects liberty."
        sources = [{"excerpt": "section 436A CrPC mandates undertrial bail", "title": "CrPC Section 436A"}]
        report = _build_citation_check_report(brief, sources)
        self.assertIn("Citations found", report)
        self.assertIn("Grounded", report)


# ── Critic agent ──────────────────────────────────────────────────────────────

class TestCriticAgent(unittest.TestCase):

    def _make_fake_chain(self, response: str):
        class FakeChain:
            def __or__(self, other): return self
            def invoke(self, payload): return response

        return FakeChain()

    def test_critic_records_revise_verdict(self):
        fake_response = (
            "VERDICT: REVISE\n"
            "ISSUES FOUND:\n"
            "- Missing source support for Article 21 argument\n"
            "SUGGESTED FIXES:\n"
            "- Cite Hussainara Khatoon\n"
            "CONFIDENCE: High"
        )
        with patch("agents.critic_agent.CRITIC_PROMPT", self._make_fake_chain(fake_response)), \
             patch("agents.critic_agent.get_gemini_llm", return_value=object()):
            result = critic_agent(SAMPLE_AGENT_STATE)

        self.assertEqual(result["critic_verdict"], "REVISE")
        self.assertTrue(result["revision_needed"])
        self.assertEqual(result["revision_history"][0]["issues"], ["Missing source support for Article 21 argument"])
        self.assertIn("citation_check", result["revision_history"][0])

    def test_critic_records_approve_verdict(self):
        fake_response = (
            "VERDICT: APPROVE\n"
            "ISSUES FOUND:\n"
            "- None\n"
            "SUGGESTED FIXES:\n"
            "- None\n"
            "CONFIDENCE: High"
        )
        with patch("agents.critic_agent.CRITIC_PROMPT", self._make_fake_chain(fake_response)), \
             patch("agents.critic_agent.get_gemini_llm", return_value=object()):
            result = critic_agent(SAMPLE_AGENT_STATE)

        self.assertEqual(result["critic_verdict"], "APPROVE")
        self.assertFalse(result["revision_needed"])
        self.assertNotEqual(result["final_brief"], "")

    def test_critic_caps_revisions_at_2(self):
        fake_response = "VERDICT: REVISE\nISSUES FOUND:\n- Test\nSUGGESTED FIXES:\n- Fix\nCONFIDENCE: High"
        state_at_limit = {**SAMPLE_AGENT_STATE, "revision_count": 2}
        with patch("agents.critic_agent.CRITIC_PROMPT", self._make_fake_chain(fake_response)), \
             patch("agents.critic_agent.get_gemini_llm", return_value=object()):
            result = critic_agent(state_at_limit)

        self.assertFalse(result["revision_needed"])


# ── Graph: analyze_case ───────────────────────────────────────────────────────

class TestAnalyzeCase(unittest.TestCase):

    def test_analyze_case_returns_required_fields(self):
        fake_result = {
            "eligibility_report": "Eligibility",
            "rights_report": "Rights",
            "advocate_draft": "Draft",
            "final_brief": "Final",
            "plain_summary": "Summary",
            "critic_feedback": "VERDICT: APPROVE",
            "critic_verdict": "APPROVE",
            "revision_count": 1,
            "retrieved_sources": [SAMPLE_SOURCE],
            "eligibility_sources": [SAMPLE_SOURCE],
            "rights_sources": [],
            "revision_history": [{"iteration": 1, "verdict": "APPROVE", "issues": [], "feedback": "VERDICT: APPROVE", "citation_check": "No citations detected."}],
        }
        with patch("agents.graph.graph.invoke", return_value=fake_result):
            response = analyze_case(SAMPLE_CASE)

        required = [
            "case_id", "eligibility_report", "rights_report", "final_brief",
            "plain_summary", "critic_feedback", "critic_verdict", "revisions_done",
            "retrieved_sources", "eligibility_sources", "rights_sources", "revision_history",
        ]
        for field in required:
            self.assertIn(field, response, f"Missing field: {field}")

    def test_analyze_case_falls_back_to_advocate_draft(self):
        fake_result = {
            "eligibility_report": "E", "rights_report": "R",
            "advocate_draft": "Fallback draft",
            "final_brief": "",  # empty — should fall back
            "plain_summary": "S", "critic_feedback": "FB", "critic_verdict": "REVISE",
            "revision_count": 0, "retrieved_sources": [], "eligibility_sources": [],
            "rights_sources": [], "revision_history": [],
        }
        with patch("agents.graph.graph.invoke", return_value=fake_result):
            response = analyze_case(SAMPLE_CASE)
        self.assertEqual(response["final_brief"], "Fallback draft")


# ── API smoke tests ───────────────────────────────────────────────────────────

class TestAPISmoke(unittest.TestCase):

    def test_health_endpoint(self):
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("version", body)

    def test_analyze_endpoint_shape(self):
        api_payload = {
            "case_id": "CASE-9",
            "eligibility_report": "Eligibility",
            "rights_report": "Rights",
            "final_brief": "Final",
            "plain_summary": "Summary",
            "critic_feedback": "VERDICT: APPROVE",
            "critic_verdict": "APPROVE",
            "revisions_done": 1,
            "retrieved_sources": [{"title": "Source", "used_by": ["eligibility"]}],
            "eligibility_sources": [{"title": "Source", "used_by": ["eligibility"]}],
            "rights_sources": [],
            "revision_history": [{"iteration": 1, "verdict": "APPROVE", "issues": [], "feedback": "VERDICT: APPROVE"}],
        }
        with patch("main.ingest_case_details"), patch("main.analyze_case", return_value=api_payload):
            resp = client.post("/analyze", json=SAMPLE_CASE)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["critic_verdict"], "APPROVE")
        self.assertIn("retrieved_sources", body)
        self.assertIn("revision_history", body)

    def test_ingest_pdf_rejects_non_pdf(self):
        resp = client.post(
            "/ingest/pdf",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        self.assertEqual(resp.status_code, 400)

    def test_ingest_kanoon_missing_token(self):
        with patch("main.search_and_ingest_kanoon", side_effect=ValueError("INDIAN_KANOON_API_TOKEN not set in .env")):
            resp = client.post("/ingest/kanoon", json={"query": "bail 436A", "text": "", "limit": 2})
        self.assertEqual(resp.status_code, 400)

    def test_retrieval_diagnose_endpoint(self):
        mock_docs = [Document(page_content="Test content", metadata={"title": "T", "category": "statute", "source": "s", "court": ""})]
        mock_diagnostics = [{"title": "T", "category": "statute", "source": "s", "similarity": 0.8, "authority_score": 1.0, "combined": 0.87}]
        with patch("main.retrieve_with_scores", return_value=(mock_docs, mock_diagnostics)):
            resp = client.get("/retrieval/diagnose", params={"query": "section 436A bail"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["query"], "section 436A bail")
        self.assertIn("results", body)

    def test_ingestion_status_endpoint(self):
        mock_log = {"abc123": {"label": "kanoon:456", "ingested_at": "2025-01-01T00:00:00Z"}}
        with patch("main._load_ingestion_log", return_value=mock_log):
            resp = client.get("/ingestion/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_ingested"], 1)
        self.assertEqual(len(body["entries"]), 1)


# ── Retrieval evaluation harness ──────────────────────────────────────────────

class TestRetrievalEvaluation(unittest.TestCase):
    """
    Fixed legal queries with expected authorities.
    These tests validate retrieval quality using mocked vector store responses.
    In CI, replace mocks with a seeded test ChromaDB for true integration tests.
    """

    EVAL_QUERIES = [
        {
            "query": "bail eligibility section 436A CrPC undertrial half sentence",
            "expected_keywords": ["436A", "bail", "undertrial"],
        },
        {
            "query": "Article 21 speedy trial Hussainara Khatoon undertrial prisoners rights",
            "expected_keywords": ["Hussainara", "speedy trial", "Article 21"],
        },
        {
            "query": "section 167 CrPC 60 day 90 day remand default bail",
            "expected_keywords": ["167", "remand", "60"],
        },
    ]

    def _make_mock_docs(self, keywords: list[str]) -> list[Document]:
        content = " ".join(keywords) + " CrPC bail undertrial India legal precedent."
        return [Document(
            page_content=content,
            metadata={"title": keywords[0], "category": "statute", "source": "test", "court": "central", "document_id": "test"}
        )]

    def test_retrieval_returns_docs_for_known_queries(self):
        for eval_case in self.EVAL_QUERIES:
            query = eval_case["query"]
            keywords = eval_case["expected_keywords"]
            mock_docs = self._make_mock_docs(keywords)
            mock_diagnostics = [{"title": keywords[0], "category": "statute", "source": "test", "similarity": 0.9, "authority_score": 1.0, "combined": 0.94}]

            with patch("rag.pipeline.get_vector_store") as mock_store:
                mock_store.return_value.similarity_search_with_relevance_scores.return_value = [(mock_docs[0], 0.9)]
                from rag.pipeline import retrieve_with_scores
                docs, diags = retrieve_with_scores(query, k=4)

            self.assertGreater(len(docs), 0, f"No docs returned for query: {query}")

    def test_statute_sources_ranked_above_unknown(self):
        statute_doc = Document(page_content="Statute text " * 20, metadata={"category": "statute", "court": "central"})
        unknown_doc = Document(page_content="Unknown source " * 20, metadata={"category": "unknown", "court": ""})
        results = [(statute_doc, 0.7), (unknown_doc, 0.95)]
        reranked = rerank_documents(results)
        self.assertEqual(reranked[0].metadata["category"], "statute")


if __name__ == "__main__":
    unittest.main(verbosity=2)

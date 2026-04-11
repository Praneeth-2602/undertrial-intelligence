import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from langchain.schema import Document

from agents.critic_agent import critic_agent
from agents.graph import analyze_case
from agents.source_utils import documents_to_context_and_sources, merge_sources
from fastapi.testclient import TestClient
from main import app


class SourceUtilsTests(unittest.TestCase):
    def test_documents_to_context_and_sources_builds_metadata(self):
        docs = [
            Document(
                page_content="Section 436A allows release when half the maximum sentence is served.",
                metadata={
                    "title": "Section 436A CrPC",
                    "source": "hardcoded_excerpt",
                    "category": "statute",
                    "court": "central",
                    "document_id": "436A",
                },
            )
        ]

        context, sources = documents_to_context_and_sources(docs, "eligibility")

        self.assertIn("Title: Section 436A CrPC", context)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["used_by"], ["eligibility"])
        self.assertEqual(sources[0]["document_id"], "436A")

    def test_merge_sources_merges_usage_labels(self):
        shared = {
            "title": "Shared Source",
            "excerpt": "Example excerpt",
            "source": "indian_kanoon",
            "category": "judgment",
            "court": "Supreme Court of India",
            "document_id": "123",
            "used_by": ["eligibility"],
        }
        merged = merge_sources(
            [shared],
            [{**shared, "used_by": ["rights"]}],
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["used_by"], ["eligibility", "rights"])


class RevisionLoopTests(unittest.TestCase):
    def test_run_parallel_agents_executes_concurrently(self):
        from agents.graph import run_parallel_agents

        state = {
            "case_input": {
                "case_id": "CASE-P",
                "accused_name": "Test",
                "fir_text": "Summary",
                "charges": ["IPC 379 - Theft"],
                "detention_days": 90,
                "court": "Sessions Court",
                "state": "Maharashtra",
            },
            "eligibility_report": "",
            "rights_report": "",
            "advocate_draft": "",
            "critic_feedback": "",
            "critic_verdict": "",
            "revision_needed": False,
            "revision_count": 0,
            "revision_history": [],
            "final_brief": "",
            "plain_summary": "",
            "retrieved_sources": [],
            "eligibility_sources": [],
            "rights_sources": [],
        }

        def fake_eligibility(s):
            time.sleep(0.25)
            return {
                **s,
                "eligibility_report": "Eligibility ready",
                "eligibility_sources": [
                    {
                        "title": "E Source",
                        "excerpt": "e",
                        "source": "test",
                        "category": "statute",
                        "court": "SC",
                        "document_id": "E1",
                        "used_by": ["eligibility"],
                    }
                ],
            }

        def fake_rights(s):
            time.sleep(0.25)
            return {
                **s,
                "rights_report": "Rights ready",
                "rights_sources": [
                    {
                        "title": "R Source",
                        "excerpt": "r",
                        "source": "test",
                        "category": "judgment",
                        "court": "SC",
                        "document_id": "R1",
                        "used_by": ["rights"],
                    }
                ],
            }

        start = time.perf_counter()
        with patch("agents.graph.eligibility_agent", side_effect=fake_eligibility), patch(
            "agents.graph.rights_agent", side_effect=fake_rights
        ):
            result = run_parallel_agents(state)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 0.45)
        self.assertEqual(result["eligibility_report"], "Eligibility ready")
        self.assertEqual(result["rights_report"], "Rights ready")
        self.assertEqual(len(result["retrieved_sources"]), 2)

    def test_critic_agent_records_verdict_and_history(self):
        state = {
            "case_input": {
                "case_id": "CASE-1",
                "accused_name": "Test Accused",
                "fir_text": "Summary",
                "charges": ["IPC 379 - Theft"],
                "detention_days": 120,
                "court": "Sessions Court",
                "state": "Maharashtra",
            },
            "eligibility_report": "Eligibility report",
            "rights_report": "Rights report",
            "advocate_draft": "Draft brief",
            "critic_feedback": "",
            "critic_verdict": "",
            "revision_needed": False,
            "revision_count": 0,
            "revision_history": [],
            "final_brief": "",
            "plain_summary": "",
            "retrieved_sources": [
                {
                    "title": "Section 436A CrPC",
                    "excerpt": "Half sentence threshold",
                    "source": "hardcoded_excerpt",
                    "category": "statute",
                    "court": "central",
                    "document_id": "436A",
                    "used_by": ["eligibility"],
                }
            ],
            "eligibility_sources": [],
            "rights_sources": [],
        }

        class FakeChain:
            def __or__(self, other):
                return self

            def invoke(self, payload):
                return "VERDICT: REVISE\nISSUES FOUND:\n- Missing source support\nSUGGESTED FIXES:\n- Cite retrieved authority\nCONFIDENCE: High"

        with patch("agents.critic_agent.CRITIC_PROMPT", FakeChain()), patch(
            "agents.critic_agent.get_gemini_llm", return_value=object()
        ):
            result = critic_agent(state)

        self.assertEqual(result["critic_verdict"], "REVISE")
        self.assertTrue(result["revision_needed"])
        self.assertEqual(result["revision_history"][0]["issues"], ["Missing source support"])

    def test_analyze_case_returns_new_response_fields(self):
        fake_result = {
            "eligibility_report": "Eligibility",
            "rights_report": "Rights",
            "advocate_draft": "Draft",
            "final_brief": "Final",
            "plain_summary": "Summary",
            "critic_feedback": "VERDICT: APPROVE",
            "critic_verdict": "APPROVE",
            "revision_count": 1,
            "retrieved_sources": [{"title": "Source", "used_by": ["eligibility"]}],
            "eligibility_sources": [{"title": "Source", "used_by": ["eligibility"]}],
            "rights_sources": [],
            "revision_history": [{"iteration": 1, "verdict": "APPROVE", "issues": [], "feedback": "VERDICT: APPROVE"}],
        }

        with patch("agents.graph.graph.invoke", return_value=fake_result):
            response = analyze_case(
                {
                    "case_id": "CASE-1",
                    "accused_name": "Test",
                    "fir_text": "Summary",
                    "charges": ["IPC 379 - Theft"],
                    "detention_days": 60,
                    "court": "Court",
                    "state": "State",
                }
            )

        self.assertEqual(response["critic_verdict"], "APPROVE")
        self.assertIn("retrieved_sources", response)
        self.assertIn("revision_history", response)

    def test_analyze_endpoint_returns_extended_payload(self):
        client = TestClient(app)
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
            response = client.post(
                "/analyze",
                json={
                    "case_id": "CASE-9",
                    "accused_name": "Test",
                    "fir_text": "Summary",
                    "charges": ["IPC 379 - Theft"],
                    "detention_days": 90,
                    "court": "Sessions Court",
                    "state": "Maharashtra",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["critic_verdict"], "APPROVE")
        self.assertIn("retrieved_sources", body)


if __name__ == "__main__":
    unittest.main()

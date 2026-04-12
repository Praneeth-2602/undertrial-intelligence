import re

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.state import AgentState
from agents.source_utils import format_sources_for_prompt
from utils.llm_config import get_gemini_llm

# ── Citation verification ──────────────────────────────────────────────────────

def _extract_citations(text: str) -> list[str]:
    """
    Extract cited authorities from brief text.
    Captures: 'Section 436A', 'Article 21', 'Hussainara Khatoon', case names, etc.
    """
    patterns = [
        r"Section\s+\d+[A-Z]?\s+\w+",
        r"Article\s+\d+[A-Z]?",
        r"IPC\s+\d+",
        r"CrPC\s+\d+[A-Z]?",
        r"(?:[A-Z][a-z]+ ){1,3}v\.?\s+(?:[A-Z][a-z]+ ){0,3}(?:of\s+\w+)?",
    ]
    found = []
    for p in patterns:
        found.extend(re.findall(p, text))
    return list(set(found))


def _verify_citations_against_sources(
    citations: list[str],
    sources: list[dict],
) -> tuple[list[str], list[str]]:
    """
    Cross-check each citation against retrieved source excerpts.
    Returns (grounded_citations, ungrounded_citations).
    """
    all_source_text = " ".join(
        (s.get("excerpt", "") + " " + s.get("title", "")).lower()
        for s in sources
    )
    grounded, ungrounded = [], []
    for citation in citations:
        key = citation.lower().strip()
        # Partial match: accept if any significant word appears in sources
        words = [w for w in key.split() if len(w) > 3]
        if any(w in all_source_text for w in words):
            grounded.append(citation)
        else:
            ungrounded.append(citation)
    return grounded, ungrounded


CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strict legal reviewer and hallucination detector for AI-generated legal briefs in India.

Your job:
1. Check every cited case/section — flag any that seem fabricated or inconsistent with the source documents provided
2. Check if the bail eligibility math is correct (detention_days vs. 436A threshold)
3. Check if constitutional arguments are legally sound
4. Identify any overconfident claims not supported by the retrieved evidence
5. Check if the citation verification report below shows ungrounded citations — these must be flagged

Citation verification pre-check:
{citation_check}

Retrieved source documents (ground truth):
{source_docs}

Output format (strict):
VERDICT: APPROVE or REVISE
ISSUES FOUND:
- (list each issue, or "None" if clean)
SUGGESTED FIXES:
- (list fixes, or "None")
CONFIDENCE: High / Medium / Low
"""),
    ("human", """Review this legal brief:

{advocate_draft}

Eligibility report used:
{eligibility_report}

Rights report used:
{rights_report}

Detention days: {detention_days}
Charges: {charges}
"""),
])


def _build_citation_check_report(brief: str, sources: list[dict]) -> str:
    citations = _extract_citations(brief)
    if not citations:
        return "No citations detected in brief."
    grounded, ungrounded = _verify_citations_against_sources(citations, sources)
    lines = [f"Citations found: {len(citations)}"]
    lines.append(f"Grounded (found in sources): {len(grounded)}")
    if grounded:
        lines.append("  " + "; ".join(grounded[:6]))
    lines.append(f"UNGROUNDED (not found in sources): {len(ungrounded)}")
    if ungrounded:
        lines.append("  " + "; ".join(ungrounded[:6]))
    return "\n".join(lines)


def critic_agent(state: AgentState) -> AgentState:
    case = state["case_input"]
    retrieved = state.get("retrieved_sources", [])
    source_context = format_sources_for_prompt(retrieved, limit=10)
    citation_report = _build_citation_check_report(state["advocate_draft"], retrieved)

    chain = CRITIC_PROMPT | get_gemini_llm(temperature=0.0) | StrOutputParser()
    feedback = chain.invoke({
        "citation_check": citation_report,
        "source_docs": source_context,
        "advocate_draft": state["advocate_draft"],
        "eligibility_report": state["eligibility_report"],
        "rights_report": state["rights_report"],
        "detention_days": case["detention_days"],
        "charges": ", ".join(case["charges"]),
    })

    verdict = "REVISE" if "VERDICT: REVISE" in feedback else "APPROVE"
    issues: list[str] = []
    in_issues = False
    for raw_line in feedback.splitlines():
        line = raw_line.strip()
        if line.startswith("ISSUES FOUND:"):
            in_issues = True
            continue
        if in_issues and line.startswith("SUGGESTED FIXES:"):
            break
        if in_issues and line.startswith("-"):
            issue = line[1:].strip()
            if issue and issue.lower() != "none":
                issues.append(issue)

    revision_needed = (
        verdict == "REVISE"
        and state.get("revision_count", 0) < 2
    )

    revision_history = list(state.get("revision_history", []))
    revision_history.append({
        "iteration": state.get("revision_count", 0) + 1,
        "verdict": verdict,
        "issues": issues,
        "feedback": feedback,
        "citation_check": citation_report,
    })

    final_brief = state["advocate_draft"] if not revision_needed else ""

    return {
        **state,
        "critic_feedback": feedback,
        "critic_verdict": verdict,
        "revision_needed": revision_needed,
        "revision_count": state.get("revision_count", 0) + 1,
        "revision_history": revision_history,
        "final_brief": final_brief,
    }


def should_revise(state: AgentState) -> str:
    if state.get("revision_needed", False):
        return "revise"
    return "done"

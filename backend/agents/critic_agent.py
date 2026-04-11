from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.state import AgentState
from agents.source_utils import format_sources_for_prompt
from utils.llm_config import get_gemini_llm

CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strict legal reviewer and hallucination detector for AI-generated legal briefs in India.

Your job:
1. Check every cited case/section — flag any that seem fabricated or inconsistent with the context provided
2. Check if the bail eligibility math is correct (detention_days vs. 436A threshold)
3. Check if constitutional arguments are legally sound
4. Identify any overconfident claims not supported by evidence

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

def critic_agent(state: AgentState) -> AgentState:
    case = state["case_input"]
    source_context = format_sources_for_prompt(state.get("retrieved_sources", []), limit=10)

    chain = CRITIC_PROMPT | get_gemini_llm(temperature=0.0) | StrOutputParser()
    feedback = chain.invoke({
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
        and state.get("revision_count", 0) < 2  # max 2 revision loops
    )

    revision_history = list(state.get("revision_history", []))
    revision_history.append({
        "iteration": state.get("revision_count", 0) + 1,
        "verdict": verdict,
        "issues": issues,
        "feedback": feedback,
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
    """LangGraph conditional edge - routes back to advocate or exits."""
    if state.get("revision_needed", False):
        return "revise"
    return "done"

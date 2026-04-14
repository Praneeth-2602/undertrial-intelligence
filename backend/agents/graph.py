from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.eligibility_agent import eligibility_agent
from agents.rights_agent import rights_agent
from agents.advocate_agent import advocate_agent
from agents.critic_agent import critic_agent, should_revise
from agents.source_utils import merge_sources

def run_parallel_agents(state: AgentState) -> AgentState:
    """
    Run eligibility + rights agents. LangGraph supports true parallel
    execution via Send() API, but for simplicity we run sequentially here.
    Both use Groq so rate limits are shared — add asyncio if needed.
    """
    state = eligibility_agent(state)
    state = rights_agent(state)
    state["retrieved_sources"] = merge_sources(
        state.get("eligibility_sources", []),
        state.get("rights_sources", []),
    )
    return state

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("parallel_analysis", run_parallel_agents)
    graph.add_node("advocate", advocate_agent)
    graph.add_node("critic", critic_agent)

    # Edges
    graph.set_entry_point("parallel_analysis")
    graph.add_edge("parallel_analysis", "advocate")
    graph.add_edge("advocate", "critic")

    # Conditional: critic either approves or sends back to advocate
    graph.add_conditional_edges(
        "critic",
        should_revise,
        {
            "revise": "advocate",
            "done": END,
        },
    )

    return graph.compile()

# Compiled graph (import this in API routes)
graph = build_graph()

def analyze_case(case_input: dict) -> dict:
    """Entry point for the FastAPI layer."""
    initial_state: AgentState = {
        "case_input": case_input,
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
        "localized_summaries": {},
        "retrieved_sources": [],
        "eligibility_sources": [],
        "rights_sources": [],
    }

    result = graph.invoke(initial_state)
    return {
        "case_id": case_input["case_id"],
        "eligibility_report": result["eligibility_report"],
        "rights_report": result["rights_report"],
        "final_brief": result["final_brief"] or result["advocate_draft"],
        "plain_summary": result["plain_summary"],
        "family_language": case_input.get("family_language", "English"),
        "localized_summaries": result.get("localized_summaries") or {"English": result["plain_summary"]},
        "critic_feedback": result["critic_feedback"],
        "critic_verdict": result["critic_verdict"],
        "revisions_done": result["revision_count"],
        "retrieved_sources": result["retrieved_sources"],
        "eligibility_sources": result["eligibility_sources"],
        "rights_sources": result["rights_sources"],
        "revision_history": result["revision_history"],
    }

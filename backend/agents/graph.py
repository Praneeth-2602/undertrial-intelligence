from langgraph.graph import StateGraph, END
from concurrent.futures import ThreadPoolExecutor
from agents.state import AgentState
from agents.eligibility_agent import eligibility_agent
from agents.rights_agent import rights_agent
from agents.advocate_agent import advocate_agent
from agents.critic_agent import critic_agent, should_revise
from agents.source_utils import merge_sources

def run_parallel_agents(state: AgentState) -> AgentState:
    """
    Run eligibility + rights agents concurrently, then merge outputs.
    Each agent gets an isolated snapshot of state to avoid cross-thread mutation.
    """
    eligibility_input = {
        **state,
        "retrieved_sources": [],
        "eligibility_sources": [],
        "rights_sources": [],
    }
    rights_input = {
        **state,
        "retrieved_sources": [],
        "eligibility_sources": [],
        "rights_sources": [],
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        eligibility_future = executor.submit(eligibility_agent, eligibility_input)
        rights_future = executor.submit(rights_agent, rights_input)
        eligibility_result = eligibility_future.result()
        rights_result = rights_future.result()

    eligibility_sources = eligibility_result.get("eligibility_sources", [])
    rights_sources = rights_result.get("rights_sources", [])

    merged_sources = merge_sources(
        eligibility_sources,
        rights_sources,
    )

    return {
        **state,
        "eligibility_report": eligibility_result.get("eligibility_report", ""),
        "rights_report": rights_result.get("rights_report", ""),
        "eligibility_sources": eligibility_sources,
        "rights_sources": rights_sources,
        "retrieved_sources": merged_sources,
    }

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
        "critic_feedback": result["critic_feedback"],
        "critic_verdict": result["critic_verdict"],
        "revisions_done": result["revision_count"],
        "retrieved_sources": result["retrieved_sources"],
        "eligibility_sources": result["eligibility_sources"],
        "rights_sources": result["rights_sources"],
        "revision_history": result["revision_history"],
    }

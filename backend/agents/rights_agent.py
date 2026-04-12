from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.state import AgentState
from agents.source_utils import documents_to_context_and_sources, merge_sources
from rag.pipeline import retrieve_with_scores, log_retrieval_diagnostics
from utils.llm_config import get_groq_llm
from utils.prompt_loader import load_prompt


def rights_agent(state: AgentState) -> AgentState:
    case = state["case_input"]

    query = "Article 21 right to speedy trial undertrial prisoners Hussainara Khatoon section 167 CrPC default bail remand"

    docs, diagnostics = retrieve_with_scores(query, k=8)
    log_retrieval_diagnostics(query, diagnostics, agent="rights")
    context, sources = documents_to_context_and_sources(docs, "rights")

    prompt = ChatPromptTemplate.from_messages([
        ("system", load_prompt("rights_system")),
        ("human", """Assess rights violations for:

Name: {accused_name}
Charges: {charges}
Days in detention: {detention_days}
Court: {court}, {state}

FIR Summary:
{fir_text}

Retrieved legal authorities (cite specific cases/articles by name if relevant):
{context}
"""),
    ])

    chain = prompt | get_groq_llm() | StrOutputParser()
    report = chain.invoke({
        "context": context,
        "accused_name": case["accused_name"],
        "charges": "\n".join(f"- {c}" for c in case["charges"]),
        "detention_days": case["detention_days"],
        "court": case["court"],
        "state": case["state"],
        "fir_text": case["fir_text"],
    })

    print(f"[rights_agent] done — {len(docs)} docs retrieved")
    return {
        **state,
        "rights_report": report,
        "rights_sources": sources,
        "retrieved_sources": merge_sources(state.get("retrieved_sources", []), sources),
    }

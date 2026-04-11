from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.state import AgentState
from agents.source_utils import documents_to_context_and_sources
from rag.pipeline import get_retriever
from utils.llm_config import get_groq_llm
from utils.prompt_loader import load_prompt

def eligibility_agent(state: AgentState) -> AgentState:
    case = state["case_input"]
    retriever = get_retriever(k=8)

    charges_str = " ".join(case["charges"])
    query = f"bail eligibility {charges_str} section 436A CrPC undertrial default bail maximum sentence"
    docs = retriever.invoke(query)
    context, sources = documents_to_context_and_sources(docs, "eligibility")

    prompt = ChatPromptTemplate.from_messages([
        ("system", load_prompt("eligibility_system")),
        ("human", """Assess bail eligibility for:

Name: {accused_name}
Charges: {charges}
Days in detention: {detention_days}
Court: {court}, {state}

FIR Summary:
{fir_text}
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

    print(f"[eligibility_agent] done — {len(docs)} docs retrieved")
    return {
        **state,
        "eligibility_report": report,
        "eligibility_sources": sources,
        "retrieved_sources": sources,
    }

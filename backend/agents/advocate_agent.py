from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents.state import AgentState
from agents.source_utils import format_sources_for_prompt
from utils.llm_config import get_gemini_llm
from utils.prompt_loader import load_prompt

SUPPORTED_FAMILY_LANGUAGES = {
    "English": "English",
    "Hindi": "Hindi",
    "Marathi": "Marathi",
    "Bengali": "Bengali",
    "Tamil": "Tamil",
    "Telugu": "Telugu",
    "Kannada": "Kannada",
    "Malayalam": "Malayalam",
    "Gujarati": "Gujarati",
    "Punjabi": "Punjabi",
    "Urdu": "Urdu",
}


def _normalize_family_language(language: str | None) -> str:
    if not language:
        return "English"

    normalized = str(language).strip()
    for supported in SUPPORTED_FAMILY_LANGUAGES:
        if supported.lower() == normalized.lower():
            return supported
    return "English"


def advocate_agent(state: AgentState) -> AgentState:
    case = state["case_input"]
    gemini = get_gemini_llm()
    is_revision = bool(state.get("critic_feedback"))
    family_language = _normalize_family_language(case.get("family_language"))

    brief_prompt = ChatPromptTemplate.from_messages([
        ("system", load_prompt("advocate_system").split("# ──")[0].strip()),
        ("human", """Draft the complete legal brief.

ELIGIBILITY ASSESSMENT:
{eligibility_report}

RIGHTS ANALYSIS:
{rights_report}

CASE DETAILS:
Name: {accused_name}
Charges: {charges}
Detention: {detention_days} days
Court: {court}, {state}
FIR: {fir_text}

AUTHORITIES RETRIEVED:
{retrieved_authorities}

PRIOR DRAFT:
{prior_draft}

CRITIC FEEDBACK TO ADDRESS:
{critic_feedback}
"""),
    ])

    plain_prompt = ChatPromptTemplate.from_messages([
        ("system", load_prompt("advocate_system").split("# Prompt: Advocate Agent — Plain")[1].strip()),
        ("human", "Summarize this legal brief for the family:\n\n{brief}"),
    ])
    translate_prompt = ChatPromptTemplate.from_messages([
        ("system", """You translate family-facing legal summaries for Indian undertrial cases.

Rules:
- Keep the meaning fully consistent with the original English summary.
- Use plain, compassionate language for a non-lawyer family member.
- Preserve legal sections, case names, and legal terms when translation would reduce accuracy.
- Return only the translated summary in Markdown.
"""),
        ("human", "Translate this summary into {language} for the family:\n\n{summary}"),
    ])

    brief_chain = brief_prompt | gemini | StrOutputParser()
    brief = brief_chain.invoke({
        "eligibility_report": state["eligibility_report"],
        "rights_report": state["rights_report"],
        "accused_name": case["accused_name"],
        "charges": "\n".join(f"- {c}" for c in case["charges"]),
        "detention_days": case["detention_days"],
        "court": case["court"],
        "state": case["state"],
        "fir_text": case["fir_text"],
        "retrieved_authorities": format_sources_for_prompt(state.get("retrieved_sources", [])),
        "prior_draft": state["advocate_draft"] if is_revision else "None",
        "critic_feedback": state["critic_feedback"] if is_revision else "None",
    })

    summary_chain = plain_prompt | gemini | StrOutputParser()
    plain = summary_chain.invoke({"brief": brief})
    localized_summaries = {"English": plain}

    if family_language != "English":
        try:
            translate_chain = translate_prompt | gemini | StrOutputParser()
            localized_summaries[family_language] = translate_chain.invoke({
                "language": family_language,
                "summary": plain,
            })
        except Exception as exc:
            print(f"[advocate_agent] translation failed for {family_language}: {exc}")

    print(f"[advocate_agent] brief drafted ({len(brief)} chars)")
    return {
        **state,
        "advocate_draft": brief,
        "plain_summary": plain,
        "localized_summaries": localized_summaries,
    }

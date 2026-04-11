from typing import TypedDict, Annotated, Literal
import operator

class CaseInput(TypedDict):
    case_id: str
    accused_name: str
    fir_text: str
    charges: list[str]
    detention_days: int
    court: str
    state: str


class SourceRecord(TypedDict):
    title: str
    excerpt: str
    source: str
    category: str
    court: str
    document_id: str
    used_by: list[Literal["eligibility", "rights"]]


class RevisionRecord(TypedDict):
    iteration: int
    verdict: str
    issues: list[str]
    feedback: str

class AgentState(TypedDict):
    # Input
    case_input: CaseInput

    # Agent outputs (populated in parallel)
    eligibility_report: str
    rights_report: str
    advocate_draft: str

    # Critic feedback
    critic_feedback: str
    critic_verdict: str
    revision_needed: bool
    revision_count: int
    revision_history: list[RevisionRecord]

    # Final output
    final_brief: str
    plain_summary: str

    # Shared retrieved context
    retrieved_sources: Annotated[list[SourceRecord], operator.add]
    eligibility_sources: list[SourceRecord]
    rights_sources: list[SourceRecord]

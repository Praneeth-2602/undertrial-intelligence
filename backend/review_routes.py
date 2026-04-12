"""
review_routes.py - FastAPI routes for lawyer review workflow.
"""

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from review_store import save_review, get_review, list_reviews

router = APIRouter(tags=["Lawyer Review"])


class ReviewRequest(BaseModel):
    case_id: str
    verdict: Literal["approved", "flagged", "needs_revision"]
    note: str = Field(default="", description="Free-text lawyer note")
    reviewer: str = Field(default="", description="Reviewer name or initials")


class ReviewResponse(BaseModel):
    case_id: str
    verdict: str
    note: str
    reviewer: str
    reviewed_at: str


@router.post("/review", response_model=ReviewResponse, summary="Submit a lawyer review verdict")
def submit_review(req: ReviewRequest):
    """
    Submit or update the lawyer review verdict for a case.
    Calling this again for the same case_id overwrites the previous verdict.
    """
    try:
        record = save_review(
            case_id=req.case_id,
            verdict=req.verdict,
            note=req.note,
            reviewer=req.reviewer,
        )
        return ReviewResponse(**record)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review/{case_id}", response_model=Optional[ReviewResponse], summary="Get review for a case")
def get_case_review(case_id: str):
    """
    Return the current lawyer review for a case, or null if not yet reviewed.
    """
    record = get_review(case_id)
    if record is None:
        return None
    return ReviewResponse(**record)


@router.get("/reviews", summary="List all lawyer reviews")
def list_all_reviews():
    """
    Return all submitted lawyer reviews - used by the review dashboard.
    """
    return list_reviews()

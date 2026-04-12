"""
review_store.py - lightweight persistence for lawyer review verdicts.

Stores reviews in data/lawyer_reviews.json - no extra DB needed.
Each record keyed by case_id; a new verdict overwrites the previous one
(last-write-wins, which is fine for single-lawyer NGO use).
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

REVIEW_STORE_PATH = os.getenv("LAWYER_REVIEW_PATH", "./data/lawyer_reviews.json")


def _load() -> dict:
    path = Path(REVIEW_STORE_PATH)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    path = Path(REVIEW_STORE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def save_review(
    case_id: str,
    verdict: str,
    note: str,
    reviewer: str,
) -> dict:
    """
    Persist a lawyer review verdict for a case.

    verdict must be one of: "approved", "flagged", "needs_revision"
    """
    allowed = {"approved", "flagged", "needs_revision"}
    if verdict not in allowed:
        raise ValueError(f"verdict must be one of {allowed}")

    data = _load()
    record = {
        "case_id": case_id,
        "verdict": verdict,
        "note": note.strip(),
        "reviewer": reviewer.strip() or "Anonymous",
        "reviewed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    data[case_id] = record
    _save(data)
    return record


def get_review(case_id: str) -> Optional[dict]:
    return _load().get(case_id)


def list_reviews() -> list[dict]:
    return list(_load().values())

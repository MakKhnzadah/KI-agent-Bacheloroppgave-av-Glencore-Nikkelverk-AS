from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuggestionOperation(str, Enum):
    create = "create"
    update = "update"
    append_section = "append_section"


class Citation(BaseModel):
    source_name: str
    locator: str | None = None
    quote: str | None = None


class Suggestion(BaseModel):
    suggestion_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    target_path: str
    operation: SuggestionOperation

    proposed_markdown: str
    rationale: str
    citations: list[Citation] = Field(default_factory=list)

    extra: dict[str, Any] = Field(default_factory=dict)


class ReviewDecision(str, Enum):
    approved = "approved"
    rejected = "rejected"


class ReviewedSuggestion(BaseModel):
    suggestion: Suggestion
    decision: ReviewDecision
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    reviewer: str | None = None
    notes: str | None = None

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from verity.schemas.extractionReviewSchemas import (
    ClarificationResponseInput,
)


class EffectiveFactValue(BaseModel):
    value: str

    origin: Literal[
        "pdfExtraction",
        "reviewerSupplied",
    ]

    candidateIndex: int | None = None
    actionStatus: str | None = None

    occurrences: list[dict[str, object]] = Field(
        default_factory=list,
    )

    evidenceNote: str | None = None


class EffectiveField(BaseModel):
    decision: Literal[
        "unreviewed",
        "accept",
        "correct",
        "notApplicable",
        "unresolved",
    ]

    candidateCount: int
    values: list[EffectiveFactValue] = Field(
        default_factory=list,
    )
    reason: str | None = None


class EffectiveFactView(BaseModel):
    extractionId: UUID
    reviewId: UUID
    revisionNumber: int
    reviewStatus: Literal["draft", "approved"]

    assessmentVersion: str
    reviewAssessmentCurrent: bool
    canDraftHypotheses: bool

    fields: dict[str, EffectiveField]
    clarificationResponses: dict[
        str,
        ClarificationResponseInput,
    ]
    pendingFindingIds: list[str]
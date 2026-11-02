from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.schemas.rcaEvidenceAssessmentSchemas import (
    RcaEvidenceAssessment,
)
from verity.schemas.rcaReviewSchemas import RcaFindingResponse


class EffectiveRcaHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesisId: str
    originalStatement: str

    decision: Literal[
        "unreviewed",
        "retain",
        "reject",
        "revise",
    ]
    effectiveStatement: str | None
    statementOrigin: Literal[
        "generated",
        "reviewerSupplied",
    ] | None

    rationale: str | None

    status: Literal["unverified"] = "unverified"
    requiresHumanEvidenceReview: Literal[True] = True


class EffectiveRcaView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rcaDraftId: UUID
    rcaReviewId: UUID
    revisionNumber: int
    reviewStatus: Literal["draft", "reviewed"]

    reviewerLabel: str
    reviewNote: str | None
    reviewCreatedAt: datetime

    assessmentVersion: str
    reviewAssessmentCurrent: bool
    reviewComplete: bool

    sourceDraft: ValidatedRcaDraft

    hypotheses: list[EffectiveRcaHypothesis]

    savedEvidenceAssessment: RcaEvidenceAssessment
    currentEvidenceAssessment: RcaEvidenceAssessment
    findingResponses: dict[str, RcaFindingResponse]
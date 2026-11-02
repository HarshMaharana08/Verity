from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID

from verity.schemas.rcaEvidenceAssessmentSchemas import (
    RcaEvidenceAssessment,
)


class RcaReviewSchemaBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class RetainedRcaHypothesis(RcaReviewSchemaBase):
    decision: Literal["retain"]

    rationale: str = Field(
        min_length=1,
        max_length=4000,
    )


class RejectedRcaHypothesis(RcaReviewSchemaBase):
    decision: Literal["reject"]

    rationale: str = Field(
        min_length=1,
        max_length=4000,
    )


class RevisedRcaHypothesis(RcaReviewSchemaBase):
    decision: Literal["revise"]

    revisedStatement: str = Field(
        min_length=1,
        max_length=3000,
    )
    rationale: str = Field(
        min_length=1,
        max_length=4000,
    )


RcaHypothesisDecision = Annotated[
    (
        RetainedRcaHypothesis
        | RejectedRcaHypothesis
        | RevisedRcaHypothesis
    ),
    Field(discriminator="decision"),
]


class RcaFindingResponse(RcaReviewSchemaBase):
    disposition: Literal[
        "acknowledged",
        "disputed",
    ]
    explanation: str = Field(
        min_length=1,
        max_length=4000,
    )


class RcaReviewRequest(RcaReviewSchemaBase):
    expectedRevision: int = Field(
        ge=0,
    )

    expectedAssessmentVersion: str = Field(
        min_length=1,
        max_length=50,
    )

    reviewStatus: Literal[
        "draft",
        "reviewed",
    ]

    reviewerLabel: str = Field(
        min_length=1,
        max_length=100,
    )

    hypothesisDecisions: dict[
        str,
        RcaHypothesisDecision,
    ] = Field(default_factory=dict)

    findingResponses: dict[
        str,
        RcaFindingResponse,
    ] = Field(default_factory=dict)

    reviewNote: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )
    
class RcaReviewResponse(RcaReviewSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    rcaReviewId: UUID
    rcaDraftId: UUID
    revisionNumber: int
    reviewStatus: Literal["draft", "reviewed"]
    reviewerLabel: str

    assessmentVersion: str
    assessmentSnapshot: RcaEvidenceAssessment

    hypothesisDecisions: dict[str, RcaHypothesisDecision]
    findingResponses: dict[str, RcaFindingResponse]
    reviewNote: str | None
    createdAt: datetime
    
class RcaReviewSummary(RcaReviewSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    rcaReviewId: UUID
    rcaDraftId: UUID
    revisionNumber: int
    reviewStatus: Literal["draft", "reviewed"]
    reviewerLabel: str
    assessmentVersion: str
    reviewNote: str | None
    createdAt: datetime


class RcaReviewListResponse(RcaReviewSchemaBase):
    items: list[RcaReviewSummary]
    pageSize: int
    pageOffset: int
    hasMore: bool
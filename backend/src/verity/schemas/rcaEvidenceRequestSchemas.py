from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RcaEvidenceRequestCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    hypothesisId: str | None = Field(
        default=None,
        pattern=r"^hyp-[1-9][0-9]*$",
        max_length=50,
    )

    requestText: str = Field(
        min_length=1,
        max_length=5000,
    )

    rationale: str = Field(
        min_length=1,
        max_length=5000,
    )

    requestedByLabel: str = Field(
        min_length=1,
        max_length=100,
    )


class RcaEvidenceRequestResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    evidenceRequestId: UUID
    rcaReviewId: UUID
    hypothesisId: str | None
    requestText: str
    rationale: str
    requestedByLabel: str
    createdAt: datetime
    
class RcaEvidenceRequestListResponse(BaseModel):
    items: list[RcaEvidenceRequestResponse]
    pageSize: int
    pageOffset: int
    hasMore: bool
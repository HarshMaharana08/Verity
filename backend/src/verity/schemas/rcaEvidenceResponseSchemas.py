from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RcaEvidenceResponseCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    expectedRevision: int = Field(ge=0)

    responseStatus: Literal[
        "pending",
        "supplied",
        "unavailable",
    ]

    responseText: str = Field(
        min_length=1,
        max_length=10000,
    )

    respondedByLabel: str = Field(
        min_length=1,
        max_length=100,
    )

    documentIds: list[UUID] = Field(
        default_factory=list,
        max_length=50,
    )

    @model_validator(mode="after")
    def validateDocumentLinks(self) -> "RcaEvidenceResponseCreate":
        if len(self.documentIds) != len(set(self.documentIds)):
            raise ValueError(
                "Supporting document IDs must not repeat."
            )

        if (
            self.responseStatus != "supplied"
            and self.documentIds
        ):
            raise ValueError(
                "Only supplied responses can link supporting documents."
            )

        return self


class RcaEvidenceResponseView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidenceResponseId: UUID
    evidenceRequestId: UUID
    revisionNumber: int

    responseStatus: Literal[
        "pending",
        "supplied",
        "unavailable",
    ]

    responseText: str
    respondedByLabel: str
    documentIds: list[UUID]
    createdAt: datetime
    
class RcaEvidenceResponseListView(BaseModel):
    items: list[RcaEvidenceResponseView]
    pageSize: int
    pageOffset: int
    hasMore: bool
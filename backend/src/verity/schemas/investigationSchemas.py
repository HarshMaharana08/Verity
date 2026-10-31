from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)


class CreateInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=255,
        ),
    ]

    description: str | None = Field(
        default=None,
        max_length=10000,
    )


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigationId: UUID
    title: str
    description: str | None
    status: str
    createdAt: datetime
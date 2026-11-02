from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RcaJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rcaJobId: UUID
    sourceReviewId: UUID

    status: Literal[
        "queued",
        "processing",
        "succeeded",
        "failed",
    ]
    attemptCount: int

    inputSha256: str
    providerName: str
    modelName: str
    workflowVersion: str
    promptVersion: str
    schemaVersion: str

    availableAt: datetime
    createdAt: datetime
    startedAt: datetime | None
    completedAt: datetime | None

    errorCode: str | None
    errorMessage: str | None
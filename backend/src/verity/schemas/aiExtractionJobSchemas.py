from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AiExtractionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    aiJobId: UUID
    sourceProcessingJobId: UUID
    status: str
    attemptCount: int
    availableAt: datetime

    providerName: str
    modelName: str
    promptVersion: str
    schemaVersion: str

    extractionId: UUID | None
    createdAt: datetime
    startedAt: datetime | None
    completedAt: datetime | None

    errorCode: str | None
    errorMessage: str | None
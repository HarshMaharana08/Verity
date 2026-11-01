from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    jobId: UUID
    documentId: UUID
    status: str
    attemptCount: int
    createdAt: datetime
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    errorMessage: str | None = None
    

class ProcessingJobTextResponse(BaseModel):
    jobId: UUID
    documentId: UUID
    characterCount: int
    extractedText: str
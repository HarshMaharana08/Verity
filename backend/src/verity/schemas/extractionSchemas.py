from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IncidentExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    extractionId: UUID
    sourceProcessingJobId: UUID
    providerName: str
    modelName: str
    promptVersion: str
    schemaVersion: str
    sourceTextSha256: str
    extractedData: dict[str, object]
    createdAt: datetime
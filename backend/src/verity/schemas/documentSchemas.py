from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    documentId: UUID
    investigationId: UUID
    originalFileName: str
    mediaType: str
    fileSizeBytes: int
    sha256Digest: str
    uploadedAt: datetime
    
class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    pageSize: int
    pageOffset: int
    hasMore: bool
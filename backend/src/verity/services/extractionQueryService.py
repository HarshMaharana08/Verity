from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verity.models import (
    DocumentProcessingJob,
    IncidentExtractionRecord,
    InvestigationDocument,
)


class IncidentExtractionNotFoundError(LookupError):
    pass


def getIncidentExtraction(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
) -> IncidentExtractionRecord:
    extractionQuery = (
        select(IncidentExtractionRecord)
        .join(
            DocumentProcessingJob,
            IncidentExtractionRecord.sourceProcessingJobId
            == DocumentProcessingJob.jobId,
        )
        .join(
            InvestigationDocument,
            DocumentProcessingJob.documentId
            == InvestigationDocument.documentId,
        )
        .where(
            IncidentExtractionRecord.extractionId
            == extractionId,
            InvestigationDocument.documentId
            == documentId,
            InvestigationDocument.investigationId
            == investigationId,
        )
    )

    extractionRecord = databaseSession.scalar(
        extractionQuery
    )

    if extractionRecord is None:
        raise IncidentExtractionNotFoundError(
            "Extraction not found for this document "
            "and investigation."
        )

    return extractionRecord
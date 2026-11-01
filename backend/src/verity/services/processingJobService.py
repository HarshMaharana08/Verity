from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from verity.models.documentProcessingJob import (
    DocumentProcessingJob,
)
from verity.models.investigationDocument import (
    InvestigationDocument,
)
from verity.services.documentService import (
    DocumentNotFoundError,
)


class ActiveProcessingJobError(Exception):
    pass


def queueDocumentProcessingJob(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
) -> DocumentProcessingJob:
    documentQuery = select(InvestigationDocument).where(
        InvestigationDocument.documentId == documentId,
        InvestigationDocument.investigationId == investigationId,
    )

    documentRecord = databaseSession.scalar(documentQuery)

    if documentRecord is None:
        raise DocumentNotFoundError(
            "Document not found for this investigation."
        )

    jobRecord = DocumentProcessingJob(
        documentId=documentRecord.documentId,
        status="queued",
        attemptCount=0,
    )

    try:
        databaseSession.add(jobRecord)
        databaseSession.flush()
        databaseSession.refresh(jobRecord)
        databaseSession.commit()

    except IntegrityError as databaseError:
        databaseSession.rollback()

        originalError = databaseError.orig

        if (
            isinstance(originalError, UniqueViolation)
            and originalError.diag.constraint_name
            == "uniqueActiveDocumentProcessingJob"
        ):
            raise ActiveProcessingJobError(
                "This document already has a queued or "
                "processing job."
            ) from None

        raise

    except SQLAlchemyError:
        databaseSession.rollback()
        raise

    return jobRecord


class ProcessingJobNotFoundError(LookupError):
    pass


def getDocumentProcessingJob(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    jobId: UUID,
) -> DocumentProcessingJob:
    jobQuery = (
        select(DocumentProcessingJob)
        .join(
            InvestigationDocument,
            DocumentProcessingJob.documentId
            == InvestigationDocument.documentId,
        )
        .where(
            DocumentProcessingJob.jobId == jobId,
            DocumentProcessingJob.documentId == documentId,
            InvestigationDocument.investigationId
            == investigationId,
        )
    )

    jobRecord = databaseSession.scalar(jobQuery)

    if jobRecord is None:
        raise ProcessingJobNotFoundError(
            "Processing job not found for this document "
            "and investigation."
        )

    return jobRecord
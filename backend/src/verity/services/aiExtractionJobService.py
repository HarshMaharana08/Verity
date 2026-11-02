from hashlib import sha256
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.models import (
    AiExtractionJob,
    DocumentProcessingJob,
    InvestigationDocument,
)
from verity.schemas.incidentExtractionSchemas import (
    incidentExtractionSchemaVersion,
)
from verity.services.aiExtractionService import (
    extractionPromptVersion,
)
from verity.services.processingJobService import (
    getDocumentProcessingJob,
)
from sqlalchemy import select


class AiSourceJobNotReadyError(ValueError):
    pass


class ActiveAiExtractionJobError(ValueError):
    pass


def queueAiExtractionJob(
    databaseSession: Session,
    applicationSettings: ApplicationSettings,
    investigationId: UUID,
    documentId: UUID,
    sourceProcessingJobId: UUID,
) -> AiExtractionJob:
    sourceJob = getDocumentProcessingJob(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        jobId=sourceProcessingJobId,
    )

    if sourceJob.status != "succeeded":
        raise AiSourceJobNotReadyError(
            "The source PDF-processing job must have succeeded."
        )

    sourceText = sourceJob.extractedText

    if sourceText is None or not sourceText.strip():
        raise AiSourceJobNotReadyError(
            "The source job has no extracted text."
        )

    jobRecord = AiExtractionJob(
        sourceProcessingJobId=sourceProcessingJobId,
        status="queued",
        attemptCount=0,
        providerName="groq",
        modelName=applicationSettings.groqModel,
        promptVersion=extractionPromptVersion,
        schemaVersion=incidentExtractionSchemaVersion,
        sourceTextSha256=sha256(
            sourceText.encode("utf-8")
        ).hexdigest(),
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
            == "uniqueActiveAiJobBySourceJob"
        ):
            raise ActiveAiExtractionJobError(
                "This source job already has a queued "
                "or processing AI-extraction job."
            ) from None

        raise

    except SQLAlchemyError:
        databaseSession.rollback()
        raise

    return jobRecord

class AiExtractionJobNotFoundError(LookupError):
    pass


def getAiExtractionJob(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    sourceProcessingJobId: UUID,
    aiJobId: UUID,
) -> AiExtractionJob:
    jobQuery = (
        select(AiExtractionJob)
        .join(
            DocumentProcessingJob,
            AiExtractionJob.sourceProcessingJobId
            == DocumentProcessingJob.jobId,
        )
        .join(
            InvestigationDocument,
            DocumentProcessingJob.documentId
            == InvestigationDocument.documentId,
        )
        .where(
            AiExtractionJob.aiJobId == aiJobId,
            AiExtractionJob.sourceProcessingJobId
            == sourceProcessingJobId,
            InvestigationDocument.documentId
            == documentId,
            InvestigationDocument.investigationId
            == investigationId,
        )
    )

    jobRecord = databaseSession.scalar(jobQuery)

    if jobRecord is None:
        raise AiExtractionJobNotFoundError(
            "AI-extraction job not found for this source "
            "job, document, and investigation."
        )

    return jobRecord
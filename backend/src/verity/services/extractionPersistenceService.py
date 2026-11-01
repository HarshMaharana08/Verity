from hashlib import sha256
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.models import (
    DocumentProcessingJob,
    IncidentExtractionRecord,
)
from verity.schemas.incidentExtractionSchemas import (
    incidentExtractionSchemaVersion,
)
from verity.services.aiExtractionService import (
    extractionPromptVersion,
    extractIncidentWithGroq,
)
from verity.services.processingJobService import (
    getDocumentProcessingJob,
)


class SourceJobNotReadyError(ValueError):
    pass


class ExtractionSourceChangedError(ValueError):
    pass


def createIncidentExtraction(
    databaseEngine: Engine,
    applicationSettings: ApplicationSettings,
    investigationId: UUID,
    documentId: UUID,
    sourceProcessingJobId: UUID,
) -> IncidentExtractionRecord:
    with Session(bind=databaseEngine) as databaseSession:
        sourceJob = getDocumentProcessingJob(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            jobId=sourceProcessingJobId,
        )

        if sourceJob.status != "succeeded":
            raise SourceJobNotReadyError(
                "The source PDF-processing job must have succeeded."
            )

        sourceText = sourceJob.extractedText

        if sourceText is None or not sourceText.strip():
            raise SourceJobNotReadyError(
                "The source job has no extracted text."
            )

    sourceTextSha256 = sha256(
        sourceText.encode("utf-8")
    ).hexdigest()

    # No database session remains open during the model request.
    incidentExtraction = extractIncidentWithGroq(
        sourceText=sourceText,
        applicationSettings=applicationSettings,
    )

    with Session(
        bind=databaseEngine,
        expire_on_commit=False,
    ) as databaseSession:
        with databaseSession.begin():
            currentSourceJob = databaseSession.get(
                DocumentProcessingJob,
                sourceProcessingJobId,
                with_for_update=True,
            )

            if (
                currentSourceJob is None
                or currentSourceJob.status != "succeeded"
                or currentSourceJob.documentId != documentId
                or currentSourceJob.extractedText is None
            ):
                raise ExtractionSourceChangedError(
                    "The source job changed during AI extraction."
                )

            currentSourceSha256 = sha256(
                currentSourceJob.extractedText.encode("utf-8")
            ).hexdigest()

            if currentSourceSha256 != sourceTextSha256:
                raise ExtractionSourceChangedError(
                    "The source text changed during AI extraction."
                )

            extractionRecord = IncidentExtractionRecord(
                sourceProcessingJobId=sourceProcessingJobId,
                providerName="groq",
                modelName=applicationSettings.groqModel,
                promptVersion=extractionPromptVersion,
                schemaVersion=incidentExtractionSchemaVersion,
                sourceTextSha256=sourceTextSha256,
                extractedData=incidentExtraction.model_dump(
                    mode="json"
                ),
            )

            databaseSession.add(extractionRecord)
            databaseSession.flush()
            databaseSession.refresh(extractionRecord)

    return extractionRecord
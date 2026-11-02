import logging

from sqlalchemy import Engine, func
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.models import AiExtractionChunk, AiExtractionJob
from verity.schemas.incidentExtractionSchemas import (
    IncidentExtraction,
    incidentExtractionSchemaVersion,
)
from verity.services.aiChunkService import (
    AiChunkPlanMismatchError,
    lockOwnedAiJob,
    prepareAiChunkPlan,
    renewAiJobLease,
)
from verity.services.aiExtractionService import (
    AiExtractionError,
    extractionPromptVersion,
    extractIncidentWithGroq,
)
from verity.services.incidentExtractionService import (
    validateIncidentExtraction,
)


chunkLogger = logging.getLogger(__name__)


def saveAiChunkOutcome(
    databaseEngine: Engine,
    claimedJob: AiExtractionJob,
    plannedChunk: AiExtractionChunk,
    extraction: IncidentExtraction | None = None,
    error: AiExtractionError | None = None,
) -> None:
    if (extraction is None) == (error is None):
        raise ValueError(
            "Provide exactly one extraction or error."
        )

    with Session(bind=databaseEngine) as databaseSession:
        with databaseSession.begin():
            lockOwnedAiJob(
                databaseSession,
                claimedJob.aiJobId,
                claimedJob.leaseToken,
            )

            chunkRecord = databaseSession.get(
                AiExtractionChunk,
                plannedChunk.chunkId,
                with_for_update=True,
            )

            if (
                chunkRecord is None
                or chunkRecord.aiJobId != claimedJob.aiJobId
                or chunkRecord.status != "processing"
                or chunkRecord.sourceTextSha256
                != plannedChunk.sourceTextSha256
            ):
                raise AiChunkPlanMismatchError(
                    "The processing chunk checkpoint changed."
                )

            if extraction is not None:
                chunkRecord.extractedData = extraction.model_dump(
                    mode="json"
                )
                chunkRecord.status = "succeeded"
                chunkRecord.errorCode = None
                chunkRecord.errorMessage = None
            else:
                chunkRecord.extractedData = None
                chunkRecord.status = "failed"
                chunkRecord.errorCode = error.errorCode
                chunkRecord.errorMessage = str(error)

            chunkRecord.completedAt = databaseSession.scalar(
                func.clock_timestamp().select()
            )


def executeAiChunks(
    databaseEngine: Engine,
    applicationSettings: ApplicationSettings,
    claimedJob: AiExtractionJob,
    sourceText: str,
) -> list[IncidentExtraction]:
    if (
        claimedJob.providerName != "groq"
        or claimedJob.promptVersion != extractionPromptVersion
        or claimedJob.schemaVersion
        != incidentExtractionSchemaVersion
    ):
        raise AiChunkPlanMismatchError(
            "The queued extraction configuration is unsupported."
        )

    plannedChunks = prepareAiChunkPlan(
        databaseEngine=databaseEngine,
        aiJobId=claimedJob.aiJobId,
        leaseToken=claimedJob.leaseToken,
        sourceText=sourceText,
    )

    jobSettings = applicationSettings.model_copy(
        update={"groqModel": claimedJob.modelName},
    )

    results: list[IncidentExtraction] = []

    for plannedChunk in plannedChunks:
        renewAiJobLease(
            databaseEngine,
            claimedJob.aiJobId,
            claimedJob.leaseToken,
        )

        chunkText = sourceText[
            plannedChunk.startCharacter:
            plannedChunk.endCharacter
        ]

        with Session(bind=databaseEngine) as databaseSession:
            with databaseSession.begin():
                lockOwnedAiJob(
                    databaseSession,
                    claimedJob.aiJobId,
                    claimedJob.leaseToken,
                )

                chunkRecord = databaseSession.get(
                    AiExtractionChunk,
                    plannedChunk.chunkId,
                    with_for_update=True,
                )

                if (
                    chunkRecord is None
                    or chunkRecord.aiJobId != claimedJob.aiJobId
                    or chunkRecord.sourceTextSha256
                    != plannedChunk.sourceTextSha256
                ):
                    raise AiChunkPlanMismatchError(
                        "The saved chunk checkpoint changed."
                    )

                savedPayload = chunkRecord.extractedData
                reuseCheckpoint = (
                    chunkRecord.status == "succeeded"
                )

                if reuseCheckpoint:
                    if savedPayload is None:
                        raise AiChunkPlanMismatchError(
                            "A succeeded chunk has no saved result."
                        )
                else:
                    chunkRecord.status = "processing"
                    chunkRecord.attemptCount += 1
                    chunkRecord.extractedData = None
                    chunkRecord.completedAt = None
                    chunkRecord.errorCode = None
                    chunkRecord.errorMessage = None

        if reuseCheckpoint:
            extraction = validateIncidentExtraction(
                extractionPayload=savedPayload,
                sourceText=chunkText,
            )

            chunkLogger.info(
                "Reused chunk %s/%s.",
                plannedChunk.chunkIndex + 1,
                len(plannedChunks),
            )

            results.append(extraction)
            continue

        chunkLogger.info(
            "Extracting chunk %s/%s.",
            plannedChunk.chunkIndex + 1,
            len(plannedChunks),
        )

        try:
            extraction = extractIncidentWithGroq(
                sourceText=chunkText,
                applicationSettings=jobSettings,
            )
        except AiExtractionError as extractionError:
            saveAiChunkOutcome(
                databaseEngine=databaseEngine,
                claimedJob=claimedJob,
                plannedChunk=plannedChunk,
                error=extractionError,
            )
            raise

        saveAiChunkOutcome(
            databaseEngine=databaseEngine,
            claimedJob=claimedJob,
            plannedChunk=plannedChunk,
            extraction=extraction,
        )

        results.append(extraction)

    return results
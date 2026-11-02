import argparse
import logging
import time
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.database import createDatabaseEngine
from verity.models import (
    AiExtractionJob,
    DocumentProcessingJob,
    IncidentExtractionRecord,
)
from verity.schemas.incidentExtractionSchemas import (
    IncidentExtraction,
    incidentExtractionSchemaVersion,
)
from verity.services.aiExtractionService import (
    AiExtractionError,
    extractionPromptVersion,
    extractIncidentWithGroq,
)
from verity.services.groqRequestBudgetService import (
    getTokenEncoding,
)


workerLogger = logging.getLogger(__name__)

leaseDurationSeconds = 300
maxAttempts = 3
pollIntervalSeconds = 2


class WorkerInputError(ValueError):
    def __init__(
        self,
        errorCode: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.errorCode = errorCode


def claimNextAiJob(
    databaseEngine: Engine,
) -> AiExtractionJob | None:
    with Session(
        bind=databaseEngine,
        expire_on_commit=False,
    ) as databaseSession:
        with databaseSession.begin():
            databaseTime = databaseSession.scalar(
                select(func.clock_timestamp())
            )

            jobQuery = (
                select(AiExtractionJob)
                .where(
                    or_(
                        and_(
                            AiExtractionJob.status == "queued",
                            AiExtractionJob.availableAt
                            <= databaseTime,
                        ),
                        and_(
                            AiExtractionJob.status == "processing",
                            AiExtractionJob.leaseExpiresAt
                            <= databaseTime,
                        ),
                    )
                )
                .order_by(
                    AiExtractionJob.availableAt,
                    AiExtractionJob.createdAt,
                    AiExtractionJob.aiJobId,
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )

            jobRecord = databaseSession.scalar(jobQuery)

            if jobRecord is None:
                return None

            if jobRecord.attemptCount >= maxAttempts:
                jobRecord.status = "failed"
                jobRecord.completedAt = databaseTime
                jobRecord.leaseToken = None
                jobRecord.leaseExpiresAt = None
                jobRecord.errorCode = "attemptsExhausted"
                jobRecord.errorMessage = (
                    "Processing stopped after the maximum "
                    "number of attempts."
                )
                return None

            jobRecord.status = "processing"
            jobRecord.attemptCount += 1
            jobRecord.leaseToken = uuid4()
            jobRecord.leaseExpiresAt = (
                databaseTime
                + timedelta(seconds=leaseDurationSeconds)
            )
            jobRecord.startedAt = databaseTime
            jobRecord.completedAt = None
            jobRecord.errorCode = None
            jobRecord.errorMessage = None

        # Return a detached snapshot of this worker's claim.
        return jobRecord


def loadAiSourceText(
    databaseEngine: Engine,
    claimedJob: AiExtractionJob,
) -> str:
    if (
        claimedJob.providerName != "groq"
        or claimedJob.promptVersion != extractionPromptVersion
        or claimedJob.schemaVersion
        != incidentExtractionSchemaVersion
    ):
        raise WorkerInputError(
            "unsupportedJobConfiguration",
            "The queued provider or prompt/schema versions "
            "are not supported by this worker.",
        )

    with Session(bind=databaseEngine) as databaseSession:
        sourceJob = databaseSession.get(
            DocumentProcessingJob,
            claimedJob.sourceProcessingJobId,
        )

        if (
            sourceJob is None
            or sourceJob.status != "succeeded"
            or not sourceJob.extractedText
            or not sourceJob.extractedText.strip()
        ):
            raise WorkerInputError(
                "sourceNotReady",
                "The source job must have succeeded "
                "and contain extracted text.",
            )

        sourceText = sourceJob.extractedText

    sourceHash = sha256(
        sourceText.encode("utf-8")
    ).hexdigest()

    if sourceHash != claimedJob.sourceTextSha256:
        raise WorkerInputError(
            "sourceChanged",
            "The source text differs from the queued snapshot.",
        )

    return sourceText


def finishAiJob(
    databaseEngine: Engine,
    claimedJob: AiExtractionJob,
    extraction: IncidentExtraction | None = None,
    errorCode: str | None = None,
    errorMessage: str | None = None,
) -> bool:
    if extraction is None and (
        errorCode is None or errorMessage is None
    ):
        raise ValueError(
            "Completion requires an extraction or failure details."
        )

    with Session(
        bind=databaseEngine,
        expire_on_commit=False,
    ) as databaseSession:
        with databaseSession.begin():
            currentJob = databaseSession.scalar(
                select(AiExtractionJob)
                .where(
                    AiExtractionJob.aiJobId
                    == claimedJob.aiJobId,
                )
                .with_for_update()
            )

            if (
                currentJob is None
                or currentJob.status != "processing"
                or currentJob.leaseToken
                != claimedJob.leaseToken
            ):
                return False

            if extraction is not None:
                sourceJob = databaseSession.get(
                    DocumentProcessingJob,
                    currentJob.sourceProcessingJobId,
                    with_for_update=True,
                )

                if (
                    sourceJob is None
                    or sourceJob.status != "succeeded"
                    or sourceJob.extractedText is None
                    or sha256(
                        sourceJob.extractedText.encode("utf-8")
                    ).hexdigest()
                    != currentJob.sourceTextSha256
                ):
                    raise WorkerInputError(
                        "sourceChanged",
                        "The source changed before the result "
                        "could be saved.",
                    )

            databaseTime = databaseSession.scalar(
                select(func.clock_timestamp())
            )

            if (
                currentJob.leaseExpiresAt is None
                or currentJob.leaseExpiresAt <= databaseTime
            ):
                return False

            if extraction is not None:
                resultRecord = IncidentExtractionRecord(
                    sourceProcessingJobId=(
                        currentJob.sourceProcessingJobId
                    ),
                    providerName=currentJob.providerName,
                    modelName=currentJob.modelName,
                    promptVersion=currentJob.promptVersion,
                    schemaVersion=currentJob.schemaVersion,
                    sourceTextSha256=currentJob.sourceTextSha256,
                    extractedData=extraction.model_dump(
                        mode="json"
                    ),
                )

                databaseSession.add(resultRecord)
                databaseSession.flush()

                currentJob.extractionId = (
                    resultRecord.extractionId
                )
                currentJob.status = "succeeded"
                currentJob.errorCode = None
                currentJob.errorMessage = None
            else:
                currentJob.status = "failed"
                currentJob.errorCode = errorCode
                currentJob.errorMessage = errorMessage

            currentJob.completedAt = databaseTime
            currentJob.leaseToken = None
            currentJob.leaseExpiresAt = None

        if currentJob.status == "succeeded":
            workerLogger.info(
                "AI job %s succeeded; extraction ID: %s.",
                currentJob.aiJobId,
                currentJob.extractionId,
            )
        else:
            workerLogger.warning(
                "AI job %s failed; error code: %s.",
                currentJob.aiJobId,
                currentJob.errorCode,
            )

    return True

def scheduleAiJobRetry(
    databaseEngine: Engine,
    claimedJob: AiExtractionJob,
    jobError: AiExtractionError,
) -> bool:
    if claimedJob.attemptCount >= maxAttempts:
        return finishAiJob(
            databaseEngine=databaseEngine,
            claimedJob=claimedJob,
            errorCode="attemptsExhausted",
            errorMessage=(
                "Maximum processing attempts reached. "
                f"Last error: {jobError}"
            ),
        )

    backoffSeconds = (
        65 * (2 ** (claimedJob.attemptCount - 1))
    )

    retryDelaySeconds = max(
        backoffSeconds,
        jobError.retryAfterSeconds or 0.0,
    )

    with Session(bind=databaseEngine) as databaseSession:
        with databaseSession.begin():
            currentJob = databaseSession.scalar(
                select(AiExtractionJob)
                .where(
                    AiExtractionJob.aiJobId
                    == claimedJob.aiJobId,
                )
                .with_for_update()
            )

            if (
                currentJob is None
                or currentJob.status != "processing"
                or currentJob.leaseToken
                != claimedJob.leaseToken
            ):
                return False

            databaseTime = databaseSession.scalar(
                select(func.clock_timestamp())
            )

            if (
                currentJob.leaseExpiresAt is None
                or currentJob.leaseExpiresAt <= databaseTime
            ):
                return False

            currentJob.status = "queued"
            currentJob.availableAt = (
                databaseTime
                + timedelta(seconds=retryDelaySeconds)
            )
            currentJob.completedAt = None
            currentJob.leaseToken = None
            currentJob.leaseExpiresAt = None
            currentJob.errorCode = jobError.errorCode
            currentJob.errorMessage = str(jobError)

    workerLogger.warning(
        "AI job %s scheduled for retry in %.1f seconds.",
        claimedJob.aiJobId,
        retryDelaySeconds,
    )

    return True

def processAiJob(
    databaseEngine: Engine,
    applicationSettings: ApplicationSettings,
    claimedJob: AiExtractionJob,
) -> None:
    workerLogger.info(
        "Processing AI job %s; attempt %s.",
        claimedJob.aiJobId,
        claimedJob.attemptCount,
    )

    try:
        sourceText = loadAiSourceText(
            databaseEngine,
            claimedJob,
        )

        jobSettings = applicationSettings.model_copy(
            update={"groqModel": claimedJob.modelName},
        )

        extraction = extractIncidentWithGroq(
            sourceText=sourceText,
            applicationSettings=jobSettings,
        )

        completed = finishAiJob(
            databaseEngine=databaseEngine,
            claimedJob=claimedJob,
            extraction=extraction,
        )

    except WorkerInputError as jobError:
        completed = finishAiJob(
            databaseEngine=databaseEngine,
            claimedJob=claimedJob,
            errorCode=jobError.errorCode,
            errorMessage=str(jobError),
        )

    except AiExtractionError as jobError:
        if jobError.retryable:
            completed = scheduleAiJobRetry(
                databaseEngine=databaseEngine,
                claimedJob=claimedJob,
                jobError=jobError,
            )
        else:
            completed = finishAiJob(
                databaseEngine=databaseEngine,
                claimedJob=claimedJob,
                errorCode=jobError.errorCode,
                errorMessage=str(jobError),
            )

    if not completed:
        workerLogger.warning(
            "AI job %s result was discarded because "
            "its lease expired or ownership changed.",
            claimedJob.aiJobId,
        )


def runWorker() -> None:
    argumentParser = argparse.ArgumentParser(
        description="Process Verity AI-extraction jobs."
    )
    argumentParser.add_argument(
        "--once",
        action="store_true",
        help="Check for one eligible job, then exit.",
    )
    arguments = argumentParser.parse_args()

    backendRoot = Path(__file__).resolve().parents[2]

    applicationSettings = ApplicationSettings(
        _env_file=backendRoot.parent / ".env",
        _env_file_encoding="utf-8",
    )

    # Initialize the tokenizer before acquiring a job lease.
    getTokenEncoding()

    databaseEngine = createDatabaseEngine(
        applicationSettings
    )

    try:
        workerLogger.info("AI-extraction worker started.")

        while True:
            try:
                claimedJob = claimNextAiJob(databaseEngine)

                if claimedJob is None:
                    if arguments.once:
                        workerLogger.info(
                            "No AI job claimed on this check."
                        )
                else:
                    processAiJob(
                        databaseEngine=databaseEngine,
                        applicationSettings=applicationSettings,
                        claimedJob=claimedJob,
                    )

            except SQLAlchemyError:
                workerLogger.error(
                    "A database operation failed. "
                    "Unfinished claims can recover "
                    "after lease expiry."
                )

                if arguments.once:
                    raise SystemExit(1) from None

            if arguments.once:
                break

            time.sleep(pollIntervalSeconds)

    except KeyboardInterrupt:
        workerLogger.info("AI-extraction worker stopped.")

    finally:
        databaseEngine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    runWorker()
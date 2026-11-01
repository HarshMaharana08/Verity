import argparse
import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Engine, and_, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.database import createDatabaseEngine
from verity.models import (
    DocumentProcessingJob,
    InvestigationDocument,
)
from verity.services.documentService import (
    DocumentNotFoundError,
    DocumentStorageError,
    getDocumentDownloadDetails,
)
from verity.services.pdfExtractionService import (
    PdfTextExtractionError,
    extractPdfText,
)


workerLogger = logging.getLogger(__name__)

leaseDurationSeconds = 120
maxAttempts = 3
pollIntervalSeconds = 2


@dataclass(frozen=True)
class ClaimedJob:
    jobId: UUID
    documentId: UUID
    leaseToken: UUID


def claimNextJob(
    databaseEngine: Engine,
) -> ClaimedJob | None:
    with Session(bind=databaseEngine) as databaseSession:
        with databaseSession.begin():
            databaseTime = databaseSession.scalar(
                select(func.clock_timestamp())
            )

            jobQuery = (
                select(DocumentProcessingJob)
                .where(
                    or_(
                        DocumentProcessingJob.status == "queued",
                        and_(
                            DocumentProcessingJob.status
                            == "processing",
                            DocumentProcessingJob.leaseExpiresAt
                            <= databaseTime,
                        ),
                    )
                )
                .order_by(
                    DocumentProcessingJob.createdAt,
                    DocumentProcessingJob.jobId,
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
                jobRecord.extractedText = None
                jobRecord.errorMessage = (
                    "Processing stopped after the maximum "
                    "number of attempts."
                )

                workerLogger.warning(
                    "Job %s exhausted its attempts.",
                    jobRecord.jobId,
                )
                return None

            leaseToken = uuid4()

            jobRecord.status = "processing"
            jobRecord.attemptCount += 1
            jobRecord.leaseToken = leaseToken
            jobRecord.leaseExpiresAt = (
                databaseTime
                + timedelta(seconds=leaseDurationSeconds)
            )
            jobRecord.startedAt = databaseTime
            jobRecord.completedAt = None
            jobRecord.extractedText = None
            jobRecord.errorMessage = None

            claimedJob = ClaimedJob(
                jobId=jobRecord.jobId,
                documentId=jobRecord.documentId,
                leaseToken=leaseToken,
            )

        return claimedJob


def finishJob(
    databaseEngine: Engine,
    claimedJob: ClaimedJob,
    extractedText: str | None,
    errorMessage: str | None,
) -> bool:
    finalStatus = (
        "succeeded" if errorMessage is None else "failed"
    )

    with Session(bind=databaseEngine) as databaseSession:
        with databaseSession.begin():
            completionQuery = (
                update(DocumentProcessingJob)
                .where(
                    DocumentProcessingJob.jobId
                    == claimedJob.jobId,
                    DocumentProcessingJob.status
                    == "processing",
                    DocumentProcessingJob.leaseToken
                    == claimedJob.leaseToken,
                    DocumentProcessingJob.leaseExpiresAt
                    > func.clock_timestamp(),
                )
                .values(
                    status=finalStatus,
                    extractedText=extractedText,
                    errorMessage=errorMessage,
                    completedAt=func.clock_timestamp(),
                    leaseToken=None,
                    leaseExpiresAt=None,
                )
                .returning(DocumentProcessingJob.jobId)
                .execution_options(synchronize_session=False)
            )

            completedJobId = databaseSession.scalar(
                completionQuery
            )

        return completedJobId is not None


def processClaimedJob(
    databaseEngine: Engine,
    documentStorageRoot: Path,
    claimedJob: ClaimedJob,
) -> None:
    workerLogger.info(
        "Processing job %s for document %s.",
        claimedJob.jobId,
        claimedJob.documentId,
    )

    extractedText = None
    errorMessage = None

    try:
        with Session(bind=databaseEngine) as databaseSession:
            documentRecord = databaseSession.get(
                InvestigationDocument,
                claimedJob.documentId,
            )

            if documentRecord is None:
                raise DocumentNotFoundError(
                    "The document record is unavailable."
                )

            documentPath, _ = getDocumentDownloadDetails(
                databaseSession=databaseSession,
                investigationId=documentRecord.investigationId,
                documentId=claimedJob.documentId,
                documentStorageRoot=documentStorageRoot,
            )

        # Parsing runs after the read session has closed.
        extractedText = extractPdfText(documentPath)

    except PdfTextExtractionError as extractionError:
        errorMessage = str(extractionError)

    except (DocumentNotFoundError, DocumentStorageError):
        errorMessage = (
            "The stored document is unavailable for processing."
        )

    except SQLAlchemyError:
        # Leave the lease in place for recovery after expiry.
        raise

    except Exception as processingError:
        workerLogger.error(
            "Unexpected extraction error for job %s: %s",
            claimedJob.jobId,
            type(processingError).__name__,
        )
        errorMessage = (
            "An unexpected PDF processing error occurred."
        )

    completed = finishJob(
        databaseEngine=databaseEngine,
        claimedJob=claimedJob,
        extractedText=extractedText,
        errorMessage=errorMessage,
    )

    if not completed:
        workerLogger.warning(
            "Job %s result was discarded because its "
            "lease expired or ownership changed.",
            claimedJob.jobId,
        )
        return

    if errorMessage is not None:
        workerLogger.warning(
            "Job %s failed: %s",
            claimedJob.jobId,
            errorMessage,
        )
        return

    workerLogger.info(
        "Job %s succeeded; saved %s characters.",
        claimedJob.jobId,
        len(extractedText or ""),
    )


def runWorker() -> None:
    argumentParser = argparse.ArgumentParser(
        description="Process Verity document jobs."
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

    documentStorageRoot = (
        backendRoot / applicationSettings.documentStorageRoot
    ).resolve()

    databaseEngine = createDatabaseEngine(
        applicationSettings
    )

    try:
        workerLogger.info("Document worker started.")

        while True:
            try:
                claimedJob = claimNextJob(databaseEngine)

                if claimedJob is None:
                    if arguments.once:
                        workerLogger.info(
                            "No job claimed on this check."
                        )
                else:
                    processClaimedJob(
                        databaseEngine=databaseEngine,
                        documentStorageRoot=documentStorageRoot,
                        claimedJob=claimedJob,
                    )

            except SQLAlchemyError:
                workerLogger.error(
                    "A database operation failed. "
                    "Unfinished jobs remain eligible for "
                    "recovery after lease expiry."
                )

                if arguments.once:
                    raise SystemExit(1) from None

            if arguments.once:
                break

            time.sleep(pollIntervalSeconds)

    except KeyboardInterrupt:
        workerLogger.info("Document worker stopped.")

    finally:
        databaseEngine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    runWorker()
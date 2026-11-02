import argparse
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event, Thread
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.database import createDatabaseEngine
from verity.services.rcaDraftValidationService import (
    InvalidRcaDraftError,
)
from verity.services.rcaGenerationService import (
    RcaGenerationError,
    runRcaWithGroq,
)
from verity.services.rcaWorkerService import (
    RcaLeaseLostError,
    claimRcaJob,
    recordRcaFailure,
    renewRcaJobLease,
    saveRcaDraft,
)


workerLogger = logging.getLogger(__name__)
heartbeatIntervalSeconds = 30.0


@contextmanager
def maintainRcaLease(
    databaseEngine: Engine,
    rcaJobId: UUID,
    leaseToken: UUID,
) -> Iterator[None]:
    stopEvent = Event()
    heartbeatErrors: list[Exception] = []

    def runHeartbeat() -> None:
        while not stopEvent.wait(heartbeatIntervalSeconds):
            try:
                with Session(
                    bind=databaseEngine
                ) as databaseSession:
                    with databaseSession.begin():
                        renewRcaJobLease(
                            databaseSession,
                            rcaJobId,
                            leaseToken,
                        )

            except Exception as heartbeatError:
                heartbeatErrors.append(heartbeatError)
                stopEvent.set()
                return

    heartbeatThread = Thread(
        target=runHeartbeat,
        name=f"rca-lease-{rcaJobId}",
        daemon=True,
    )
    heartbeatThread.start()

    try:
        yield

    finally:
        stopEvent.set()
        heartbeatThread.join()

        if heartbeatErrors:
            raise RcaLeaseLostError(
                "RCA lease renewal failed; "
                "discarding this worker's outcome."
            ) from None


def processOneRcaJob(
    databaseEngine: Engine,
    applicationSettings: ApplicationSettings,
    rcaJobId: UUID | None = None,
) -> bool:
    # Keep the claimed values available after commit and session close.
    with Session(
        bind=databaseEngine,
        expire_on_commit=False,
    ) as databaseSession:
        with databaseSession.begin():
            claimedJob = claimRcaJob(
                databaseSession,
                rcaJobId,
            )

    if claimedJob is None:
        return False

    claimedJobId = claimedJob.rcaJobId
    leaseToken = claimedJob.leaseToken

    workerLogger.info(
        "Claimed RCA job %s, attempt %s.",
        claimedJobId,
        claimedJob.attemptCount,
    )

    result = None
    generationError = None

    try:
        with maintainRcaLease(
            databaseEngine,
            claimedJobId,
            leaseToken,
        ):
            result = runRcaWithGroq(
                jobRecord=claimedJob,
                applicationSettings=applicationSettings,
            )

    except RcaLeaseLostError:
        workerLogger.warning(
            "Lease lost for RCA job %s; outcome discarded.",
            claimedJobId,
        )
        return True

    except RcaGenerationError as error:
        generationError = error

    except (InvalidRcaDraftError, ValidationError):
        generationError = RcaGenerationError(
            "The generated RCA draft failed validation.",
            errorCode="invalidRcaDraft",
            retryable=False,
        )

    except Exception:
        workerLogger.exception(
            "Unexpected generation failure for RCA job %s.",
            claimedJobId,
        )
        generationError = RcaGenerationError(
            "An unexpected RCA generation error occurred.",
            errorCode="unexpectedRcaGenerationFailure",
            retryable=False,
        )

    # Heartbeat has stopped. Recheck ownership while saving.
    try:
        with Session(bind=databaseEngine) as databaseSession:
            with databaseSession.begin():
                if generationError is not None:
                    recordRcaFailure(
                        databaseSession,
                        claimedJobId,
                        leaseToken,
                        generationError,
                    )
                    savedDraftId = None

                else:
                    if result is None:
                        raise RuntimeError(
                            "RCA generation returned no result."
                        )

                    savedDraft = saveRcaDraft(
                        databaseSession,
                        claimedJobId,
                        leaseToken,
                        result,
                    )
                    savedDraftId = savedDraft.rcaDraftId

        # Report completion only after the transaction commits.
        if generationError is not None:
            workerLogger.warning(
                "Recorded RCA failure for job %s: code=%s.",
                claimedJobId,
                generationError.errorCode,
            )
        else:
            workerLogger.info(
                "RCA job %s succeeded. Draft ID: %s.",
                claimedJobId,
                savedDraftId,
            )

    except RcaLeaseLostError:
        workerLogger.warning(
            "Lease lost before saving RCA job %s; "
            "outcome discarded.",
            claimedJobId,
        )

    return True


def main() -> int:
    argumentParser = argparse.ArgumentParser(
        description="Process queued Verity RCA jobs.",
    )
    argumentParser.add_argument(
        "--env-file",
        default="../.env",
        help="Settings file path, relative to the current directory.",
    )
    argumentParser.add_argument(
        "--once",
        action="store_true",
        help="Try one claim and then exit.",
    )
    argumentParser.add_argument(
        "--job-id",
        type=UUID,
        help="Target one job; requires --once.",
    )

    arguments = argumentParser.parse_args()

    if arguments.job_id is not None and not arguments.once:
        argumentParser.error("--job-id requires --once")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    applicationSettings = ApplicationSettings(
        _env_file=arguments.env_file,
        _env_file_encoding="utf-8",
    )
    databaseEngine = createDatabaseEngine(applicationSettings)

    try:
        if arguments.once:
            processed = processOneRcaJob(
                databaseEngine,
                applicationSettings,
                arguments.job_id,
            )

            if not processed:
                workerLogger.info("No eligible RCA job claimed.")

            return 0

        idleEvent = Event()

        while True:
            processed = processOneRcaJob(
                databaseEngine,
                applicationSettings,
            )

            if not processed:
                idleEvent.wait(2.0)

    except KeyboardInterrupt:
        workerLogger.info("RCA worker stopped.")
        return 0

    except Exception:
        workerLogger.exception("RCA worker stopped after an error.")
        return 1

    finally:
        databaseEngine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
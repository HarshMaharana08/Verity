from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from verity.models import RcaJob

from verity.models import RcaDraftRecord
from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.services.rcaDraftValidationService import (
    InvalidRcaDraftError,
    validateRcaDraft,
)

from math import isfinite

from verity.services.rcaGenerationService import (
    RcaGenerationError,
)


rcaLeaseSeconds = 180
rcaMaxAttempts = 3


class RcaLeaseLostError(RuntimeError):
    pass


def claimRcaJob(
    databaseSession: Session,
    rcaJobId: UUID | None = None,
) -> RcaJob | None:
    databaseNow = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    claimQuery = (
        select(RcaJob)
        .where(
            or_(
                (
                    (RcaJob.status == "queued")
                    & (RcaJob.availableAt <= databaseNow)
                ),
                (
                    (RcaJob.status == "processing")
                    & (RcaJob.leaseExpiresAt <= databaseNow)
                ),
            )
        )
        .order_by(
            RcaJob.availableAt,
            RcaJob.createdAt,
            RcaJob.rcaJobId,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    if rcaJobId is not None:
        claimQuery = claimQuery.where(
            RcaJob.rcaJobId == rcaJobId
        )

    jobRecord = databaseSession.scalar(claimQuery)

    if jobRecord is None:
        return None

    # Refresh database time after selecting the locked row.
    databaseNow = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    if jobRecord.attemptCount >= rcaMaxAttempts:
        jobRecord.status = "failed"
        jobRecord.completedAt = databaseNow
        jobRecord.leaseToken = None
        jobRecord.leaseExpiresAt = None
        jobRecord.errorCode = "rcaAttemptsExhausted"
        jobRecord.errorMessage = (
            "The RCA job reached its maximum attempt count."
        )
        databaseSession.flush()
        return None

    jobRecord.status = "processing"
    jobRecord.attemptCount += 1
    jobRecord.leaseToken = uuid4()
    jobRecord.leaseExpiresAt = (
        databaseNow + timedelta(seconds=rcaLeaseSeconds)
    )

    if jobRecord.startedAt is None:
        jobRecord.startedAt = databaseNow

    jobRecord.completedAt = None
    jobRecord.errorCode = None
    jobRecord.errorMessage = None

    databaseSession.flush()

    return jobRecord


def lockOwnedRcaJob(
    databaseSession: Session,
    rcaJobId: UUID,
    leaseToken: UUID,
) -> RcaJob:
    jobRecord = databaseSession.scalar(
        select(RcaJob)
        .where(RcaJob.rcaJobId == rcaJobId)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    databaseNow = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    if (
        jobRecord is None
        or jobRecord.status != "processing"
        or jobRecord.leaseToken != leaseToken
        or jobRecord.leaseExpiresAt is None
        or jobRecord.leaseExpiresAt <= databaseNow
    ):
        raise RcaLeaseLostError(
            "The worker no longer owns an active RCA job lease."
        )

    return jobRecord


def renewRcaJobLease(
    databaseSession: Session,
    rcaJobId: UUID,
    leaseToken: UUID,
) -> None:
    jobRecord = lockOwnedRcaJob(
        databaseSession,
        rcaJobId,
        leaseToken,
    )

    databaseNow = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    jobRecord.leaseExpiresAt = (
        databaseNow + timedelta(seconds=rcaLeaseSeconds)
    )

    databaseSession.flush()
    
def saveRcaDraft(
    databaseSession: Session,
    rcaJobId: UUID,
    leaseToken: UUID,
    validatedDraft: ValidatedRcaDraft,
) -> RcaDraftRecord:
    jobRecord = lockOwnedRcaJob(
        databaseSession,
        rcaJobId,
        leaseToken,
    )

    if (
        validatedDraft.rcaJobId != jobRecord.rcaJobId
        or validatedDraft.sourceReviewId
        != jobRecord.sourceReviewId
        or validatedDraft.inputSha256 != jobRecord.inputSha256
        or validatedDraft.schemaVersion != jobRecord.schemaVersion
        or validatedDraft.sourceFacts.model_dump(mode="json")
        != jobRecord.inputSnapshot
    ):
        raise InvalidRcaDraftError(
            "The generated draft does not match this job's "
            "saved input and configuration."
        )

    # Recheck content against the locked database record.
    checkedDraft = validateRcaDraft(
        jobRecord=jobRecord,
        draftContent=validatedDraft.content,
    )

    draftRecord = RcaDraftRecord(
        rcaJobId=jobRecord.rcaJobId,
        schemaVersion=jobRecord.schemaVersion,
        draftData=checkedDraft.model_dump(mode="json"),
    )

    databaseSession.add(draftRecord)
    databaseSession.flush()

    databaseNow = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    if jobRecord.leaseExpiresAt <= databaseNow:
        raise RcaLeaseLostError(
            "The RCA lease expired before completion. "
            "The transaction must be rolled back."
        )

    jobRecord.status = "succeeded"
    jobRecord.completedAt = databaseNow
    jobRecord.leaseToken = None
    jobRecord.leaseExpiresAt = None
    jobRecord.errorCode = None
    jobRecord.errorMessage = None

    databaseSession.flush()
    databaseSession.refresh(draftRecord)

    return draftRecord

def recordRcaFailure(
    databaseSession: Session,
    rcaJobId: UUID,
    leaseToken: UUID,
    error: RcaGenerationError,
) -> None:
    jobRecord = lockOwnedRcaJob(
        databaseSession,
        rcaJobId,
        leaseToken,
    )

    databaseNow = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    canRetry = (
        error.retryable
        and jobRecord.attemptCount < rcaMaxAttempts
    )

    jobRecord.errorCode = error.errorCode[:100]
    jobRecord.errorMessage = str(error)[:1500]
    jobRecord.leaseToken = None
    jobRecord.leaseExpiresAt = None

    if canRetry:
        backoffSeconds = min(
            300.0,
            65.0 * (2 ** (jobRecord.attemptCount - 1)),
        )

        providerDelay = error.retryAfterSeconds

        if (
            providerDelay is None
            or not isfinite(providerDelay)
            or providerDelay < 0
        ):
            providerDelay = 0.0

        delaySeconds = max(
            backoffSeconds,
            providerDelay,
        )

        jobRecord.status = "queued"
        jobRecord.availableAt = (
            databaseNow + timedelta(seconds=delaySeconds)
        )
        jobRecord.completedAt = None

    else:
        jobRecord.status = "failed"
        jobRecord.completedAt = databaseNow

    databaseSession.flush()
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verity.models import RcaDraftRecord
from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.services.rcaDraftValidationService import (
    validateRcaDraft,
)
from verity.services.rcaJobService import getRcaJob


class RcaDraftNotReadyError(ValueError):
    pass


def getRcaDraft(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
) -> RcaDraftRecord:
    jobRecord = getRcaJob(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
    )

    if jobRecord.status != "succeeded":
        raise RcaDraftNotReadyError(
            "This RCA job has no successful draft result. "
            f"Current status: {jobRecord.status}."
        )

    draftRecord = databaseSession.scalar(
        select(RcaDraftRecord).where(
            RcaDraftRecord.rcaJobId == jobRecord.rcaJobId
        )
    )

    if draftRecord is None:
        raise ValueError(
            "A succeeded RCA job has no saved draft."
        )

    savedDraft = ValidatedRcaDraft.model_validate(
        draftRecord.draftData
    )

    if (
        savedDraft.rcaJobId != jobRecord.rcaJobId
        or savedDraft.sourceReviewId != jobRecord.sourceReviewId
        or savedDraft.inputSha256 != jobRecord.inputSha256
        or savedDraft.schemaVersion != jobRecord.schemaVersion
        or draftRecord.schemaVersion != jobRecord.schemaVersion
        or savedDraft.sourceFacts.model_dump(mode="json")
        != jobRecord.inputSnapshot
    ):
        raise ValueError(
            "The saved RCA draft does not match its source job."
        )

    checkedDraft = validateRcaDraft(
        jobRecord=jobRecord,
        draftContent=savedDraft.content,
    )

    if checkedDraft.model_dump(mode="json") != draftRecord.draftData:
        raise ValueError(
            "The saved RCA draft is inconsistent."
        )

    return draftRecord
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from verity.models import RcaDraftRecord, RcaEvidenceRequest
from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.schemas.rcaEvidenceRequestSchemas import (
    RcaEvidenceRequestCreate,
)
from verity.services.rcaReviewService import (
    getRcaReviewById,
)


class InvalidRcaEvidenceRequestError(ValueError):
    pass


class RcaEvidenceRequestNotFoundError(LookupError):
    pass


def createRcaEvidenceRequest(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    requestInput: RcaEvidenceRequestCreate,
) -> RcaEvidenceRequest:
    try:
        sourceReview = getRcaReviewById(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
        )

        draftRecord = databaseSession.get(
            RcaDraftRecord,
            sourceReview.rcaDraftId,
        )

        if draftRecord is None:
            raise ValueError(
                "The RCA review's source draft is missing."
            )

        sourceDraft = ValidatedRcaDraft.model_validate(
            draftRecord.draftData
        )

        hypothesisIds = {
            hypothesis.hypothesisId
            for hypothesis in sourceDraft.content.hypotheses
        }

        if (
            requestInput.hypothesisId is not None
            and requestInput.hypothesisId not in hypothesisIds
        ):
            raise InvalidRcaEvidenceRequestError(
                "The hypothesis does not belong to this RCA draft."
            )

        requestRecord = RcaEvidenceRequest(
            rcaReviewId=sourceReview.rcaReviewId,
            hypothesisId=requestInput.hypothesisId,
            requestText=requestInput.requestText,
            rationale=requestInput.rationale,
            requestedByLabel=requestInput.requestedByLabel,
        )

        databaseSession.add(requestRecord)
        databaseSession.flush()
        databaseSession.refresh(requestRecord)
        databaseSession.commit()

    except Exception:
        databaseSession.rollback()
        raise

    return requestRecord


def getRcaEvidenceRequest(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
) -> RcaEvidenceRequest:
    sourceReview = getRcaReviewById(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
        rcaReviewId=rcaReviewId,
    )

    requestRecord = databaseSession.scalar(
        select(RcaEvidenceRequest).where(
            RcaEvidenceRequest.evidenceRequestId
            == evidenceRequestId,
            RcaEvidenceRequest.rcaReviewId
            == sourceReview.rcaReviewId,
        )
    )

    if requestRecord is None:
        raise RcaEvidenceRequestNotFoundError(
            "Evidence request not found for this RCA review."
        )

    return requestRecord

def listRcaEvidenceRequests(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    pageSize: int,
    pageOffset: int,
) -> tuple[list[RcaEvidenceRequest], bool]:
    sourceReview = getRcaReviewById(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
        rcaReviewId=rcaReviewId,
    )

    records = list(
        databaseSession.scalars(
            select(RcaEvidenceRequest)
            .where(
                RcaEvidenceRequest.rcaReviewId
                == sourceReview.rcaReviewId
            )
            .order_by(
                RcaEvidenceRequest.createdAt.desc(),
                RcaEvidenceRequest.evidenceRequestId.desc(),
            )
            .offset(pageOffset)
            .limit(pageSize + 1)
        ).all()
    )

    return records[:pageSize], len(records) > pageSize
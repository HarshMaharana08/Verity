from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verity.models import RcaDraftRecord, RcaReview
from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.schemas.rcaReviewSchemas import RcaReviewRequest
from verity.services.rcaDraftQueryService import getRcaDraft
from verity.services.rcaEvidenceAssessmentService import (
    assessRcaEvidence,
)


class RcaReviewConflictError(ValueError):
    pass


class InvalidRcaReviewError(ValueError):
    pass


def createRcaReview(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    reviewRequest: RcaReviewRequest,
) -> RcaReview:
    try:
        scopedDraft = getRcaDraft(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        # Serialize review revision creation for this draft.
        draftRecord = databaseSession.scalar(
            select(RcaDraftRecord)
            .where(
                RcaDraftRecord.rcaDraftId
                == scopedDraft.rcaDraftId
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        if draftRecord is None:
            raise InvalidRcaReviewError(
                "The source RCA draft is no longer available."
            )

        latestRevision = databaseSession.scalar(
            select(func.max(RcaReview.revisionNumber))
            .where(
                RcaReview.rcaDraftId == draftRecord.rcaDraftId
            )
        ) or 0

        if reviewRequest.expectedRevision != latestRevision:
            raise RcaReviewConflictError(
                "The RCA review revision has changed. "
                f"Current revision is {latestRevision}."
            )

        validatedDraft = ValidatedRcaDraft.model_validate(
            draftRecord.draftData
        )
        assessment = assessRcaEvidence(validatedDraft)

        if (
            reviewRequest.expectedAssessmentVersion
            != assessment.assessmentVersion
        ):
            raise RcaReviewConflictError(
                "The evidence assessment version has changed. "
                "Retrieve the current assessment before saving."
            )

        hypothesisIds = {
            hypothesis.hypothesisId
            for hypothesis in validatedDraft.content.hypotheses
        }

        findingKeys = {
            f"{item.hypothesisId}:{finding.findingCode}"
            for item in assessment.hypotheses
            for finding in item.findings
        }

        unknownHypotheses = (
            set(reviewRequest.hypothesisDecisions)
            - hypothesisIds
        )

        if unknownHypotheses:
            raise InvalidRcaReviewError(
                "Unknown hypothesis IDs: "
                + ", ".join(sorted(unknownHypotheses))
            )

        unknownFindings = (
            set(reviewRequest.findingResponses)
            - findingKeys
        )

        if unknownFindings:
            raise InvalidRcaReviewError(
                "Unknown evidence findings: "
                + ", ".join(sorted(unknownFindings))
            )

        if reviewRequest.reviewStatus == "reviewed":
            missingHypotheses = (
                hypothesisIds
                - set(reviewRequest.hypothesisDecisions)
            )

            if missingHypotheses:
                raise InvalidRcaReviewError(
                    "Completed review requires decisions for: "
                    + ", ".join(sorted(missingHypotheses))
                )

            missingFindings = (
                findingKeys
                - set(reviewRequest.findingResponses)
            )

            if missingFindings:
                raise InvalidRcaReviewError(
                    "Completed review requires responses for: "
                    + ", ".join(sorted(missingFindings))
                )

        requestData = reviewRequest.model_dump(mode="json")

        reviewRecord = RcaReview(
            rcaDraftId=draftRecord.rcaDraftId,
            revisionNumber=latestRevision + 1,
            reviewStatus=reviewRequest.reviewStatus,
            reviewerLabel=reviewRequest.reviewerLabel,
            assessmentVersion=assessment.assessmentVersion,
            assessmentSnapshot=assessment.model_dump(mode="json"),
            hypothesisDecisions=requestData[
                "hypothesisDecisions"
            ],
            findingResponses=requestData["findingResponses"],
            reviewNote=reviewRequest.reviewNote,
        )

        databaseSession.add(reviewRecord)
        databaseSession.flush()
        databaseSession.refresh(reviewRecord)
        databaseSession.commit()

    except Exception:
        databaseSession.rollback()
        raise

    return reviewRecord

class RcaReviewNotFoundError(LookupError):
    pass


def getLatestRcaReview(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
) -> RcaReview:
    draftRecord = getRcaDraft(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
    )

    reviewRecord = databaseSession.scalar(
        select(RcaReview)
        .where(
            RcaReview.rcaDraftId == draftRecord.rcaDraftId
        )
        .order_by(RcaReview.revisionNumber.desc())
        .limit(1)
    )

    if reviewRecord is None:
        raise RcaReviewNotFoundError(
            "No RCA review exists for this draft."
        )

    return reviewRecord

def listRcaReviews(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    pageSize: int,
    pageOffset: int,
) -> tuple[list[RcaReview], bool]:
    draftRecord = getRcaDraft(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
    )

    records = list(
        databaseSession.scalars(
            select(RcaReview)
            .where(
                RcaReview.rcaDraftId == draftRecord.rcaDraftId
            )
            .order_by(RcaReview.revisionNumber.desc())
            .offset(pageOffset)
            .limit(pageSize + 1)
        ).all()
    )

    return records[:pageSize], len(records) > pageSize


def getRcaReviewById(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
) -> RcaReview:
    draftRecord = getRcaDraft(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
    )

    reviewRecord = databaseSession.scalar(
        select(RcaReview).where(
            RcaReview.rcaReviewId == rcaReviewId,
            RcaReview.rcaDraftId == draftRecord.rcaDraftId,
        )
    )

    if reviewRecord is None:
        raise RcaReviewNotFoundError(
            "RCA review not found for this draft."
        )

    return reviewRecord
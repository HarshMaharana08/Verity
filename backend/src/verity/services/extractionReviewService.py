from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verity.models import (
    ExtractionReview,
    IncidentExtractionRecord,
)
from verity.schemas.extractionReviewSchemas import (
    AcceptedFieldDecision,
    CorrectedFieldDecision,
    ExtractionReviewRequest,
)
from verity.schemas.incidentExtractionSchemas import (
    IncidentExtraction,
)
from verity.services.extractionAssessmentService import (
    assessIncidentExtraction,
)
from verity.services.extractionQueryService import (
    IncidentExtractionNotFoundError,
    getIncidentExtraction,
)
from verity.services.incidentConsolidationService import (
    consolidatedExtractionSchemaVersion,
)


class ExtractionReviewConflictError(ValueError):
    pass


class InvalidExtractionReviewError(ValueError):
    pass


class UnsupportedReviewExtractionError(ValueError):
    pass


def createExtractionReview(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewRequest: ExtractionReviewRequest,
) -> ExtractionReview:
    try:
        getIncidentExtraction(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
        )

        # Serialize revision creation for this extraction.
        extractionRecord = databaseSession.scalar(
            select(IncidentExtractionRecord)
            .where(
                IncidentExtractionRecord.extractionId
                == extractionId
            )
            .with_for_update()
        )

        if extractionRecord is None:
            raise IncidentExtractionNotFoundError(
                "Extraction not found."
            )

        if (
            extractionRecord.schemaVersion
            != consolidatedExtractionSchemaVersion
        ):
            raise UnsupportedReviewExtractionError(
                "Review requires a supported consolidated extraction."
            )

        latestRevision = databaseSession.scalar(
            select(func.max(ExtractionReview.revisionNumber))
            .where(ExtractionReview.extractionId == extractionId)
        ) or 0

        if reviewRequest.expectedRevision != latestRevision:
            raise ExtractionReviewConflictError(
                "The review revision has changed. "
                f"Current revision is {latestRevision}."
            )

        assessment = assessIncidentExtraction(
            extractionId=extractionId,
            extractedData=extractionRecord.extractedData,
        )

        if (
            reviewRequest.expectedAssessmentVersion
            != assessment.assessmentVersion
        ):
            raise ExtractionReviewConflictError(
                "The assessment version has changed. "
                "Retrieve the assessment before saving."
            )

        candidateFields = extractionRecord.extractedData[
            "fieldCandidates"
        ]

        for fieldName, decision in (
            reviewRequest.fieldDecisions.items()
        ):
            if isinstance(decision, AcceptedFieldDecision):
                candidateCount = len(candidateFields[fieldName])

                if any(
                    index >= candidateCount
                    for index in decision.candidateIndexes
                ):
                    raise InvalidExtractionReviewError(
                        f"{fieldName}: a selected candidate "
                        "index does not exist."
                    )

        findingIds = {
            finding.findingId
            for finding in assessment.findings
        }

        unknownResponses = (
            set(reviewRequest.clarificationResponses)
            - findingIds
        )

        if unknownResponses:
            raise InvalidExtractionReviewError(
                "Unknown clarification findings: "
                + ", ".join(sorted(unknownResponses))
            )

        if reviewRequest.reviewStatus == "approved":
            if assessment.requiresDocumentReview:
                raise InvalidExtractionReviewError(
                    "Document classification requires review. "
                    "This extraction cannot be approved."
                )

            expectedFields = (
                set(IncidentExtraction.model_fields)
                - {"documentType"}
            )

            missingDecisions = (
                expectedFields
                - set(reviewRequest.fieldDecisions)
            )

            if missingDecisions:
                raise InvalidExtractionReviewError(
                    "Approval requires decisions for: "
                    + ", ".join(sorted(missingDecisions))
                )

            descriptionDecision = (
                reviewRequest.fieldDecisions[
                    "incidentDescription"
                ]
            )

            if not isinstance(
                descriptionDecision,
                (
                    AcceptedFieldDecision,
                    CorrectedFieldDecision,
                ),
            ):
                raise InvalidExtractionReviewError(
                    "Approval requires an accepted or corrected "
                    "incident description."
                )

            unansweredFindings = (
                findingIds
                - set(reviewRequest.clarificationResponses)
            )

            if unansweredFindings:
                raise InvalidExtractionReviewError(
                    "Approval requires explicit responses for: "
                    + ", ".join(sorted(unansweredFindings))
                )

        requestData = reviewRequest.model_dump(mode="json")

        reviewRecord = ExtractionReview(
            extractionId=extractionId,
            revisionNumber=latestRevision + 1,
            reviewStatus=reviewRequest.reviewStatus,
            reviewerLabel=reviewRequest.reviewerLabel,
            assessmentVersion=assessment.assessmentVersion,
            assessmentSnapshot=assessment.model_dump(mode="json"),
            fieldDecisions=requestData["fieldDecisions"],
            clarificationResponses=(
                requestData["clarificationResponses"]
            ),
            reviewNote=reviewRequest.reviewNote,
        )

        databaseSession.add(reviewRecord)
        databaseSession.flush()
        databaseSession.refresh(reviewRecord)
        databaseSession.commit()

    except Exception:
        # Release locks and discard changes on any failure.
        databaseSession.rollback()
        raise

    return reviewRecord

class ExtractionReviewNotFoundError(LookupError):
    pass


def getLatestExtractionReview(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
) -> ExtractionReview:
    getIncidentExtraction(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
    )

    reviewRecord = databaseSession.scalar(
        select(ExtractionReview)
        .where(
            ExtractionReview.extractionId == extractionId
        )
        .order_by(
            ExtractionReview.revisionNumber.desc()
        )
        .limit(1)
    )

    if reviewRecord is None:
        raise ExtractionReviewNotFoundError(
            "No review exists for this extraction."
        )

    return reviewRecord

def listExtractionReviews(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    pageSize: int,
    pageOffset: int,
) -> tuple[list[ExtractionReview], bool]:
    getIncidentExtraction(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
    )

    reviewRecords = list(
        databaseSession.scalars(
            select(ExtractionReview)
            .where(
                ExtractionReview.extractionId == extractionId
            )
            .order_by(
                ExtractionReview.revisionNumber.desc()
            )
            .offset(pageOffset)
            .limit(pageSize + 1)
        ).all()
    )

    return (
        reviewRecords[:pageSize],
        len(reviewRecords) > pageSize,
    )


def getExtractionReviewById(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
) -> ExtractionReview:
    getIncidentExtraction(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
    )

    reviewRecord = databaseSession.scalar(
        select(ExtractionReview)
        .where(
            ExtractionReview.reviewId == reviewId,
            ExtractionReview.extractionId == extractionId,
        )
    )

    if reviewRecord is None:
        raise ExtractionReviewNotFoundError(
            "Review not found for this extraction."
        )

    return reviewRecord
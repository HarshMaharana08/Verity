from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from verity.models import (
    InvestigationDocument,
    RcaEvidenceRequest,
    RcaEvidenceResponse,
    RcaEvidenceResponseDocument,
)
from verity.schemas.rcaEvidenceResponseSchemas import (
    RcaEvidenceResponseCreate,
    RcaEvidenceResponseView,
)
from verity.services.rcaEvidenceRequestService import (
    getRcaEvidenceRequest,
)


class RcaEvidenceResponseConflictError(ValueError):
    pass


class InvalidRcaEvidenceResponseError(ValueError):
    pass


def validateRcaEvidenceDocuments(
    databaseSession: Session,
    investigationId: UUID,
    documentIds: list[UUID],
) -> None:
    if not documentIds:
        return

    matchingIds = set(
        databaseSession.scalars(
            select(InvestigationDocument.documentId)
            .where(
                InvestigationDocument.documentId.in_(documentIds),
                InvestigationDocument.investigationId
                == investigationId,
            )
            .order_by(InvestigationDocument.documentId)
            .with_for_update(read=True)
        ).all()
    )

    if matchingIds != set(documentIds):
        raise InvalidRcaEvidenceResponseError(
            "One or more supporting documents were not found "
            "in this investigation."
        )


def createRcaEvidenceResponse(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
    responseInput: RcaEvidenceResponseCreate,
) -> RcaEvidenceResponseView:
    try:
        # Revalidate callers that constructed or modified a model directly.
        validatedInput = RcaEvidenceResponseCreate.model_validate(
            responseInput.model_dump(mode="json")
        )

        scopedRequest = getRcaEvidenceRequest(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            evidenceRequestId=evidenceRequestId,
        )

        # Serialize revision creation for this request.
        requestRecord = databaseSession.scalar(
            select(RcaEvidenceRequest)
            .where(
                RcaEvidenceRequest.evidenceRequestId
                == scopedRequest.evidenceRequestId
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        if requestRecord is None:
            raise ValueError(
                "The source evidence request is missing."
            )

        latestRevision = databaseSession.scalar(
            select(func.max(RcaEvidenceResponse.revisionNumber))
            .where(
                RcaEvidenceResponse.evidenceRequestId
                == requestRecord.evidenceRequestId
            )
        ) or 0

        if validatedInput.expectedRevision != latestRevision:
            raise RcaEvidenceResponseConflictError(
                "The evidence response revision has changed. "
                f"Current revision is {latestRevision}."
            )

        validateRcaEvidenceDocuments(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentIds=validatedInput.documentIds,
        )

        responseRecord = RcaEvidenceResponse(
            evidenceRequestId=requestRecord.evidenceRequestId,
            revisionNumber=latestRevision + 1,
            responseStatus=validatedInput.responseStatus,
            responseText=validatedInput.responseText,
            respondedByLabel=validatedInput.respondedByLabel,
        )

        databaseSession.add(responseRecord)
        databaseSession.flush()

        databaseSession.add_all([
            RcaEvidenceResponseDocument(
                evidenceResponseId=responseRecord.evidenceResponseId,
                documentId=supportingDocumentId,
            )
            for supportingDocumentId in validatedInput.documentIds
        ])

        databaseSession.flush()
        databaseSession.refresh(responseRecord)

        responseView = RcaEvidenceResponseView(
            evidenceResponseId=responseRecord.evidenceResponseId,
            evidenceRequestId=responseRecord.evidenceRequestId,
            revisionNumber=responseRecord.revisionNumber,
            responseStatus=responseRecord.responseStatus,
            responseText=responseRecord.responseText,
            respondedByLabel=responseRecord.respondedByLabel,
            documentIds=sorted(
                validatedInput.documentIds,
                key=str,
            ),
            createdAt=responseRecord.createdAt,
        )

        databaseSession.commit()

    except Exception:
        databaseSession.rollback()
        raise

    return responseView

class RcaEvidenceResponseNotFoundError(LookupError):
    pass


def listRcaEvidenceResponses(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
    pageSize: int,
    pageOffset: int,
) -> tuple[list[RcaEvidenceResponseView], bool]:
    requestRecord = getRcaEvidenceRequest(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
        rcaReviewId=rcaReviewId,
        evidenceRequestId=evidenceRequestId,
    )

    records = list(
        databaseSession.scalars(
            select(RcaEvidenceResponse)
            .where(
                RcaEvidenceResponse.evidenceRequestId
                == requestRecord.evidenceRequestId
            )
            .order_by(RcaEvidenceResponse.revisionNumber.desc())
            .offset(pageOffset)
            .limit(pageSize + 1)
        ).all()
    )

    selectedRecords = records[:pageSize]

    documentsByResponse = {
        record.evidenceResponseId: []
        for record in selectedRecords
    }

    if selectedRecords:
        links = databaseSession.execute(
            select(
                RcaEvidenceResponseDocument.evidenceResponseId,
                InvestigationDocument.documentId,
                InvestigationDocument.investigationId,
            )
            .join(
                InvestigationDocument,
                InvestigationDocument.documentId
                == RcaEvidenceResponseDocument.documentId,
            )
            .where(
                RcaEvidenceResponseDocument.evidenceResponseId.in_(
                    list(documentsByResponse)
                )
            )
            .order_by(
                RcaEvidenceResponseDocument.evidenceResponseId,
                InvestigationDocument.documentId,
            )
        ).all()

        for responseId, supportingDocumentId, sourceInvestigationId in links:
            if sourceInvestigationId != investigationId:
                raise ValueError(
                    "A saved evidence document belongs "
                    "to another investigation."
                )

            documentsByResponse[responseId].append(
                supportingDocumentId
            )

    views = [
        RcaEvidenceResponseView(
            evidenceResponseId=record.evidenceResponseId,
            evidenceRequestId=record.evidenceRequestId,
            revisionNumber=record.revisionNumber,
            responseStatus=record.responseStatus,
            responseText=record.responseText,
            respondedByLabel=record.respondedByLabel,
            documentIds=documentsByResponse[
                record.evidenceResponseId
            ],
            createdAt=record.createdAt,
        )
        for record in selectedRecords
    ]

    return views, len(records) > pageSize


def getLatestRcaEvidenceResponse(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
) -> RcaEvidenceResponseView:
    responses, _ = listRcaEvidenceResponses(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
        rcaJobId=rcaJobId,
        rcaReviewId=rcaReviewId,
        evidenceRequestId=evidenceRequestId,
        pageSize=1,
        pageOffset=0,
    )

    if not responses:
        raise RcaEvidenceResponseNotFoundError(
            "No response has been recorded for this evidence request."
        )

    return responses[0]
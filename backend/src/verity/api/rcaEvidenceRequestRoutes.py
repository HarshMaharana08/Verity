import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from verity.databaseSession import getDatabaseSession
from verity.schemas.rcaEvidenceRequestSchemas import (
    RcaEvidenceRequestCreate,
    RcaEvidenceRequestListResponse,
    RcaEvidenceRequestResponse,
)
from verity.services.extractionQueryService import (
    IncidentExtractionNotFoundError,
)
from verity.services.extractionReviewService import (
    ExtractionReviewNotFoundError,
)
from verity.services.rcaDraftQueryService import (
    RcaDraftNotReadyError,
)
from verity.services.rcaEvidenceRequestService import (
    InvalidRcaEvidenceRequestError,
    RcaEvidenceRequestNotFoundError,
    createRcaEvidenceRequest,
    getRcaEvidenceRequest,
    listRcaEvidenceRequests,
)
from verity.services.rcaJobService import RcaJobNotFoundError
from verity.services.rcaReviewService import (
    RcaReviewNotFoundError,
)
from verity.schemas.rcaEvidenceResponseSchemas import (
    RcaEvidenceResponseCreate,
    RcaEvidenceResponseListView,
    RcaEvidenceResponseView,
)
from verity.services.rcaEvidenceResponseService import (
    InvalidRcaEvidenceResponseError,
    RcaEvidenceResponseConflictError,
    RcaEvidenceResponseNotFoundError,
    createRcaEvidenceResponse,
    getLatestRcaEvidenceResponse,
    listRcaEvidenceResponses,
)


evidenceRequestLogger = logging.getLogger(__name__)

rcaEvidenceRequestRouter = APIRouter(
    prefix=(
        "/investigations/{investigationId}"
        "/documents/{documentId}"
        "/extractions/{extractionId}/reviews/{reviewId}"
        "/rcaJobs/{rcaJobId}/draft/reviews/{rcaReviewId}"
        "/evidenceRequests"
    ),
    tags=["RCA Evidence Requests"],
)


@contextmanager
def handleEvidenceRequestErrors() -> Iterator[None]:
    try:
        yield

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
        RcaReviewNotFoundError,
        RcaEvidenceRequestNotFoundError,
        RcaEvidenceResponseNotFoundError,
    ) as requestError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(requestError),
        ) from None

    except (
        RcaDraftNotReadyError,
        RcaEvidenceResponseConflictError,
    ) as requestError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(requestError),
        ) from None

    except (
        InvalidRcaEvidenceRequestError,
        InvalidRcaEvidenceResponseError,
    ) as requestError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(requestError),
        ) from None

    except (SQLAlchemyError, ValueError):
        evidenceRequestLogger.exception(
            "RCA evidence request operation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The evidence request operation could not be completed.",
        ) from None


@rcaEvidenceRequestRouter.post(
    "",
    response_model=RcaEvidenceRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an RCA evidence request",
)
def createRcaEvidenceRequestEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    requestInput: RcaEvidenceRequestCreate,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaEvidenceRequestResponse:
    with handleEvidenceRequestErrors():
        record = createRcaEvidenceRequest(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            requestInput=requestInput,
        )

        return RcaEvidenceRequestResponse.model_validate(record)


@rcaEvidenceRequestRouter.get(
    "",
    response_model=RcaEvidenceRequestListResponse,
    summary="List RCA evidence requests",
)
def listRcaEvidenceRequestsEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    pageOffset: Annotated[int, Query(ge=0)] = 0,
) -> RcaEvidenceRequestListResponse:
    with handleEvidenceRequestErrors():
        records, hasMore = listRcaEvidenceRequests(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            pageSize=pageSize,
            pageOffset=pageOffset,
        )

        return RcaEvidenceRequestListResponse(
            items=[
                RcaEvidenceRequestResponse.model_validate(record)
                for record in records
            ],
            pageSize=pageSize,
            pageOffset=pageOffset,
            hasMore=hasMore,
        )


@rcaEvidenceRequestRouter.get(
    "/{evidenceRequestId}",
    response_model=RcaEvidenceRequestResponse,
    summary="Get an RCA evidence request",
)
def getRcaEvidenceRequestEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaEvidenceRequestResponse:
    with handleEvidenceRequestErrors():
        record = getRcaEvidenceRequest(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            evidenceRequestId=evidenceRequestId,
        )

        return RcaEvidenceRequestResponse.model_validate(record)
    
@rcaEvidenceRequestRouter.post(
    "/{evidenceRequestId}/responses",
    response_model=RcaEvidenceResponseView,
    status_code=status.HTTP_201_CREATED,
    summary="Save an evidence response revision",
)
def createRcaEvidenceResponseEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
    responseInput: RcaEvidenceResponseCreate,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaEvidenceResponseView:
    with handleEvidenceRequestErrors():
        return createRcaEvidenceResponse(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            evidenceRequestId=evidenceRequestId,
            responseInput=responseInput,
        )


@rcaEvidenceRequestRouter.get(
    "/{evidenceRequestId}/responses/latest",
    response_model=RcaEvidenceResponseView,
    summary="Get the latest evidence response",
)
def getLatestRcaEvidenceResponseEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaEvidenceResponseView:
    with handleEvidenceRequestErrors():
        return getLatestRcaEvidenceResponse(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            evidenceRequestId=evidenceRequestId,
        )


@rcaEvidenceRequestRouter.get(
    "/{evidenceRequestId}/responses",
    response_model=RcaEvidenceResponseListView,
    summary="List evidence response revisions",
)
def listRcaEvidenceResponsesEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    rcaReviewId: UUID,
    evidenceRequestId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    pageOffset: Annotated[int, Query(ge=0)] = 0,
) -> RcaEvidenceResponseListView:
    with handleEvidenceRequestErrors():
        items, hasMore = listRcaEvidenceResponses(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
            evidenceRequestId=evidenceRequestId,
            pageSize=pageSize,
            pageOffset=pageOffset,
        )

        return RcaEvidenceResponseListView(
            items=items,
            pageSize=pageSize,
            pageOffset=pageOffset,
            hasMore=hasMore,
        )
import logging
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
from verity.schemas.extractionReviewSchemas import (
    ExtractionReviewRequest,
    ExtractionReviewResponse,
    ExtractionReviewListResponse,
    ExtractionReviewSummary,
)
from verity.services.extractionQueryService import (
    IncidentExtractionNotFoundError,
)
from verity.services.extractionReviewService import (
    ExtractionReviewConflictError,
    ExtractionReviewNotFoundError,
    InvalidExtractionReviewError,
    UnsupportedReviewExtractionError,
    createExtractionReview,
    getLatestExtractionReview,
    getExtractionReviewById,
    listExtractionReviews,
)


reviewLogger = logging.getLogger(__name__)

extractionReviewRouter = APIRouter(
    prefix="/investigations",
    tags=["Extraction Reviews"],
)


@extractionReviewRouter.post(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews",
    response_model=ExtractionReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save an extraction review revision",
    responses={
        404: {"description": "Extraction not found"},
        409: {"description": "Version conflict or unsupported format"},
        422: {"description": "Invalid review decisions"},
        500: {"description": "Review could not be saved"},
    },
)
def createExtractionReviewEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewRequest: ExtractionReviewRequest,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ExtractionReviewResponse:
    try:
        reviewRecord = createExtractionReview(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewRequest=reviewRequest,
        )

        return ExtractionReviewResponse.model_validate(
            reviewRecord
        )

    except IncidentExtractionNotFoundError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except (
        ExtractionReviewConflictError,
        UnsupportedReviewExtractionError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(reviewError),
        ) from None

    except InvalidExtractionReviewError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        reviewLogger.exception(
            "Extraction review creation failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The review could not be saved.",
        ) from None


@extractionReviewRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/latest",
    response_model=ExtractionReviewResponse,
    summary="Get the latest extraction review",
    responses={
        404: {"description": "Extraction or review not found"},
        500: {"description": "Review could not be retrieved"},
    },
)
def getLatestExtractionReviewEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ExtractionReviewResponse:
    try:
        reviewRecord = getLatestExtractionReview(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
        )

        return ExtractionReviewResponse.model_validate(
            reviewRecord
        )

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        reviewLogger.exception(
            "Extraction review retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The review could not be retrieved.",
        ) from None
        
@extractionReviewRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews",
    response_model=ExtractionReviewListResponse,
    summary="List extraction review revisions",
    responses={
        404: {"description": "Extraction not found"},
        500: {"description": "Review history could not be retrieved"},
    },
)
def listExtractionReviewsEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
    pageSize: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
    pageOffset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> ExtractionReviewListResponse:
    try:
        records, hasMore = listExtractionReviews(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            pageSize=pageSize,
            pageOffset=pageOffset,
        )

        return ExtractionReviewListResponse(
            items=[
                ExtractionReviewSummary.model_validate(record)
                for record in records
            ],
            pageSize=pageSize,
            pageOffset=pageOffset,
            hasMore=hasMore,
        )

    except IncidentExtractionNotFoundError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        reviewLogger.exception(
            "Extraction review history retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The review history could not be retrieved.",
        ) from None


@extractionReviewRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}",
    response_model=ExtractionReviewResponse,
    summary="Get an extraction review revision",
    responses={
        404: {"description": "Extraction or review not found"},
        500: {"description": "Review could not be retrieved"},
    },
)
def getExtractionReviewByIdEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ExtractionReviewResponse:
    try:
        reviewRecord = getExtractionReviewById(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
        )

        return ExtractionReviewResponse.model_validate(
            reviewRecord
        )

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        reviewLogger.exception(
            "Extraction review revision retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The review could not be retrieved.",
        ) from None
import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from verity.databaseSession import getDatabaseSession
from verity.schemas.rcaJobSchemas import RcaJobResponse
from verity.services.extractionQueryService import (
    IncidentExtractionNotFoundError,
)
from verity.services.extractionReviewService import (
    ExtractionReviewNotFoundError,
)
from verity.services.rcaJobService import (
    ActiveRcaJobError,
    RcaJobNotFoundError,
    RcaReviewNotEligibleError,
    getRcaJob,
    queueRcaJob,
)
from verity.schemas.rcaDraftSchemas import RcaDraftResponse
from verity.services.rcaDraftQueryService import (
    RcaDraftNotReadyError,
    getRcaDraft,
)


rcaJobLogger = logging.getLogger(__name__)

rcaJobRouter = APIRouter(
    prefix="/investigations",
    tags=["RCA Jobs"],
)


@rcaJobRouter.post(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}/rcaJobs",
    response_model=RcaJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an RCA draft job",
    responses={
        404: {"description": "Extraction or review not found"},
        409: {"description": "Review ineligible or active job exists"},
        500: {"description": "RCA job could not be queued"},
    },
)
def queueRcaJobEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    request: Request,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaJobResponse:
    try:
        jobRecord = queueRcaJob(
            databaseSession=databaseSession,
            applicationSettings=request.app.state.applicationSettings,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
        )

        return RcaJobResponse.model_validate(jobRecord)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
    ) as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except (
        RcaReviewNotEligibleError,
        ActiveRcaJobError,
    ) as jobError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(jobError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA job creation failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA job could not be queued.",
        ) from None


@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}",
    response_model=RcaJobResponse,
    summary="Get an RCA job",
    responses={
        404: {"description": "Extraction, review, or RCA job not found"},
        500: {"description": "RCA job could not be retrieved"},
    },
)
def getRcaJobEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaJobResponse:
    try:
        jobRecord = getRcaJob(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        return RcaJobResponse.model_validate(jobRecord)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
    ) as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA job retrieval failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA job could not be retrieved.",
        ) from None
        
@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft",
    response_model=RcaDraftResponse,
    summary="Get a saved RCA draft",
    responses={
        404: {"description": "Extraction, review, or RCA job not found"},
        409: {"description": "Job has no successful draft result"},
        500: {"description": "RCA draft could not be retrieved"},
    },
)
def getRcaDraftEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaDraftResponse:
    try:
        draftRecord = getRcaDraft(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        return RcaDraftResponse.model_validate(draftRecord)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
    ) as draftError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(draftError),
        ) from None

    except RcaDraftNotReadyError as draftError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(draftError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA draft retrieval failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA draft could not be retrieved.",
        ) from None
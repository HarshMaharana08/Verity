import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
    Query,
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
from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.schemas.rcaEvidenceAssessmentSchemas import (
    RcaEvidenceAssessment,
)
from verity.services.rcaEvidenceAssessmentService import (
    assessRcaEvidence,
)
from verity.schemas.rcaReviewSchemas import (
    RcaReviewRequest,
    RcaReviewResponse,
    RcaReviewListResponse,
    RcaReviewSummary,
)
from verity.services.rcaReviewService import (
    InvalidRcaReviewError,
    RcaReviewConflictError,
    RcaReviewNotFoundError,
    createRcaReview,
    getLatestRcaReview,
    getRcaReviewById,
    listRcaReviews,
)
from verity.schemas.effectiveRcaSchemas import EffectiveRcaView
from verity.services.effectiveRcaService import (
    buildEffectiveRcaView,
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
        
@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft/evidenceAssessment",
    response_model=RcaEvidenceAssessment,
    summary="Assess evidence sources in an RCA draft",
    responses={
        404: {"description": "Extraction, review, or RCA job not found"},
        409: {"description": "Job has no successful draft result"},
        500: {"description": "Evidence assessment could not be generated"},
    },
)
def getRcaEvidenceAssessmentEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaEvidenceAssessment:
    try:
        draftRecord = getRcaDraft(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        validatedDraft = ValidatedRcaDraft.model_validate(
            draftRecord.draftData
        )

        return assessRcaEvidence(validatedDraft)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
    ) as assessmentError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(assessmentError),
        ) from None

    except RcaDraftNotReadyError as assessmentError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(assessmentError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception(
            "RCA evidence assessment failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The evidence assessment could not be generated.",
        ) from None
        
@rcaJobRouter.post(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft/reviews",
    response_model=RcaReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save an RCA review revision",
    responses={
        404: {"description": "Source resource not found"},
        409: {"description": "Version conflict or draft unavailable"},
        422: {"description": "Invalid RCA review decisions"},
        500: {"description": "RCA review could not be saved"},
    },
)
def createRcaReviewEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    reviewRequest: RcaReviewRequest,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaReviewResponse:
    try:
        reviewRecord = createRcaReview(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            reviewRequest=reviewRequest,
        )

        return RcaReviewResponse.model_validate(reviewRecord)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except (
        RcaReviewConflictError,
        RcaDraftNotReadyError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(reviewError),
        ) from None

    except InvalidRcaReviewError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA review creation failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA review could not be saved.",
        ) from None


@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft/reviews/latest",
    response_model=RcaReviewResponse,
    summary="Get the latest RCA review",
    responses={
        404: {"description": "Source resource or RCA review not found"},
        409: {"description": "Draft unavailable"},
        500: {"description": "RCA review could not be retrieved"},
    },
)
def getLatestRcaReviewEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> RcaReviewResponse:
    try:
        reviewRecord = getLatestRcaReview(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        return RcaReviewResponse.model_validate(reviewRecord)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
        RcaReviewNotFoundError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except RcaDraftNotReadyError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA review retrieval failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA review could not be retrieved.",
        ) from None
        
@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft/reviews",
    response_model=RcaReviewListResponse,
    summary="List RCA review revisions",
)
def listRcaReviewsEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
    pageSize: Annotated[int, Query(ge=1, le=100)] = 20,
    pageOffset: Annotated[int, Query(ge=0)] = 0,
) -> RcaReviewListResponse:
    try:
        records, hasMore = listRcaReviews(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            pageSize=pageSize,
            pageOffset=pageOffset,
        )

        return RcaReviewListResponse(
            items=[
                RcaReviewSummary.model_validate(record)
                for record in records
            ],
            pageSize=pageSize,
            pageOffset=pageOffset,
            hasMore=hasMore,
        )

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except RcaDraftNotReadyError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA review history retrieval failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA review history could not be retrieved.",
        ) from None


@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft/reviews/{rcaReviewId}",
    response_model=RcaReviewResponse,
    summary="Get an RCA review revision",
)
def getRcaReviewByIdEndpoint(
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
) -> RcaReviewResponse:
    try:
        reviewRecord = getRcaReviewById(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
            rcaReviewId=rcaReviewId,
        )

        return RcaReviewResponse.model_validate(reviewRecord)

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
        RcaReviewNotFoundError,
    ) as reviewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(reviewError),
        ) from None

    except RcaDraftNotReadyError as reviewError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(reviewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception("RCA review revision retrieval failed.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The RCA review could not be retrieved.",
        ) from None
        
@rcaJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/reviews/{reviewId}"
    "/rcaJobs/{rcaJobId}/draft/effectiveReview",
    response_model=EffectiveRcaView,
    summary="Get the latest effective reviewed RCA",
    responses={
        404: {"description": "Source resource or RCA review not found"},
        409: {"description": "Draft unavailable"},
        500: {"description": "Effective RCA review could not be generated"},
    },
)
def getLatestEffectiveRcaReviewEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> EffectiveRcaView:
    try:
        draftRecord = getRcaDraft(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        reviewRecord = getLatestRcaReview(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
            rcaJobId=rcaJobId,
        )

        return buildEffectiveRcaView(
            draftRecord=draftRecord,
            reviewRecord=reviewRecord,
        )

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
        RcaJobNotFoundError,
        RcaReviewNotFoundError,
    ) as viewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(viewError),
        ) from None

    except RcaDraftNotReadyError as viewError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(viewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        rcaJobLogger.exception(
            "Effective RCA review retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The effective RCA review could not be generated.",
        ) from None
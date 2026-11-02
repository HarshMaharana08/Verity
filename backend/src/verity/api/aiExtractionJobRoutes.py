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
from verity.schemas.aiExtractionJobSchemas import (
    AiExtractionJobResponse,
)
from verity.services.aiExtractionJobService import (
    ActiveAiExtractionJobError,
    AiExtractionJobNotFoundError,
    AiSourceJobNotReadyError,
    getAiExtractionJob,
    queueAiExtractionJob,
)
from verity.services.processingJobService import (
    ProcessingJobNotFoundError,
)


aiJobLogger = logging.getLogger(__name__)

aiExtractionJobRouter = APIRouter(
    prefix="/investigations",
    tags=["AI Extraction Jobs"],
)


@aiExtractionJobRouter.post(
    "/{investigationId}/documents/{documentId}"
    "/processingJobs/{sourceProcessingJobId}/aiExtractionJobs",
    response_model=AiExtractionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue AI incident extraction",
    responses={
        404: {"description": "Source processing job not found"},
        409: {
            "description": "Source not ready or AI job already active",
        },
        500: {"description": "AI job could not be queued"},
    },
)
def queueAiExtractionJobEndpoint(
    investigationId: UUID,
    documentId: UUID,
    sourceProcessingJobId: UUID,
    request: Request,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> AiExtractionJobResponse:
    try:
        jobRecord = queueAiExtractionJob(
            databaseSession=databaseSession,
            applicationSettings=(
                request.app.state.applicationSettings
            ),
            investigationId=investigationId,
            documentId=documentId,
            sourceProcessingJobId=sourceProcessingJobId,
        )

    except ProcessingJobNotFoundError as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except (
        AiSourceJobNotReadyError,
        ActiveAiExtractionJobError,
    ) as jobError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(jobError),
        ) from None

    except SQLAlchemyError:
        aiJobLogger.exception(
            "AI-extraction job could not be queued."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI-extraction job could not be queued.",
        ) from None

    return AiExtractionJobResponse.model_validate(jobRecord)

@aiExtractionJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/processingJobs/{sourceProcessingJobId}"
    "/aiExtractionJobs/{aiJobId}",
    response_model=AiExtractionJobResponse,
    summary="Get AI-extraction job status",
    responses={
        404: {"description": "AI-extraction job not found"},
        500: {"description": "AI job could not be retrieved"},
    },
)
def getAiExtractionJobEndpoint(
    investigationId: UUID,
    documentId: UUID,
    sourceProcessingJobId: UUID,
    aiJobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> AiExtractionJobResponse:
    try:
        jobRecord = getAiExtractionJob(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            sourceProcessingJobId=sourceProcessingJobId,
            aiJobId=aiJobId,
        )

    except AiExtractionJobNotFoundError as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except SQLAlchemyError:
        aiJobLogger.exception(
            "AI-extraction job retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI-extraction job could not be retrieved.",
        ) from None

    return AiExtractionJobResponse.model_validate(jobRecord)
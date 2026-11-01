import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from verity.databaseSession import getDatabaseSession
from verity.schemas.processingJobSchemas import (
    ProcessingJobResponse,
    ProcessingJobTextResponse,
)
from verity.services.documentService import (
    DocumentNotFoundError,
)
from verity.services.processingJobService import (
    ActiveProcessingJobError,
    ProcessingJobNotFoundError,
    getDocumentProcessingJob,
    queueDocumentProcessingJob,
)


processingJobLogger = logging.getLogger(__name__)

processingJobRouter = APIRouter(
    prefix="/investigations",
    tags=["Document Processing"],
)


@processingJobRouter.post(
    "/{investigationId}/documents/{documentId}/processingJobs",
    response_model=ProcessingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue document processing",
    responses={
        404: {"description": "Document not found"},
        409: {"description": "Document already has an active job"},
        500: {"description": "Processing job could not be queued"},
    },
)
def queueDocumentProcessingJobEndpoint(
    investigationId: UUID,
    documentId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ProcessingJobResponse:
    try:
        jobRecord = queueDocumentProcessingJob(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
        )

    except DocumentNotFoundError as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except ActiveProcessingJobError as jobError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(jobError),
        ) from None

    except SQLAlchemyError:
        processingJobLogger.exception(
            "Document processing job could not be queued."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The processing job could not be queued.",
        ) from None

    return ProcessingJobResponse.model_validate(jobRecord)


@processingJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/processingJobs/{jobId}",
    response_model=ProcessingJobResponse,
    summary="Get document processing job status",
    responses={
        404: {"description": "Processing job not found"},
        500: {"description": "Processing job could not be retrieved"},
    },
)
def getDocumentProcessingJobEndpoint(
    investigationId: UUID,
    documentId: UUID,
    jobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ProcessingJobResponse:
    try:
        jobRecord = getDocumentProcessingJob(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            jobId=jobId,
        )

    except ProcessingJobNotFoundError as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except SQLAlchemyError:
        processingJobLogger.exception(
            "Document processing job could not be retrieved."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The processing job could not be retrieved.",
        ) from None

    return ProcessingJobResponse.model_validate(jobRecord)


@processingJobRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/processingJobs/{jobId}/text",
    response_model=ProcessingJobTextResponse,
    summary="Get extracted document text",
    responses={
        404: {"description": "Processing job not found"},
        409: {"description": "Processing job has not succeeded"},
        500: {"description": "Extracted text could not be retrieved"},
    },
)
def getDocumentProcessingTextEndpoint(
    investigationId: UUID,
    documentId: UUID,
    jobId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ProcessingJobTextResponse:
    try:
        jobRecord = getDocumentProcessingJob(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            jobId=jobId,
        )

    except ProcessingJobNotFoundError as jobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(jobError),
        ) from None

    except SQLAlchemyError:
        processingJobLogger.exception(
            "Extracted document text could not be retrieved."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The extracted text could not be retrieved.",
        ) from None

    if jobRecord.status != "succeeded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Extracted text is available only "
                "for succeeded jobs."
            ),
        )

    extractedText = jobRecord.extractedText

    if extractedText is None or not extractedText.strip():
        processingJobLogger.error(
            "Succeeded job %s has no extracted text.",
            jobRecord.jobId,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The extracted text could not be retrieved.",
        )

    return ProcessingJobTextResponse(
        jobId=jobRecord.jobId,
        documentId=jobRecord.documentId,
        characterCount=len(extractedText),
        extractedText=extractedText,
    )
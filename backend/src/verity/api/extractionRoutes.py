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
from verity.schemas.extractionSchemas import (
    IncidentExtractionResponse,
)
from verity.services.extractionQueryService import (
    IncidentExtractionNotFoundError,
    getIncidentExtraction,
)


extractionLogger = logging.getLogger(__name__)

extractionRouter = APIRouter(
    prefix="/investigations",
    tags=["Incident Extractions"],
)


@extractionRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}",
    response_model=IncidentExtractionResponse,
    summary="Get a saved incident extraction",
    responses={
        404: {"description": "Extraction not found"},
        500: {"description": "Extraction could not be retrieved"},
    },
)
def getIncidentExtractionEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> IncidentExtractionResponse:
    try:
        extractionRecord = getIncidentExtraction(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
        )

    except IncidentExtractionNotFoundError as extractionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(extractionError),
        ) from None

    except SQLAlchemyError:
        extractionLogger.exception(
            "Saved incident extraction retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The extraction could not be retrieved.",
        ) from None

    return IncidentExtractionResponse.model_validate(
        extractionRecord
    )
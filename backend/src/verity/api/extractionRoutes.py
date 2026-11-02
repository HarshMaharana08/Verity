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
from verity.schemas.extractionAssessmentSchemas import (
    ExtractionAssessment,
)
from verity.services.extractionAssessmentService import (
    assessIncidentExtraction,
)
from verity.services.incidentConsolidationService import (
    consolidatedExtractionSchemaVersion,
)
from verity.schemas.effectiveFactSchemas import (
    EffectiveFactView,
)
from verity.services.effectiveFactService import (
    buildEffectiveFactView,
)
from verity.services.extractionReviewService import (
    ExtractionReviewNotFoundError,
    getLatestExtractionReview,
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
    
@extractionRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/assessment",
    response_model=ExtractionAssessment,
    summary="Get extraction missing-information assessment",
    responses={
        404: {"description": "Extraction not found"},
        409: {"description": "Extraction format is unsupported"},
        500: {"description": "Assessment could not be generated"},
    },
)
def getExtractionAssessmentEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> ExtractionAssessment:
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
            "Assessment source retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The assessment could not be generated.",
        ) from None

    if (
        extractionRecord.schemaVersion
        != consolidatedExtractionSchemaVersion
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Assessment requires a supported "
                "consolidated extraction result."
            ),
        )

    try:
        return assessIncidentExtraction(
            extractionId=extractionRecord.extractionId,
            extractedData=extractionRecord.extractedData,
        )

    except ValueError:
        extractionLogger.error(
            "Stored extraction %s has invalid assessment data.",
            extractionRecord.extractionId,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The assessment could not be generated.",
        ) from None
        
@extractionRouter.get(
    "/{investigationId}/documents/{documentId}"
    "/extractions/{extractionId}/effectiveFacts",
    response_model=EffectiveFactView,
    summary="Get latest effective incident facts",
    responses={
        404: {"description": "Extraction or review not found"},
        409: {"description": "Extraction format is unsupported"},
        500: {"description": "Effective facts could not be generated"},
    },
)
def getLatestEffectiveFactsEndpoint(
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> EffectiveFactView:
    try:
        extractionRecord = getIncidentExtraction(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
        )

        if (
            extractionRecord.schemaVersion
            != consolidatedExtractionSchemaVersion
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Effective facts require a supported "
                    "consolidated extraction."
                ),
            )

        reviewRecord = getLatestExtractionReview(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
        )

        return buildEffectiveFactView(
            extractionRecord=extractionRecord,
            reviewRecord=reviewRecord,
        )

    except (
        IncidentExtractionNotFoundError,
        ExtractionReviewNotFoundError,
    ) as viewError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(viewError),
        ) from None

    except (SQLAlchemyError, ValueError):
        extractionLogger.exception(
            "Effective fact retrieval failed."
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The effective facts could not be generated.",
        ) from None
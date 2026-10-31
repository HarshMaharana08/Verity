from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from verity.databaseSession import getDatabaseSession
from verity.schemas.investigationSchemas import (
    CreateInvestigationRequest,
    InvestigationResponse,
)
from verity.services.investigationService import (
    createInvestigation,
    getInvestigationById,
)


investigationRouter = APIRouter(
    prefix="/investigations",
    tags=["Investigations"],
)


@investigationRouter.post(
    "",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft investigation",
)
def createInvestigationEndpoint(
    investigationRequest: CreateInvestigationRequest,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> InvestigationResponse:
    investigationRecord = createInvestigation(
        databaseSession=databaseSession,
        investigationRequest=investigationRequest,
    )

    return InvestigationResponse.model_validate(
        investigationRecord,
    )


@investigationRouter.get(
    "/{investigationId}",
    response_model=InvestigationResponse,
    summary="Retrieve an investigation by ID",
    responses={
        404: {"description": "Investigation not found"},
    },
)
def getInvestigationByIdEndpoint(
    investigationId: UUID,
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
) -> InvestigationResponse:
    investigationRecord = getInvestigationById(
        databaseSession=databaseSession,
        investigationId=investigationId,
    )

    if investigationRecord is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    return InvestigationResponse.model_validate(
        investigationRecord,
    )
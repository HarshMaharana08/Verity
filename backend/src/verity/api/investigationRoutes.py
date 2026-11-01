from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from verity.databaseSession import getDatabaseSession
from verity.schemas.investigationSchemas import (
    CreateInvestigationRequest,
    InvestigationListItemResponse,
    InvestigationListResponse,
    InvestigationResponse,
)
from verity.services.investigationService import (
    createInvestigation,
    getInvestigationById,
    listInvestigations,
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
    "",
    response_model=InvestigationListResponse,
    summary="List investigations with pagination",
)
def listInvestigationsEndpoint(
    databaseSession: Annotated[
        Session,
        Depends(getDatabaseSession),
    ],
    pageSize: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Number of investigations to return",
        ),
    ] = 20,
    pageOffset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of investigations to skip",
        ),
    ] = 0,
) -> InvestigationListResponse:
    investigationRecords, hasMore = listInvestigations(
        databaseSession=databaseSession,
        pageSize=pageSize,
        pageOffset=pageOffset,
    )

    investigationItems = [
        InvestigationListItemResponse.model_validate(
            investigationRecord,
        )
        for investigationRecord in investigationRecords
    ]

    return InvestigationListResponse(
        items=investigationItems,
        pageSize=pageSize,
        pageOffset=pageOffset,
        hasMore=hasMore,
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
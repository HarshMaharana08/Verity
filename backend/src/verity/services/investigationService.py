from uuid import UUID

from sqlalchemy.orm import Session

from verity.models.investigation import Investigation
from verity.schemas.investigationSchemas import (
    CreateInvestigationRequest,
)

from sqlalchemy import select


def createInvestigation(
    databaseSession: Session,
    investigationRequest: CreateInvestigationRequest,
) -> Investigation:
    investigationRecord = Investigation(
        title=investigationRequest.title,
        description=investigationRequest.description,
        status="draft",
    )

    with databaseSession.begin():
        databaseSession.add(investigationRecord)
        databaseSession.flush()
        databaseSession.refresh(investigationRecord)

    return investigationRecord


def getInvestigationById(
    databaseSession: Session,
    investigationId: UUID,
) -> Investigation | None:
    return databaseSession.get(
        Investigation,
        investigationId,
    )
    

def listInvestigations(
    databaseSession: Session,
    pageSize: int,
    pageOffset: int,
) -> tuple[list[Investigation], bool]:
    investigationQuery = (
        select(Investigation)
        .order_by(
            Investigation.createdAt.desc(),
            Investigation.investigationId.desc(),
        )
        .offset(pageOffset)
        .limit(pageSize + 1)
    )

    investigationRecords = list(
        databaseSession.scalars(investigationQuery).all()
    )

    hasMore = len(investigationRecords) > pageSize

    return investigationRecords[:pageSize], hasMore
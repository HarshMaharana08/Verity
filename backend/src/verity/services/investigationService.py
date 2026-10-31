from uuid import UUID

from sqlalchemy.orm import Session

from verity.models.investigation import Investigation
from verity.schemas.investigationSchemas import (
    CreateInvestigationRequest,
)


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
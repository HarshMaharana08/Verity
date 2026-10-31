from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError


healthRouter = APIRouter(
    prefix="/health",
    tags=["Health"],
)


class LivenessResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    database: str


@healthRouter.get(
    "/live",
    response_model=LivenessResponse,
    summary="Check whether the API is responding",
)
def getLivenessStatus() -> LivenessResponse:
    return LivenessResponse(
        status="ok",
        service="verity-backend",
    )


@healthRouter.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check whether the database is reachable",
    responses={
        503: {"description": "Database is unavailable"},
    },
)
def getReadinessStatus(request: Request) -> ReadinessResponse:
    databaseEngine: Engine = request.app.state.databaseEngine

    try:
        with databaseEngine.connect() as databaseConnection:
            databaseConnection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from None

    return ReadinessResponse(
        status="ready",
        database="reachable",
    )
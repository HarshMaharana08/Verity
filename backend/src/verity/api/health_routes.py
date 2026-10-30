from fastapi import APIRouter
from pydantic import BaseModel


healthRouter = APIRouter(
    prefix="/health",
    tags=["Health"],
)


class LivenessResponse(BaseModel):
    status: str
    service: str


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
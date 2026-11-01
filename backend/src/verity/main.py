from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from verity.api.health_routes import healthRouter
from verity.config import ApplicationSettings
from verity.database import createDatabaseEngine

from verity.api.investigationRoutes import investigationRouter

from verity.api.documentRoutes import documentRouter
from verity.api.processingJobRoutes import processingJobRouter

from verity.api.extractionRoutes import extractionRouter

@asynccontextmanager
async def manageApplicationLifespan(
    application: FastAPI,
) -> AsyncIterator[None]:
    applicationSettings = ApplicationSettings()
    databaseEngine = createDatabaseEngine(applicationSettings)

    application.state.databaseEngine = databaseEngine
    
    application.state.documentStorageRoot = (
        applicationSettings.documentStorageRoot.resolve()
    )
    application.state.maxDocumentSizeBytes = (
        applicationSettings.maxDocumentSizeBytes
    )

    try:
        yield
    finally:
        await run_in_threadpool(databaseEngine.dispose)


def createApplication() -> FastAPI:
    application = FastAPI(
        title="Verity — Pharma Quality Investigator",
        description=(
            "AI-assisted deviation investigation, "
            "root cause analysis, and CAPA management."
        ),
        version="0.1.0",
        lifespan=manageApplicationLifespan,
    )

    application.include_router(
        healthRouter,
        prefix="/api/v1",
    )
    
    application.include_router(
        investigationRouter,
        prefix="/api/v1",
    )
    
    application.include_router(
        documentRouter,
        prefix="/api/v1",
    )
    
    application.include_router(
        processingJobRouter,
        prefix="/api/v1",
    )
    
    application.include_router(
        extractionRouter,
        prefix="/api/v1",
    )

    return application


application = createApplication()
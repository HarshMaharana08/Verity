from fastapi import FastAPI

from verity.api.health_routes import healthRouter


def createApplication() -> FastAPI:
    application = FastAPI(
        title="Verity — Pharma Quality Investigator",
        description=(
            "AI-assisted deviation investigation, "
            "root cause analysis, and CAPA management."
        ),
        version="0.1.0",
    )

    application.include_router(
        healthRouter,
        prefix="/api/v1",
    )

    return application


application = createApplication()
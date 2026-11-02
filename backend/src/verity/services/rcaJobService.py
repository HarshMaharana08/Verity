import json
from hashlib import sha256
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from verity.config import ApplicationSettings
from verity.models import RcaJob
from verity.services.effectiveFactService import (
    buildEffectiveFactView,
)
from verity.services.extractionQueryService import (
    getIncidentExtraction,
)
from verity.services.extractionReviewService import (
    getExtractionReviewById,
)


rcaWorkflowVersion = "rcaWorkflow.v1"
rcaPromptVersion = "rcaPrompt.v2"
rcaSchemaVersion = "rcaDraft.v1"


class RcaReviewNotEligibleError(ValueError):
    pass


class ActiveRcaJobError(ValueError):
    pass


class RcaJobNotFoundError(LookupError):
    pass


def calculateRcaInputSha256(
    inputSnapshot: dict[str, object],
) -> str:
    canonicalJson = json.dumps(
        inputSnapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

    return sha256(
        canonicalJson.encode("utf-8")
    ).hexdigest()


def queueRcaJob(
    databaseSession: Session,
    applicationSettings: ApplicationSettings,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
) -> RcaJob:
    try:
        extractionRecord = getIncidentExtraction(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
        )

        reviewRecord = getExtractionReviewById(
            databaseSession=databaseSession,
            investigationId=investigationId,
            documentId=documentId,
            extractionId=extractionId,
            reviewId=reviewId,
        )

        if reviewRecord.reviewStatus != "approved":
            raise RcaReviewNotEligibleError(
                "RCA drafting requires an approved review."
            )

        effectiveFacts = buildEffectiveFactView(
            extractionRecord=extractionRecord,
            reviewRecord=reviewRecord,
        )

        if not effectiveFacts.canDraftHypotheses:
            raise RcaReviewNotEligibleError(
                "This review is not eligible for RCA drafting. "
                "Check the assessment version and review completeness."
            )

        inputSnapshot = effectiveFacts.model_dump(
            mode="json",
        )

        jobRecord = RcaJob(
            sourceReviewId=reviewRecord.reviewId,
            inputSnapshot=inputSnapshot,
            inputSha256=calculateRcaInputSha256(
                inputSnapshot
            ),
            status="queued",
            attemptCount=0,
            providerName="groq",
            modelName=applicationSettings.groqModel,
            workflowVersion=rcaWorkflowVersion,
            promptVersion=rcaPromptVersion,
            schemaVersion=rcaSchemaVersion,
        )

        databaseSession.add(jobRecord)
        databaseSession.flush()
        databaseSession.refresh(jobRecord)
        databaseSession.commit()

    except IntegrityError as databaseError:
        databaseSession.rollback()

        originalError = databaseError.orig

        if (
            isinstance(originalError, UniqueViolation)
            and originalError.diag.constraint_name
            == "uniqueActiveRcaJobBySourceReview"
        ):
            raise ActiveRcaJobError(
                "This review already has a queued "
                "or processing RCA job."
            ) from None

        raise

    except Exception:
        databaseSession.rollback()
        raise

    return jobRecord


def getRcaJob(
    databaseSession: Session,
    investigationId: UUID,
    documentId: UUID,
    extractionId: UUID,
    reviewId: UUID,
    rcaJobId: UUID,
) -> RcaJob:
    getExtractionReviewById(
        databaseSession=databaseSession,
        investigationId=investigationId,
        documentId=documentId,
        extractionId=extractionId,
        reviewId=reviewId,
    )

    jobRecord = databaseSession.scalar(
        select(RcaJob).where(
            RcaJob.rcaJobId == rcaJobId,
            RcaJob.sourceReviewId == reviewId,
        )
    )

    if jobRecord is None:
        raise RcaJobNotFoundError(
            "RCA job not found for this review."
        )

    return jobRecord
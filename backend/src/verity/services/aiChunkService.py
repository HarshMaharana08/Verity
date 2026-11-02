from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from verity.models import AiExtractionChunk, AiExtractionJob
from verity.schemas.incidentExtractionSchemas import (
    IncidentExtraction,
)
from verity.services.aiExtractionService import (
    extractionSystemPrompt,
)
from verity.services.groqRequestBudgetService import (
    estimateGroqRequestTokens,
    requestTokenBudget,
)
from verity.services.textChunkService import (
    splitSourceTextForBudget,
)


class AiJobClaimLostError(RuntimeError):
    pass


class AiChunkPlanMismatchError(ValueError):
    pass


def lockOwnedAiJob(
    databaseSession: Session,
    aiJobId: UUID,
    leaseToken: UUID,
) -> AiExtractionJob:
    jobRecord = databaseSession.scalar(
        select(AiExtractionJob)
        .where(AiExtractionJob.aiJobId == aiJobId)
        .with_for_update()
    )

    databaseTime = databaseSession.scalar(
        select(func.clock_timestamp())
    )

    if (
        jobRecord is None
        or jobRecord.status != "processing"
        or jobRecord.leaseToken != leaseToken
        or jobRecord.leaseExpiresAt is None
        or jobRecord.leaseExpiresAt <= databaseTime
    ):
        raise AiJobClaimLostError(
            "The AI job claim expired or ownership changed."
        )

    return jobRecord


def renewAiJobLease(
    databaseEngine: Engine,
    aiJobId: UUID,
    leaseToken: UUID,
    leaseDurationSeconds: int = 300,
) -> None:
    if leaseDurationSeconds < 1:
        raise ValueError("Lease duration must be positive.")

    with Session(bind=databaseEngine) as databaseSession:
        with databaseSession.begin():
            jobRecord = lockOwnedAiJob(
                databaseSession,
                aiJobId,
                leaseToken,
            )

            databaseTime = databaseSession.scalar(
                select(func.clock_timestamp())
            )

            jobRecord.leaseExpiresAt = max(
                jobRecord.leaseExpiresAt,
                databaseTime
                + timedelta(seconds=leaseDurationSeconds),
            )


def prepareAiChunkPlan(
    databaseEngine: Engine,
    aiJobId: UUID,
    leaseToken: UUID,
    sourceText: str,
) -> list[AiExtractionChunk]:
    if not sourceText.strip():
        raise ValueError("Source text must not be empty.")

    renewAiJobLease(
        databaseEngine,
        aiJobId,
        leaseToken,
    )

    outputSchema = IncidentExtraction.model_json_schema()

    def estimateTokens(chunkText: str) -> int:
        return estimateGroqRequestTokens(
            sourceText=chunkText,
            systemPrompt=extractionSystemPrompt,
            outputSchema=outputSchema,
        )

    # Tokenization and planning happen outside a DB transaction.
    plannedChunks = splitSourceTextForBudget(
        sourceText=sourceText,
        estimateTokens=estimateTokens,
        maxRequestTokens=requestTokenBudget,
    )

    sourceHash = sha256(
        sourceText.encode("utf-8")
    ).hexdigest()

    with Session(
        bind=databaseEngine,
        expire_on_commit=False,
    ) as databaseSession:
        with databaseSession.begin():
            jobRecord = lockOwnedAiJob(
                databaseSession,
                aiJobId,
                leaseToken,
            )

            if jobRecord.sourceTextSha256 != sourceHash:
                raise AiChunkPlanMismatchError(
                    "Source text differs from the queued snapshot."
                )

            savedChunks = list(
                databaseSession.scalars(
                    select(AiExtractionChunk)
                    .where(AiExtractionChunk.aiJobId == aiJobId)
                    .order_by(AiExtractionChunk.chunkIndex)
                ).all()
            )

            if savedChunks:
                if len(savedChunks) != len(plannedChunks):
                    raise AiChunkPlanMismatchError(
                        "The saved chunk count differs "
                        "from the current plan."
                    )

                for savedChunk, plannedChunk in zip(
                    savedChunks,
                    plannedChunks,
                    strict=True,
                ):
                    chunkHash = sha256(
                        plannedChunk.text.encode("utf-8")
                    ).hexdigest()

                    if (
                        savedChunk.chunkIndex
                        != plannedChunk.chunkIndex
                        or savedChunk.startCharacter
                        != plannedChunk.startCharacter
                        or savedChunk.endCharacter
                        != plannedChunk.endCharacter
                        or savedChunk.sourceTextSha256
                        != chunkHash
                    ):
                        raise AiChunkPlanMismatchError(
                            "A saved chunk differs "
                            "from the current plan."
                        )

                return savedChunks

            chunkRecords = [
                AiExtractionChunk(
                    aiJobId=aiJobId,
                    chunkIndex=chunk.chunkIndex,
                    startCharacter=chunk.startCharacter,
                    endCharacter=chunk.endCharacter,
                    sourceTextSha256=sha256(
                        chunk.text.encode("utf-8")
                    ).hexdigest(),
                    status="queued",
                    attemptCount=0,
                )
                for chunk in plannedChunks
            ]

            databaseSession.add_all(chunkRecords)
            databaseSession.flush()

        return chunkRecords
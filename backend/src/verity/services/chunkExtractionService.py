import logging
from collections.abc import Iterator
from dataclasses import dataclass

from verity.config import ApplicationSettings
from verity.schemas.incidentExtractionSchemas import (
    IncidentExtraction,
)
from verity.services.aiExtractionService import (
    extractionSystemPrompt,
    extractIncidentWithGroq,
)
from verity.services.groqRequestBudgetService import (
    estimateGroqRequestTokens,
    requestTokenBudget,
)
from verity.services.textChunkService import (
    splitSourceTextForBudget,
)


chunkLogger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncidentChunkResult:
    chunkIndex: int
    totalChunks: int
    startCharacter: int
    endCharacter: int
    extraction: IncidentExtraction


def extractIncidentChunks(
    sourceText: str,
    applicationSettings: ApplicationSettings,
) -> Iterator[IncidentChunkResult]:
    if not sourceText.strip():
        raise ValueError("Source text must not be empty.")

    outputSchema = IncidentExtraction.model_json_schema()

    def estimateTokens(chunkText: str) -> int:
        return estimateGroqRequestTokens(
            sourceText=chunkText,
            systemPrompt=extractionSystemPrompt,
            outputSchema=outputSchema,
        )

    chunks = splitSourceTextForBudget(
        sourceText=sourceText,
        estimateTokens=estimateTokens,
        maxRequestTokens=requestTokenBudget,
    )

    for chunk in chunks:
        chunkLogger.info(
            "Extracting chunk %s/%s: characters %s to %s.",
            chunk.chunkIndex + 1,
            len(chunks),
            chunk.startCharacter,
            chunk.endCharacter,
        )

        extraction = extractIncidentWithGroq(
            sourceText=chunk.text,
            applicationSettings=applicationSettings,
        )

        chunkLogger.info(
            "Chunk %s/%s passed extraction validation.",
            chunk.chunkIndex + 1,
            len(chunks),
        )

        yield IncidentChunkResult(
            chunkIndex=chunk.chunkIndex,
            totalChunks=len(chunks),
            startCharacter=chunk.startCharacter,
            endCharacter=chunk.endCharacter,
            extraction=extraction,
        )
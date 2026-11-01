from dataclasses import dataclass
from collections.abc import Callable


@dataclass(frozen=True)
class SourceTextChunk:
    chunkIndex: int
    startCharacter: int
    endCharacter: int
    text: str


def splitSourceText(
    sourceText: str,
    maxChunkCharacters: int = 4_000,
    overlapCharacters: int = 400,
) -> list[SourceTextChunk]:
    if maxChunkCharacters < 1:
        raise ValueError("Chunk size must be positive.")

    if not 0 <= overlapCharacters < maxChunkCharacters:
        raise ValueError(
            "Overlap must be nonnegative and smaller "
            "than the chunk size."
        )

    chunks: list[SourceTextChunk] = []
    startCharacter = 0

    while startCharacter < len(sourceText):
        endCharacter = min(
            startCharacter + maxChunkCharacters,
            len(sourceText),
        )

        chunks.append(
            SourceTextChunk(
                chunkIndex=len(chunks),
                startCharacter=startCharacter,
                endCharacter=endCharacter,
                text=sourceText[startCharacter:endCharacter],
            )
        )

        if endCharacter == len(sourceText):
            break

        startCharacter = endCharacter - overlapCharacters

    return chunks

def splitSourceTextForBudget(
    sourceText: str,
    estimateTokens: Callable[[str], int],
    maxRequestTokens: int,
    maxChunkCharacters: int = 4_000,
    overlapCharacters: int = 400,
) -> list[SourceTextChunk]:
    if maxRequestTokens < 1:
        raise ValueError("The token budget must be positive.")

    if maxChunkCharacters < 1:
        raise ValueError("Chunk size must be positive.")

    if not 0 <= overlapCharacters < maxChunkCharacters:
        raise ValueError(
            "Overlap must be nonnegative and smaller "
            "than the maximum chunk size."
        )

    if not sourceText:
        return []

    if estimateTokens("") > maxRequestTokens:
        raise ValueError(
            "The prompt, schema, and reserved output "
            "already exceed the request budget."
        )

    chunks: list[SourceTextChunk] = []
    startCharacter = 0

    while startCharacter < len(sourceText):
        candidateLength = min(
            maxChunkCharacters,
            len(sourceText) - startCharacter,
        )

        while True:
            endCharacter = startCharacter + candidateLength
            candidateText = sourceText[
                startCharacter:endCharacter
            ]

            if estimateTokens(candidateText) <= maxRequestTokens:
                break

            if candidateLength == 1:
                raise ValueError(
                    "Even a one-character chunk exceeds "
                    "the request budget."
                )

            candidateLength = max(1, candidateLength // 2)

        chunks.append(
            SourceTextChunk(
                chunkIndex=len(chunks),
                startCharacter=startCharacter,
                endCharacter=endCharacter,
                text=candidateText,
            )
        )

        if endCharacter == len(sourceText):
            break

        # Reduce overlap for small chunks to ensure progress.
        actualOverlap = min(
            overlapCharacters,
            candidateLength // 4,
        )

        startCharacter = endCharacter - actualOverlap

    return chunks
import re
from bisect import bisect_right

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

    # A boundary is a source word's end, or the document's
    # start/end. Punctuation inside an identifier stays intact.
    boundaries = sorted(
        {0, len(sourceText)}
        | {
            match.end()
            for match in re.finditer(r"\S+", sourceText)
        }
    )

    chunks: list[SourceTextChunk] = []
    startIndex = 0

    while boundaries[startIndex] < len(sourceText):
        startCharacter = boundaries[startIndex]

        characterLimit = min(
            startCharacter + maxChunkCharacters,
            len(sourceText),
        )

        endIndex = (
            bisect_right(boundaries, characterLimit) - 1
        )

        if endIndex <= startIndex:
            raise ValueError(
                "A whole source word or identifier "
                "exceeds the character limit."
            )

        while True:
            endCharacter = boundaries[endIndex]
            candidateText = sourceText[
                startCharacter:endCharacter
            ]

            if estimateTokens(candidateText) <= maxRequestTokens:
                break

            if endIndex == startIndex + 1:
                raise ValueError(
                    "A whole source word or identifier "
                    "cannot fit the request budget."
                )

            endIndex = startIndex + max(
                1,
                (endIndex - startIndex) // 2,
            )

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

        overlapSize = min(
            overlapCharacters,
            len(candidateText) // 4,
        )

        desiredStart = endCharacter - overlapSize

        nextIndex = (
            bisect_right(boundaries, desiredStart) - 1
        )

        # Ensure overlap never prevents forward progress.
        startIndex = (
            nextIndex
            if nextIndex > startIndex
            else endIndex
        )

    return chunks
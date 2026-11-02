from hashlib import sha256

from verity.models import AiExtractionChunk
from verity.schemas.incidentExtractionSchemas import (
    ExtractedFact,
    IncidentExtraction,
    ReportedAction,
)
from verity.services.incidentExtractionService import (
    validateIncidentExtraction,
)


consolidatedExtractionSchemaVersion = "consolidated-1"

singularFieldNames = {
    "reportNumber",
    "incidentDate",
    "site",
    "department",
    "processStage",
    "incidentDescription",
    "reportedImpact",
    "reportedRootCause",
}


def consolidateAiChunks(
    sourceText: str,
    chunkRecords: list[AiExtractionChunk],
) -> dict[str, object]:
    if not sourceText.strip() or not chunkRecords:
        raise ValueError(
            "Consolidation requires source text and saved chunks."
        )

    orderedChunks = sorted(
        chunkRecords,
        key=lambda chunk: chunk.chunkIndex,
    )

    parentJobId = orderedChunks[0].aiJobId
    coveredUntil = 0

    fieldCandidates = {
        fieldName: []
        for fieldName in IncidentExtraction.model_fields
        if fieldName != "documentType"
    }

    candidateLookup = {}
    chunkSummaries = []
    classifications = []

    for expectedIndex, chunk in enumerate(orderedChunks):
        if (
            chunk.aiJobId != parentJobId
            or chunk.chunkIndex != expectedIndex
            or chunk.status != "succeeded"
            or chunk.extractedData is None
        ):
            raise ValueError(
                "Chunks must belong to one job, have consecutive "
                "indexes, and all have succeeded."
            )

        if not (
            0 <= chunk.startCharacter
            <= coveredUntil
            < chunk.endCharacter
            <= len(sourceText)
        ):
            raise ValueError(
                "Chunk ranges contain a gap or invalid progress."
            )

        chunkText = sourceText[
            chunk.startCharacter:chunk.endCharacter
        ]

        if sha256(chunkText.encode("utf-8")).hexdigest() != (
            chunk.sourceTextSha256
        ):
            raise ValueError(
                "A chunk hash does not match its source range."
            )

        extraction = validateIncidentExtraction(
            extractionPayload=chunk.extractedData,
            sourceText=chunkText,
        )

        coveredUntil = chunk.endCharacter
        classifications.append(extraction.documentType)

        chunkSummaries.append({
            "chunkId": str(chunk.chunkId),
            "chunkIndex": chunk.chunkIndex,
            "startCharacter": chunk.startCharacter,
            "endCharacter": chunk.endCharacter,
            "sourceTextSha256": chunk.sourceTextSha256,
            "documentType": extraction.documentType,
        })

        for fieldName in fieldCandidates:
            fieldValue = getattr(extraction, fieldName)

            facts = (
                [fieldValue]
                if isinstance(fieldValue, ExtractedFact)
                else fieldValue
            )

            for fact in facts:
                if fact.value is None:
                    continue

                actionStatus = (
                    fact.actionStatus
                    if isinstance(fact, ReportedAction)
                    else None
                )

                # Deduplicate whitespace variants only.
                # Case, punctuation, units, and status stay distinct.
                candidateKey = (
                    fieldName,
                    " ".join(fact.value.split()),
                    actionStatus,
                )

                candidate = candidateLookup.get(candidateKey)

                if candidate is None:
                    candidate = {
                        "value": fact.value,
                        "actionStatus": actionStatus,
                        "occurrences": [],
                    }

                    candidateLookup[candidateKey] = candidate
                    fieldCandidates[fieldName].append(candidate)

                occurrence = {
                    "chunkIndex": chunk.chunkIndex,
                    "fact": fact.model_dump(mode="json"),
                }

                if occurrence not in candidate["occurrences"]:
                    candidate["occurrences"].append(occurrence)

    if coveredUntil != len(sourceText):
        raise ValueError(
            "The saved chunks do not cover the complete source."
        )

    if all(
        classification == "pharmaIncidentReport"
        for classification in classifications
    ):
        classificationSummary = "allPharma"
    elif all(
        classification == "other"
        for classification in classifications
    ):
        classificationSummary = "allOther"
    else:
        classificationSummary = "mixedOrUncertain"

    return {
        "formatVersion": consolidatedExtractionSchemaVersion,
        "sourceTextSha256": sha256(
            sourceText.encode("utf-8")
        ).hexdigest(),
        "sourceCharacters": len(sourceText),
        "chunkCount": len(orderedChunks),
        "classificationSummary": classificationSummary,
        "reviewStatus": "pending",
        "chunks": chunkSummaries,
        "fieldCandidates": fieldCandidates,
        "fieldsWithMultipleValues": sorted(
            fieldName
            for fieldName in singularFieldNames
            if len(fieldCandidates[fieldName]) > 1
        ),
    }
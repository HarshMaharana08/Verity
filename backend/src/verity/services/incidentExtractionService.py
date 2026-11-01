import re
from verity.schemas.incidentExtractionSchemas import (
    ExtractedFact,
    IncidentExtraction,
    ReportedAction,
)


class SourceQuoteVerificationError(ValueError):
    pass


def findSourceExcerpt(
    excerpt: str,
    sourceText: str,
) -> str | None:
    if excerpt in sourceText:
        return excerpt

    excerptTokens = re.findall(r"\S+", excerpt)

    if not excerptTokens:
        return None

    excerptPattern = r"\s+".join(
        re.escape(token)
        for token in excerptTokens
    )

    sourceMatch = re.search(
        excerptPattern,
        sourceText,
    )

    if sourceMatch is None:
        return None

    return sourceMatch.group(0)


def verifyFactSourceQuotes(
    fact: ExtractedFact,
    sourceText: str,
    fieldPath: str,
) -> None:
    if fact.value is None:
        return

    verifiedQuotes: list[str] = []

    for quoteIndex, sourceQuote in enumerate(
        fact.sourceQuotes,
        start=1,
    ):
        matchedQuote = findSourceExcerpt(
            excerpt=sourceQuote,
            sourceText=sourceText,
        )

        if matchedQuote is None:
            raise SourceQuoteVerificationError(
                f"{fieldPath}: supporting quote "
                f"{quoteIndex} was not found in source text."
            )

        verifiedQuotes.append(matchedQuote)

    matchedValue = None

    for verifiedQuote in verifiedQuotes:
        matchedValue = findSourceExcerpt(
            excerpt=fact.value,
            sourceText=verifiedQuote,
        )

        if matchedValue is not None:
            break

    if matchedValue is None:
        raise SourceQuoteVerificationError(
            f"{fieldPath}: the value was not found "
            "within the verified supporting quotes."
        )

    verifiedFact = ExtractedFact.model_validate({
        "value": matchedValue,
        "sourceQuotes": verifiedQuotes,
    })

    fact.value = verifiedFact.value
    fact.sourceQuotes = verifiedFact.sourceQuotes
    
    if (
        isinstance(fact, ReportedAction)
        and fact.actionStatus != "notStated"
    ):
        matchedStatusQuote = findSourceExcerpt(
            excerpt=fact.statusSourceQuote or "",
            sourceText=sourceText,
        )

        if matchedStatusQuote is None:
            raise SourceQuoteVerificationError(
                f"{fieldPath}: action-status evidence "
                "was not found in source text."
            )

        if findSourceExcerpt(
            excerpt=fact.value,
            sourceText=matchedStatusQuote,
        ) is None:
            raise SourceQuoteVerificationError(
                f"{fieldPath}: action-status evidence "
                "must also contain the action."
            )

        fact.statusSourceQuote = matchedStatusQuote


def validateIncidentExtraction(
    extractionPayload: dict[str, object],
    sourceText: str,
) -> IncidentExtraction:
    if not sourceText.strip():
        raise SourceQuoteVerificationError(
            "Incident extraction requires nonempty source text."
        )

    incidentExtraction = IncidentExtraction.model_validate(
        extractionPayload
    )

    for fieldName in IncidentExtraction.model_fields:
        if fieldName == "documentType":
            continue

        fieldValue = getattr(
            incidentExtraction,
            fieldName,
        )

        if isinstance(fieldValue, ExtractedFact):
            verifyFactSourceQuotes(
                fact=fieldValue,
                sourceText=sourceText,
                fieldPath=fieldName,
            )
        else:
            for factIndex, fact in enumerate(fieldValue):
                verifyFactSourceQuotes(
                    fact=fact,
                    sourceText=sourceText,
                    fieldPath=f"{fieldName}[{factIndex}]",
                )

    return incidentExtraction
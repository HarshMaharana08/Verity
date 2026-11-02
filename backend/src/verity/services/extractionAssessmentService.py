import re
from uuid import UUID

from verity.schemas.extractionAssessmentSchemas import (
    AssessmentFinding,
    ConsolidatedAssessmentInput,
    ExtractionAssessment,
)
from verity.schemas.incidentExtractionSchemas import (
    IncidentExtraction,
)
from verity.services.incidentConsolidationService import (
    singularFieldNames,
)


missingFieldQuestions = {
    "reportNumber": (
        "What is the incident or deviation report identifier, "
        "if one has been assigned?"
    ),
    "incidentDate": "When did the incident occur?",
    "site": "At which site or facility did the incident occur?",
    "department": (
        "Which department was involved, or is this not applicable?"
    ),
    "productNames": (
        "Which products were affected, or is this not applicable?"
    ),
    "batchNumbers": (
        "Which batches or lots were affected, "
        "or is batch identification not applicable?"
    ),
    "equipmentIdentifiers": (
        "Which equipment was involved, or is this not applicable?"
    ),
    "processStage": "During which process stage did the incident occur?",
    "incidentDescription": (
        "What happened, including the observed deviation "
        "and the expected condition?"
    ),
    "reportedImpact": (
        "What impact has been assessed, and what remains undetermined?"
    ),
}

unresolvedImpactPhrases = (
    "not yet been determined",
    "not yet determined",
    "has not been determined",
    "pending assessment",
    "under assessment",
    "not yet assessed",
)


def assessIncidentExtraction(
    extractionId: UUID,
    extractedData: dict[str, object],
) -> ExtractionAssessment:
    assessmentInput = ConsolidatedAssessmentInput.model_validate(
        extractedData
    )

    expectedFields = (
        set(IncidentExtraction.model_fields) - {"documentType"}
    )

    if set(assessmentInput.fieldCandidates) != expectedFields:
        raise ValueError(
            "The consolidated candidate fields are incomplete "
            "or unsupported."
        )

    candidates = assessmentInput.fieldCandidates
    findings: list[AssessmentFinding] = []

    requiresDocumentReview = (
        assessmentInput.classificationSummary != "allPharma"
    )

    if requiresDocumentReview:
        findings.append(
            AssessmentFinding(
                findingId="documentType.documentReview",
                fieldName="documentType",
                kind="documentReview",
                message=(
                    "Chunk classifications do not establish "
                    "a consistent pharma incident report."
                ),
                question=(
                    "Is this the intended incident report? "
                    "Review the document and its chunk classifications."
                ),
            )
        )

        return ExtractionAssessment(
            extractionId=extractionId,
            requiresDocumentReview=True,
            requiresIncidentDescription=(
                not candidates["incidentDescription"]
            ),
            findings=findings,
        )

    for fieldName, question in missingFieldQuestions.items():
        if not candidates[fieldName]:
            findings.append(
                AssessmentFinding(
                    findingId=f"{fieldName}.missing",
                    fieldName=fieldName,
                    kind="missing",
                    message="No supported value was extracted.",
                    question=question,
                )
            )

    for fieldName in sorted(singularFieldNames):
        if len(candidates[fieldName]) > 1:
            findings.append(
                AssessmentFinding(
                    findingId=f"{fieldName}.multipleValues",
                    fieldName=fieldName,
                    kind="multipleValues",
                    message=(
                        "Multiple reported values or excerpts "
                        "require review; they may be compatible."
                    ),
                    question=(
                        f"How should the reported {fieldName} "
                        "values be interpreted or reconciled?"
                    ),
                    candidateIndexes=list(
                        range(len(candidates[fieldName]))
                    ),
                )
            )

    impactIndexes = [
        index
        for index, candidate in enumerate(
            candidates["reportedImpact"]
        )
        if any(
            phrase in " ".join(candidate.value.lower().split())
            for phrase in unresolvedImpactPhrases
        )
    ]

    if impactIndexes:
        findings.append(
            AssessmentFinding(
                findingId="reportedImpact.unresolvedWording",
                fieldName="reportedImpact",
                kind="unresolvedWording",
                message=(
                    "Impact wording suggests an unfinished assessment; "
                    "verify the current documented status."
                ),
                question=(
                    "Has the product-quality impact assessment "
                    "been completed? Provide its outcome and evidence, "
                    "or confirm that it remains pending."
                ),
                candidateIndexes=impactIndexes,
            )
        )

    causeIndexes = [
        index
        for index, candidate in enumerate(
            candidates["reportedRootCause"]
        )
        if re.search(
            r"\b(suspected|possible|probable|unconfirmed)\b",
            candidate.value,
            flags=re.IGNORECASE,
        )
    ]

    if causeIndexes:
        findings.append(
            AssessmentFinding(
                findingId="reportedRootCause.tentativeCause",
                fieldName="reportedRootCause",
                kind="tentativeCause",
                message=(
                    "The reported cause contains tentative wording."
                ),
                question=(
                    "What evidence supports or rules out the "
                    "reported suspected cause?"
                ),
                candidateIndexes=causeIndexes,
            )
        )

    return ExtractionAssessment(
        extractionId=extractionId,
        requiresDocumentReview=False,
        requiresIncidentDescription=(
            not candidates["incidentDescription"]
        ),
        findings=findings,
    )
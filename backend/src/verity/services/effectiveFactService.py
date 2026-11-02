from verity.models import (
    ExtractionReview,
    IncidentExtractionRecord,
)
from verity.schemas.effectiveFactSchemas import (
    EffectiveFactValue,
    EffectiveFactView,
    EffectiveField,
)
from verity.schemas.extractionAssessmentSchemas import (
    ExtractionAssessment,
)
from verity.schemas.extractionReviewSchemas import (
    AcceptedFieldDecision,
    CorrectedFieldDecision,
    ExtractionReviewRequest,
)
from verity.services.extractionAssessmentService import (
    assessIncidentExtraction,
)
from verity.services.incidentConsolidationService import (
    consolidatedExtractionSchemaVersion,
)


def buildEffectiveFactView(
    extractionRecord: IncidentExtractionRecord,
    reviewRecord: ExtractionReview,
) -> EffectiveFactView:
    if reviewRecord.extractionId != extractionRecord.extractionId:
        raise ValueError(
            "The review belongs to a different extraction."
        )

    if (
        extractionRecord.schemaVersion
        != consolidatedExtractionSchemaVersion
    ):
        raise ValueError(
            "Effective facts require a supported consolidated result."
        )

    reviewInput = ExtractionReviewRequest.model_validate({
        "expectedRevision": reviewRecord.revisionNumber - 1,
        "expectedAssessmentVersion": reviewRecord.assessmentVersion,
        "reviewStatus": reviewRecord.reviewStatus,
        "reviewerLabel": reviewRecord.reviewerLabel,
        "fieldDecisions": reviewRecord.fieldDecisions,
        "clarificationResponses": reviewRecord.clarificationResponses,
        "reviewNote": reviewRecord.reviewNote,
    })

    savedAssessment = ExtractionAssessment.model_validate(
        reviewRecord.assessmentSnapshot
    )

    if (
        savedAssessment.extractionId != extractionRecord.extractionId
        or savedAssessment.assessmentVersion
        != reviewRecord.assessmentVersion
    ):
        raise ValueError(
            "The review assessment snapshot is inconsistent."
        )

    currentAssessment = assessIncidentExtraction(
        extractionId=extractionRecord.extractionId,
        extractedData=extractionRecord.extractedData,
    )

    reviewAssessmentCurrent = (
        reviewRecord.assessmentVersion
        == currentAssessment.assessmentVersion
    )

    candidateFields = extractionRecord.extractedData[
        "fieldCandidates"
    ]

    effectiveFields: dict[str, EffectiveField] = {}

    for fieldName, candidates in candidateFields.items():
        decision = reviewInput.fieldDecisions.get(fieldName)

        if decision is None:
            effectiveFields[fieldName] = EffectiveField(
                decision="unreviewed",
                candidateCount=len(candidates),
            )
            continue

        values: list[EffectiveFactValue] = []

        if isinstance(decision, AcceptedFieldDecision):
            for candidateIndex in decision.candidateIndexes:
                if candidateIndex >= len(candidates):
                    raise ValueError(
                        f"{fieldName}: saved candidate index "
                        "does not exist."
                    )

                candidate = candidates[candidateIndex]
                occurrences = candidate.get("occurrences")

                if not isinstance(occurrences, list) or not occurrences:
                    raise ValueError(
                        f"{fieldName}: accepted candidate "
                        "has no evidence occurrences."
                    )

                values.append(
                    EffectiveFactValue(
                        value=candidate["value"],
                        origin="pdfExtraction",
                        candidateIndex=candidateIndex,
                        actionStatus=candidate.get("actionStatus"),
                        occurrences=occurrences,
                    )
                )

        elif isinstance(decision, CorrectedFieldDecision):
            values = [
                EffectiveFactValue(
                    value=correctedValue.value,
                    origin="reviewerSupplied",
                    actionStatus=correctedValue.actionStatus,
                    evidenceNote=correctedValue.evidenceNote,
                )
                for correctedValue in decision.correctedValues
            ]

        effectiveFields[fieldName] = EffectiveField(
            decision=decision.decision,
            candidateCount=len(candidates),
            values=values,
            reason=getattr(decision, "reason", None),
        )

    findingIds = {
        finding.findingId
        for finding in savedAssessment.findings
    }

    if (
        set(reviewInput.clarificationResponses)
        - findingIds
    ):
        raise ValueError(
            "Saved clarification responses reference unknown findings."
        )

    pendingFindingIds = sorted(
        findingId
        for findingId in findingIds
        if (
            findingId not in reviewInput.clarificationResponses
            or reviewInput.clarificationResponses[
                findingId
            ].status == "pending"
        )
    )

    completeFieldReview = (
        set(reviewInput.fieldDecisions) == set(candidateFields)
    )

    descriptionReviewed = (
        effectiveFields["incidentDescription"].decision
        in {"accept", "correct"}
    )

    canDraftHypotheses = (
        reviewRecord.reviewStatus == "approved"
        and reviewAssessmentCurrent
        and not currentAssessment.requiresDocumentReview
        and completeFieldReview
        and descriptionReviewed
        and findingIds
        <= set(reviewInput.clarificationResponses)
    )

    return EffectiveFactView(
        extractionId=extractionRecord.extractionId,
        reviewId=reviewRecord.reviewId,
        revisionNumber=reviewRecord.revisionNumber,
        reviewStatus=reviewRecord.reviewStatus,
        assessmentVersion=reviewRecord.assessmentVersion,
        reviewAssessmentCurrent=reviewAssessmentCurrent,
        canDraftHypotheses=canDraftHypotheses,
        fields=effectiveFields,
        clarificationResponses=reviewInput.clarificationResponses,
        pendingFindingIds=pendingFindingIds,
    )
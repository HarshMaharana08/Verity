from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.schemas.rcaEvidenceAssessmentSchemas import (
    RcaEvidenceAssessment,
    RcaEvidenceFinding,
    RcaHypothesisEvidenceAssessment,
)


rcaEvidenceAssessmentVersion = "rcaEvidenceAssessment.v1"

incidentEvidenceFields = frozenset({
    "incidentDescription",
    "reportedImpact",
})


def assessRcaEvidence(
    validatedDraft: ValidatedRcaDraft,
) -> RcaEvidenceAssessment:
    # Recheck structural references before traversing them.
    draft = ValidatedRcaDraft.model_validate(
        validatedDraft.model_dump(mode="json")
    )

    observationsById = {
        observation.observationId: observation
        for observation in draft.content.observations
    }

    hypothesisAssessments = []

    for hypothesis in draft.content.hypotheses:
        supportingFieldNames = {
            reference.fieldName
            for observationId in hypothesis.supportingObservationIds
            for reference in observationsById[
                observationId
            ].factReferences
        }

        hasReportedCause = (
            "reportedRootCause" in supportingFieldNames
        )
        hasIncidentEvidence = bool(
            supportingFieldNames & incidentEvidenceFields
        )

        findings = []

        if hasReportedCause and not hasIncidentEvidence:
            findings.append(
                RcaEvidenceFinding(
                    findingCode="reportedCauseOnlySupport",
                    explanation=(
                        "The cited support includes a reported cause "
                        "but no incident-description or impact facts. "
                        "A reported suspicion is not independent "
                        "confirmation of its mechanism."
                    ),
                    suggestedReview=(
                        "Identify evidence that could support or "
                        "exclude the proposed mechanism. Preserve "
                        "the reported cause's uncertainty."
                    ),
                )
            )

        elif hasIncidentEvidence and not hasReportedCause:
            findings.append(
                RcaEvidenceFinding(
                    findingCode="incidentOnlySupport",
                    explanation=(
                        "The cited support includes incident or impact "
                        "facts but no reported cause. These facts "
                        "alone may not distinguish this explanation "
                        "from competing explanations."
                    ),
                    suggestedReview=(
                        "Check whether the cited observations support "
                        "this specific mechanism. Request discriminating "
                        "evidence before accepting the explanation."
                    ),
                )
            )

        elif not hasReportedCause and not hasIncidentEvidence:
            findings.append(
                RcaEvidenceFinding(
                    findingCode="contextOnlySupport",
                    explanation=(
                        "The cited support consists of context or "
                        "response actions. Those sources alone do "
                        "not establish the proposed cause."
                    ),
                    suggestedReview=(
                        "Review the hypothesis's relevance and obtain "
                        "incident evidence that tests its mechanism."
                    ),
                )
            )

        hypothesisAssessments.append(
            RcaHypothesisEvidenceAssessment(
                hypothesisId=hypothesis.hypothesisId,
                supportingFieldNames=sorted(
                    supportingFieldNames
                ),
                findings=findings,
            )
        )

    return RcaEvidenceAssessment(
        assessmentVersion=rcaEvidenceAssessmentVersion,
        rcaJobId=draft.rcaJobId,
        sourceReviewId=draft.sourceReviewId,
        inputSha256=draft.inputSha256,
        hypotheses=hypothesisAssessments,
    )
from verity.models import RcaDraftRecord, RcaReview
from verity.schemas.effectiveRcaSchemas import (
    EffectiveRcaHypothesis,
    EffectiveRcaView,
)
from verity.schemas.rcaDraftSchemas import ValidatedRcaDraft
from verity.schemas.rcaEvidenceAssessmentSchemas import (
    RcaEvidenceAssessment,
)
from verity.schemas.rcaReviewSchemas import (
    RcaReviewRequest,
    RevisedRcaHypothesis,
    RetainedRcaHypothesis,
)
from verity.services.rcaEvidenceAssessmentService import (
    assessRcaEvidence,
)


def buildEffectiveRcaView(
    draftRecord: RcaDraftRecord,
    reviewRecord: RcaReview,
) -> EffectiveRcaView:
    if reviewRecord.rcaDraftId != draftRecord.rcaDraftId:
        raise ValueError(
            "The RCA review belongs to a different draft."
        )

    sourceDraft = ValidatedRcaDraft.model_validate(
        draftRecord.draftData
    )

    if (
        sourceDraft.rcaJobId != draftRecord.rcaJobId
        or sourceDraft.schemaVersion != draftRecord.schemaVersion
    ):
        raise ValueError(
            "The saved draft metadata is inconsistent."
        )

    reviewInput = RcaReviewRequest.model_validate({
        "expectedRevision": reviewRecord.revisionNumber - 1,
        "expectedAssessmentVersion": reviewRecord.assessmentVersion,
        "reviewStatus": reviewRecord.reviewStatus,
        "reviewerLabel": reviewRecord.reviewerLabel,
        "hypothesisDecisions": reviewRecord.hypothesisDecisions,
        "findingResponses": reviewRecord.findingResponses,
        "reviewNote": reviewRecord.reviewNote,
    })

    savedAssessment = RcaEvidenceAssessment.model_validate(
        reviewRecord.assessmentSnapshot
    )

    if (
        savedAssessment.rcaJobId != sourceDraft.rcaJobId
        or savedAssessment.sourceReviewId != sourceDraft.sourceReviewId
        or savedAssessment.inputSha256 != sourceDraft.inputSha256
        or savedAssessment.assessmentVersion
        != reviewRecord.assessmentVersion
    ):
        raise ValueError(
            "The saved review assessment is inconsistent."
        )

    currentAssessment = assessRcaEvidence(sourceDraft)

    hypothesisIds = {
        hypothesis.hypothesisId
        for hypothesis in sourceDraft.content.hypotheses
    }

    assessedIds = [
        item.hypothesisId
        for item in savedAssessment.hypotheses
    ]

    if (
        len(assessedIds) != len(set(assessedIds))
        or set(assessedIds) != hypothesisIds
    ):
        raise ValueError(
            "The saved assessment does not match the draft hypotheses."
        )

    if set(reviewInput.hypothesisDecisions) - hypothesisIds:
        raise ValueError(
            "The review references unknown hypotheses."
        )

    findingKeys = {
        f"{item.hypothesisId}:{finding.findingCode}"
        for item in savedAssessment.hypotheses
        for finding in item.findings
    }

    if set(reviewInput.findingResponses) - findingKeys:
        raise ValueError(
            "The review references unknown assessment findings."
        )

    effectiveHypotheses = []

    for hypothesis in sourceDraft.content.hypotheses:
        decision = reviewInput.hypothesisDecisions.get(
            hypothesis.hypothesisId
        )

        effectiveStatement = None
        statementOrigin = None

        if isinstance(decision, RetainedRcaHypothesis):
            effectiveStatement = hypothesis.statement
            statementOrigin = "generated"

        elif isinstance(decision, RevisedRcaHypothesis):
            effectiveStatement = decision.revisedStatement
            statementOrigin = "reviewerSupplied"

        effectiveHypotheses.append(
            EffectiveRcaHypothesis(
                hypothesisId=hypothesis.hypothesisId,
                originalStatement=hypothesis.statement,
                decision=(
                    decision.decision
                    if decision is not None
                    else "unreviewed"
                ),
                effectiveStatement=effectiveStatement,
                statementOrigin=statementOrigin,
                rationale=(
                    decision.rationale
                    if decision is not None
                    else None
                ),
            )
        )

    reviewAssessmentCurrent = (
        savedAssessment.model_dump(mode="json")
        == currentAssessment.model_dump(mode="json")
    )

    reviewComplete = (
        reviewRecord.reviewStatus == "reviewed"
        and reviewAssessmentCurrent
        and set(reviewInput.hypothesisDecisions) == hypothesisIds
        and set(reviewInput.findingResponses) == findingKeys
    )

    return EffectiveRcaView(
        rcaDraftId=draftRecord.rcaDraftId,
        rcaReviewId=reviewRecord.rcaReviewId,
        revisionNumber=reviewRecord.revisionNumber,
        reviewStatus=reviewRecord.reviewStatus,
        reviewerLabel=reviewRecord.reviewerLabel,
        reviewNote=reviewRecord.reviewNote,
        reviewCreatedAt=reviewRecord.createdAt,
        assessmentVersion=reviewRecord.assessmentVersion,
        reviewAssessmentCurrent=reviewAssessmentCurrent,
        reviewComplete=reviewComplete,
        sourceDraft=sourceDraft,
        hypotheses=effectiveHypotheses,
        savedEvidenceAssessment=savedAssessment,
        currentEvidenceAssessment=currentAssessment,
        findingResponses=reviewInput.findingResponses,
    )
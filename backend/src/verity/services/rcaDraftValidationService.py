from verity.models import RcaJob
from verity.schemas.effectiveFactSchemas import (
    EffectiveFactView,
)
from verity.schemas.rcaDraftSchemas import (
    RcaDraftContent,
    ValidatedRcaDraft,
)
from verity.services.rcaJobService import (
    calculateRcaInputSha256,
    rcaSchemaVersion,
)


class InvalidRcaDraftError(ValueError):
    pass


def validateRcaInputSnapshot(
    jobRecord: RcaJob,
) -> EffectiveFactView:
    if jobRecord.schemaVersion != rcaSchemaVersion:
        raise InvalidRcaDraftError(
            "The RCA job uses an unsupported draft schema."
        )

    calculatedSha256 = calculateRcaInputSha256(
        jobRecord.inputSnapshot
    )

    if calculatedSha256 != jobRecord.inputSha256:
        raise InvalidRcaDraftError(
            "The RCA input snapshot fingerprint does not match."
        )

    sourceFacts = EffectiveFactView.model_validate(
        jobRecord.inputSnapshot
    )

    if sourceFacts.reviewId != jobRecord.sourceReviewId:
        raise InvalidRcaDraftError(
            "The snapshot belongs to a different review."
        )

    if (
        sourceFacts.reviewStatus != "approved"
        or not sourceFacts.reviewAssessmentCurrent
        or not sourceFacts.canDraftHypotheses
    ):
        raise InvalidRcaDraftError(
            "The saved facts are not eligible for RCA drafting."
        )

    return sourceFacts


def validateRcaDraft(
    jobRecord: RcaJob,
    draftContent: RcaDraftContent,
) -> ValidatedRcaDraft:
    sourceFacts = validateRcaInputSnapshot(jobRecord)

    # Revalidate even if the caller passes an existing model instance.
    validatedContent = RcaDraftContent.model_validate(
        draftContent.model_dump(mode="json")
    )

    for observation in validatedContent.observations:
        seenReferences: set[tuple[str, int]] = set()

        for reference in observation.factReferences:
            referenceKey = (
                reference.fieldName,
                reference.valueIndex,
            )

            if referenceKey in seenReferences:
                raise InvalidRcaDraftError(
                    f"{observation.observationId}: "
                    "duplicate fact reference."
                )

            seenReferences.add(referenceKey)

            sourceField = sourceFacts.fields.get(
                reference.fieldName
            )

            if sourceField is None:
                raise InvalidRcaDraftError(
                    f"{observation.observationId}: "
                    "referenced field does not exist."
                )

            if sourceField.decision not in {
                "accept",
                "correct",
            }:
                raise InvalidRcaDraftError(
                    f"{observation.observationId}: "
                    "referenced field has no accepted "
                    "or corrected working facts."
                )

            if reference.valueIndex >= len(sourceField.values):
                raise InvalidRcaDraftError(
                    f"{observation.observationId}: "
                    "referenced fact value does not exist."
                )

            sourceValue = sourceField.values[
                reference.valueIndex
            ]

            if (
                sourceValue.origin == "pdfExtraction"
                and not sourceValue.occurrences
            ):
                raise InvalidRcaDraftError(
                    f"{observation.observationId}: "
                    "PDF-derived fact has no evidence occurrences."
                )

            if (
                sourceValue.origin == "reviewerSupplied"
                and (
                    sourceValue.candidateIndex is not None
                    or sourceValue.occurrences
                )
            ):
                raise InvalidRcaDraftError(
                    f"{observation.observationId}: "
                    "reviewer-supplied fact incorrectly "
                    "claims PDF provenance."
                )

    return ValidatedRcaDraft(
        rcaJobId=jobRecord.rcaJobId,
        sourceReviewId=jobRecord.sourceReviewId,
        inputSha256=jobRecord.inputSha256,
        schemaVersion=jobRecord.schemaVersion,
        sourceFacts=sourceFacts,
        content=validatedContent,
    )
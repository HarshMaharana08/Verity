from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from uuid import UUID
from datetime import datetime

from verity.schemas.effectiveFactSchemas import EffectiveFactView


class RcaSchemaBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class RcaFactReference(RcaSchemaBase):
    fieldName: str = Field(min_length=1)
    valueIndex: int = Field(ge=0)


class RcaObservation(RcaSchemaBase):
    observationId: str = Field(
        pattern=r"^obs-[1-9][0-9]*$",
    )
    statement: str = Field(
        min_length=1,
        max_length=3000,
    )
    factReferences: list[RcaFactReference] = Field(
        min_length=1,
        max_length=30,
    )


class RcaEvidenceGap(RcaSchemaBase):
    description: str = Field(
        min_length=1,
        max_length=2000,
    )
    suggestedCheck: str = Field(
        min_length=1,
        max_length=2000,
    )


class RcaHypothesis(RcaSchemaBase):
    hypothesisId: str = Field(
        pattern=r"^hyp-[1-9][0-9]*$",
    )
    statement: str = Field(
        min_length=1,
        max_length=3000,
    )
    status: Literal["unverified"]

    supportingObservationIds: list[str] = Field(
        min_length=1,
        max_length=50,
    )
    contradictoryObservationIds: list[str] = Field(
        max_length=50,
    )
    reasoning: str = Field(
        min_length=1,
        max_length=5000,
    )
    evidenceGaps: list[RcaEvidenceGap] = Field(
        min_length=1,
        max_length=20,
    )


class RcaOpenQuestion(RcaSchemaBase):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )
    reason: str = Field(
        min_length=1,
        max_length=2000,
    )
    relatedHypothesisIds: list[str] = Field(
        max_length=20,
    )


class RcaDraftContent(RcaSchemaBase):
    draftStatus: Literal["draft"]

    observations: list[RcaObservation] = Field(
        min_length=1,
        max_length=100,
    )
    hypotheses: list[RcaHypothesis] = Field(
        max_length=20,
    )
    noHypothesesReason: str | None = Field(
        max_length=3000,
    )
    openQuestions: list[RcaOpenQuestion] = Field(
        max_length=50,
    )

    @model_validator(mode="after")
    def validateDraftReferences(self) -> "RcaDraftContent":
        observationIds = [
            observation.observationId
            for observation in self.observations
        ]
        hypothesisIds = [
            hypothesis.hypothesisId
            for hypothesis in self.hypotheses
        ]

        if len(observationIds) != len(set(observationIds)):
            raise ValueError(
                "Observation IDs must be unique."
            )

        if len(hypothesisIds) != len(set(hypothesisIds)):
            raise ValueError(
                "Hypothesis IDs must be unique."
            )

        knownObservationIds = set(observationIds)
        knownHypothesisIds = set(hypothesisIds)

        for hypothesis in self.hypotheses:
            supportingIds = hypothesis.supportingObservationIds
            contradictoryIds = (
                hypothesis.contradictoryObservationIds
            )

            for references in (
                supportingIds,
                contradictoryIds,
            ):
                if len(references) != len(set(references)):
                    raise ValueError(
                        "Observation references must not repeat."
                    )

                if set(references) - knownObservationIds:
                    raise ValueError(
                        "Hypothesis references an unknown observation."
                    )

            if set(supportingIds) & set(contradictoryIds):
                raise ValueError(
                    "An observation cannot be listed as both "
                    "supporting and contradictory for one hypothesis."
                )

        for question in self.openQuestions:
            references = question.relatedHypothesisIds

            if len(references) != len(set(references)):
                raise ValueError(
                    "Related hypothesis references must not repeat."
                )

            if set(references) - knownHypothesisIds:
                raise ValueError(
                    "Open question references an unknown hypothesis."
                )

        if self.hypotheses:
            if self.noHypothesesReason is not None:
                raise ValueError(
                    "noHypothesesReason must be null "
                    "when hypotheses are provided."
                )

        elif not self.noHypothesesReason:
            raise ValueError(
                "Explain why no hypotheses could be drafted."
            )

        return self
    
class ValidatedRcaDraft(RcaSchemaBase):
    rcaJobId: UUID
    sourceReviewId: UUID
    inputSha256: str
    schemaVersion: str

    sourceFacts: EffectiveFactView
    content: RcaDraftContent
    
class RcaDraftResponse(RcaSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    rcaDraftId: UUID
    rcaJobId: UUID
    schemaVersion: str
    draftData: ValidatedRcaDraft
    createdAt: datetime
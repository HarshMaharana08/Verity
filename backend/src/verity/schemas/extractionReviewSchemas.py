from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from verity.schemas.incidentExtractionSchemas import (
    ExtractedFact,
    IncidentExtraction,
)

from datetime import datetime
from uuid import UUID


ReviewText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=10_000,
    ),
]


class ReviewInputModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


class AcceptedFieldDecision(ReviewInputModel):
    decision: Literal["accept"]

    candidateIndexes: list[
        Annotated[int, Field(ge=0)]
    ] = Field(min_length=1)

    @field_validator("candidateIndexes")
    @classmethod
    def validateUniqueIndexes(
        cls,
        candidateIndexes: list[int],
    ) -> list[int]:
        if len(candidateIndexes) != len(set(candidateIndexes)):
            raise ValueError(
                "Candidate indexes must not contain duplicates."
            )

        return candidateIndexes


class ReviewerValue(ReviewInputModel):
    value: ReviewText

    actionStatus: Literal[
        "proposed",
        "planned",
        "inProgress",
        "completed",
        "notStated",
    ] | None = None

    evidenceNote: ReviewText | None = None


class CorrectedFieldDecision(ReviewInputModel):
    decision: Literal["correct"]
    correctedValues: list[ReviewerValue] = Field(min_length=1)
    reason: ReviewText


class NotApplicableFieldDecision(ReviewInputModel):
    decision: Literal["notApplicable"]
    reason: ReviewText


class UnresolvedFieldDecision(ReviewInputModel):
    decision: Literal["unresolved"]
    reason: ReviewText


FieldDecision = Annotated[
    AcceptedFieldDecision
    | CorrectedFieldDecision
    | NotApplicableFieldDecision
    | UnresolvedFieldDecision,
    Field(discriminator="decision"),
]


class ClarificationResponseInput(ReviewInputModel):
    status: Literal[
        "answered",
        "pending",
        "notApplicable",
    ]

    response: ReviewText
    evidenceNote: ReviewText | None = None


class ExtractionReviewRequest(ReviewInputModel):
    expectedRevision: int = Field(ge=0)

    expectedAssessmentVersion: str = Field(
        min_length=1,
        max_length=50,
    )

    reviewStatus: Literal["draft", "approved"] = "draft"

    reviewerLabel: ReviewText = Field(max_length=100)

    fieldDecisions: dict[str, FieldDecision] = Field(
        default_factory=dict,
    )

    clarificationResponses: dict[
        str,
        ClarificationResponseInput,
    ] = Field(default_factory=dict)

    reviewNote: ReviewText | None = None

    @model_validator(mode="after")
    def validateFieldDecisions(self) -> Self:
        supportedFields = (
            set(IncidentExtraction.model_fields)
            - {"documentType"}
        )

        unknownFields = (
            set(self.fieldDecisions) - supportedFields
        )

        if unknownFields:
            raise ValueError(
                "Unsupported review fields: "
                + ", ".join(sorted(unknownFields))
            )

        actionFields = {
            "reportedCorrectiveActions",
            "reportedPreventiveActions",
        }

        for fieldName, decision in self.fieldDecisions.items():
            isSingular = (
                IncidentExtraction.model_fields[
                    fieldName
                ].annotation is ExtractedFact
            )

            if isinstance(decision, AcceptedFieldDecision):
                if isSingular and len(decision.candidateIndexes) != 1:
                    raise ValueError(
                        f"{fieldName} accepts exactly one candidate."
                    )

            if isinstance(decision, CorrectedFieldDecision):
                if isSingular and len(decision.correctedValues) != 1:
                    raise ValueError(
                        f"{fieldName} requires exactly one "
                        "corrected value."
                    )

                for correctedValue in decision.correctedValues:
                    hasActionStatus = (
                        correctedValue.actionStatus is not None
                    )

                    if hasActionStatus != (fieldName in actionFields):
                        raise ValueError(
                            f"{fieldName}: actionStatus is required "
                            "only for corrective/preventive actions."
                        )

        return self
    
class ExtractionReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reviewId: UUID
    extractionId: UUID
    revisionNumber: int
    reviewStatus: Literal["draft", "approved"]
    reviewerLabel: str
    assessmentVersion: str
    assessmentSnapshot: dict[str, object]
    fieldDecisions: dict[str, FieldDecision]
    clarificationResponses: dict[
        str,
        ClarificationResponseInput,
    ]
    reviewNote: str | None
    createdAt: datetime
    
class ExtractionReviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reviewId: UUID
    extractionId: UUID
    revisionNumber: int
    reviewStatus: Literal["draft", "approved"]
    reviewerLabel: str
    assessmentVersion: str
    reviewNote: str | None
    createdAt: datetime


class ExtractionReviewListResponse(BaseModel):
    items: list[ExtractionReviewSummary]
    pageSize: int
    pageOffset: int
    hasMore: bool
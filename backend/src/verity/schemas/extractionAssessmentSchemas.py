from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCandidateInput(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        strict=True,
    )

    value: str = Field(min_length=1)


class ConsolidatedAssessmentInput(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        strict=True,
    )

    formatVersion: Literal["consolidated-1"]

    classificationSummary: Literal[
        "allPharma",
        "allOther",
        "mixedOrUncertain",
    ]

    fieldCandidates: dict[
        str,
        list[AssessmentCandidateInput],
    ]


class AssessmentFinding(BaseModel):
    findingId: str
    fieldName: str

    kind: Literal[
        "missing",
        "multipleValues",
        "unresolvedWording",
        "tentativeCause",
        "documentReview",
    ]

    message: str
    question: str
    candidateIndexes: list[int] = Field(default_factory=list)


class ExtractionAssessment(BaseModel):
    assessmentVersion: Literal["1"] = "1"
    extractionId: UUID

    requiresDocumentReview: bool
    requiresIncidentDescription: bool
    requiresHumanReview: Literal[True] = True

    findings: list[AssessmentFinding]
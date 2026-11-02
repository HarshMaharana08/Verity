from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RcaEvidenceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findingCode: Literal[
        "reportedCauseOnlySupport",
        "incidentOnlySupport",
        "contextOnlySupport",
    ]
    explanation: str
    suggestedReview: str


class RcaHypothesisEvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesisId: str
    supportingFieldNames: list[str]
    findings: list[RcaEvidenceFinding]

    requiresHumanEvidenceReview: Literal[True] = True


class RcaEvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessmentVersion: str
    rcaJobId: UUID
    sourceReviewId: UUID
    inputSha256: str

    hypotheses: list[RcaHypothesisEvidenceAssessment]
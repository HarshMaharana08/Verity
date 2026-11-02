from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

incidentExtractionSchemaVersion = "3"

class ExtractedFact(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    value: str | None = Field(
        description=(
            "An exact excerpt containing the field value. "
            "Use null when not explicitly stated."
        ),
    )

    sourceQuotes: list[str] = Field(
        description=(
            "Exact supporting excerpts from the extracted "
            "source text. Use an empty list for a null value."
        ),
    )

    @model_validator(mode="after")
    def validateEvidence(self) -> Self:
        if self.value is None:
            if self.sourceQuotes:
                raise ValueError(
                    "A null value must have no source quotes."
                )

            return self

        if not self.value.strip():
            raise ValueError(
                "Use null instead of an empty value."
            )

        if not self.sourceQuotes:
            raise ValueError(
                "A populated value requires source quotes."
            )

        if any(
            not sourceQuote.strip()
            for sourceQuote in self.sourceQuotes
        ):
            raise ValueError(
                "Source quotes must not be empty."
            )

        normalizedValue = " ".join(self.value.split())

        if not any(
            normalizedValue in " ".join(sourceQuote.split())
            for sourceQuote in self.sourceQuotes
        ):
            raise ValueError(
                "The value must appear in a supporting quote, "
                "allowing whitespace differences only."
            )

        return self

class ReportedAction(ExtractedFact):
    actionStatus: Literal[
        "proposed",
        "planned",
        "inProgress",
        "completed",
        "notStated",
    ]

    statusSourceQuote: str | None = Field(
        description=(
            "An exact source excerpt supporting the action status "
            "and containing the action itself. Include the heading "
            "when it establishes the status. Use null for notStated."
        ),
    )

    @model_validator(mode="after")
    def validateActionStatusEvidence(self) -> Self:
        if self.actionStatus == "notStated":
            if self.statusSourceQuote is not None:
                raise ValueError(
                    "notStated must have a null statusSourceQuote."
                )
        elif (
            self.statusSourceQuote is None
            or not self.statusSourceQuote.strip()
        ):
            raise ValueError(
                "A stated action status requires supporting evidence."
            )

        return self

class IncidentExtraction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    documentType: Literal[
        "pharmaIncidentReport",
        "other",
        "uncertain",
    ] = Field(
        description=(
            "Document classification based on its content. "
            "Use uncertain when the content is insufficient."
        ),
    )

    reportNumber: ExtractedFact
    incidentDate: ExtractedFact
    site: ExtractedFact
    department: ExtractedFact

    productNames: list[ExtractedFact]
    batchNumbers: list[ExtractedFact]
    equipmentIdentifiers: list[ExtractedFact]

    processStage: ExtractedFact
    incidentDescription: ExtractedFact
    immediateActions: list[ExtractedFact]
    reportedImpact: ExtractedFact

    reportedRootCause: ExtractedFact = Field(
        description=(
            "An explicitly stated causal explanation for the incident. "
            "Preserve qualifiers such as suspected or probable. "
            "Investigation-status statements, including 'root cause "
            "remains under investigation', are not causal explanations "
            "and must produce value=null with sourceQuotes=[]."
        ),
    )

    reportedCorrectiveActions: list[ReportedAction]
    reportedPreventiveActions: list[ReportedAction]

    @model_validator(mode="after")
    def validateCollectionFacts(self) -> Self:
        factCollections = (
            self.productNames,
            self.batchNumbers,
            self.equipmentIdentifiers,
            self.immediateActions,
            self.reportedCorrectiveActions,
            self.reportedPreventiveActions,
        )

        for factCollection in factCollections:
            if any(
                fact.value is None
                for fact in factCollection
            ):
                raise ValueError(
                    "Collections must contain populated facts. "
                    "Use an empty list when none are reported."
                )

        return self
    
    @model_validator(mode="after")
    def validateDocumentClassification(self) -> Self:
        if self.documentType == "pharmaIncidentReport":
            return self

        for fieldName in type(self).model_fields:
            if fieldName == "documentType":
                continue

            fieldValue = getattr(self, fieldName)

            if isinstance(fieldValue, ExtractedFact):
                hasContent = fieldValue.value is not None
            else:
                hasContent = bool(fieldValue)

            if hasContent:
                raise ValueError(
                    f"{fieldName} must be empty when "
                    f"documentType is {self.documentType}."
                )

        return self
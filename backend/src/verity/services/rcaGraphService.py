from collections.abc import Callable
from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from verity.models import RcaJob
from verity.schemas.effectiveFactSchemas import (
    EffectiveFactView,
)
from verity.schemas.rcaDraftSchemas import (
    RcaDraftContent,
    ValidatedRcaDraft,
)
from verity.services.rcaDraftValidationService import (
    InvalidRcaDraftError,
    validateRcaDraft,
    validateRcaInputSnapshot,
)
from verity.services.rcaJobService import (
    rcaPromptVersion,
    rcaWorkflowVersion,
)


RcaDraftGenerator = Callable[
    [EffectiveFactView],
    RcaDraftContent,
]


class RcaGraphState(TypedDict):
    sourceFacts: NotRequired[EffectiveFactView]
    draftContent: NotRequired[RcaDraftContent]
    validatedDraft: NotRequired[ValidatedRcaDraft]


def runRcaWorkflow(
    jobRecord: RcaJob,
    draftGenerator: RcaDraftGenerator,
) -> ValidatedRcaDraft:
    def validateInput(
        state: RcaGraphState,
    ) -> dict[str, object]:
        if (
            jobRecord.workflowVersion != rcaWorkflowVersion
            or jobRecord.promptVersion != rcaPromptVersion
        ):
            raise InvalidRcaDraftError(
                "The RCA job uses an unsupported "
                "workflow or prompt version."
            )

        sourceFacts = validateRcaInputSnapshot(jobRecord)

        return {"sourceFacts": sourceFacts}

    def generateDraft(
        state: RcaGraphState,
    ) -> dict[str, object]:
        # Give the generator its own copy.
        sourceFacts = state["sourceFacts"].model_copy(
            deep=True
        )

        draftContent = draftGenerator(sourceFacts)

        return {"draftContent": draftContent}

    def validateOutput(
        state: RcaGraphState,
    ) -> dict[str, object]:
        validatedDraft = validateRcaDraft(
            jobRecord=jobRecord,
            draftContent=state["draftContent"],
        )

        return {"validatedDraft": validatedDraft}

    graphBuilder = StateGraph(RcaGraphState)

    graphBuilder.add_node("validateInput", validateInput)
    graphBuilder.add_node("generateDraft", generateDraft)
    graphBuilder.add_node("validateOutput", validateOutput)

    graphBuilder.add_edge(START, "validateInput")
    graphBuilder.add_edge("validateInput", "generateDraft")
    graphBuilder.add_edge("generateDraft", "validateOutput")
    graphBuilder.add_edge("validateOutput", END)

    graph = graphBuilder.compile()
    result = graph.invoke({})

    return result["validatedDraft"]
"""classify node: routes an issue report to the owning bank team/tribe using
structured LLM output.

The node function is built by `make_classify_node(llm_repository)` rather
than constructed at import time, so the `LLMRepository` it runs against is
injected by the caller (see `graph.py`) instead of being a module-level
singleton -- this is what lets tests substitute a fake/stub repository.

Approach: function-calling / tool-calling structured output via
`with_structured_output`, backed by Pydantic validation of the result --
this is the model-native, most reliable way to get structured data out of
an LLM. If the call fails, the issue is routed to OTHER and flagged for
human review rather than blocking the pipeline; retrying is handled by the
existing backfill mechanism, not here.

The team descriptions in CLASSIFY_SYSTEM_PROMPT (see `../prompts.py`) are
what the model uses to decide ownership -- keep them in sync with how the
teams actually divide responsibilities. They were derived from the 77
intent labels in the PolyAI banking77 dataset, grouped into 6 team-sized
clusters plus OTHER.

PRODUCTION NOTE: prefer function-calling over JSON-mode prompting (manually
asking the model to emit a JSON blob and parsing it) -- it's more reliable
and model-native. JSON-mode is only worth falling back to for models that
don't support tool/function calling, which isn't a concern for the Claude
models this project uses. Always validate the output with Pydantic
regardless of which approach is used.
"""

import logging
from typing import Callable

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.issue_classifier.prompts import CLASSIFY_SYSTEM_PROMPT
from src.models.issue_classifier_state import AssignedTeam, IssueClassifierState
from src.repository.llm_repository import LLMRepository

logger = logging.getLogger(__name__)


class IssueClassification(BaseModel):
    team: AssignedTeam = Field(description="The single team best positioned to resolve this issue.")
    reasoning: str = Field(description="One sentence explaining the team assignment.")
    requires_human_review: bool = Field(
        description="True if the assignment is uncertain enough that a human should double-check it."
    )


_classify_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", CLASSIFY_SYSTEM_PROMPT),
        ("human", "Classify this issue report:\n\n{issue_text}"),
    ]
)


def make_classify_node(llm_repository: LLMRepository) -> Callable[[IssueClassifierState], dict]:
    """Build the `classify` node bound to a given `LLMRepository`.

    Taking the repository as a parameter -- rather than constructing one at
    import time -- means the graph's composition root (`graph.py`) decides
    which repository (and therefore which underlying model) each node uses,
    and tests can pass in a fake/stub repository without needing to patch
    module state.
    """
    chain = _classify_prompt | llm_repository.get_model().with_structured_output(IssueClassification)

    def classify(state: IssueClassifierState) -> dict:
        try:
            result: IssueClassification = chain.invoke({"issue_text": state.redacted_input})
            logger.debug(
                "Classifier -- team=%s reasoning=%s",
                result.team.value,
                result.reasoning,
            )
            return {
                "assigned_team": result.team,
                "requires_human_review": result.requires_human_review,
            }
        except Exception as exc:
            logger.error("Classification failed (%s) -- defaulting to OTHER for human review.", exc)
            return {
                "assigned_team": AssignedTeam.OTHER,
                "requires_human_review": True,
            }

    return classify

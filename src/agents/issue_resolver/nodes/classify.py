"""classify node: routes an issue report to the owning Kpler team using
structured LLM output.

Approach: function-calling / tool-calling structured output via
`with_structured_output`, backed by Pydantic validation of the result --
this is the model-native, most reliable way to get structured data out of
an LLM. If the call fails, the issue is routed to OTHER and flagged for
human review rather than blocking the pipeline; retrying is handled by the
existing backfill mechanism, not here.

The team descriptions in DEFAULT_SYSTEM_PROMPT are what the model uses to
decide ownership -- keep them in sync with how the teams actually divide
responsibilities. VOYAGE's description is inferred (not explicitly
specified) and should be confirmed/corrected.

PRODUCTION NOTE: prefer function-calling over JSON-mode prompting (manually
asking the model to emit a JSON blob and parsing it) -- it's more reliable
and model-native. JSON-mode is only worth falling back to for models that
don't support tool/function calling, which isn't a concern for the Claude
models this project uses. Always validate the output with Pydantic
regardless of which approach is used.
"""

import logging

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.models.issue_resolver_state import AssignedTeam, IssueResolverState
from src.repository.llm_repository import LLMRepository

logger = logging.getLogger(__name__)

llm_repository = LLMRepository()

DEFAULT_SYSTEM_PROMPT = """You are an expert issue-triage classifier for Kpler, a maritime and \
commodities intelligence platform. Read a user's issue report and decide which single internal \
team owns it.

Teams and what they own:
- cargo_models: Vessel cargo-carrying information -- the volume of cargo carried, and the type of \
products/commodities on board.
- freight: Vessel congestion, vessel build dates, zone calls, and how many vessels are congested \
near a port.
- flows: The overall import and export volumes of commodities (oil, diesel, petrol, agricultural \
products, etc.) moving between countries.
- compliance: How many vessels are currently sanctioned, and how often a vessel's flag or MMSI \
changes.
- insights: Written analysis of how cargo flows change in relation to markets, wars, or economic \
events -- articles combining Kpler product data with real news.
- ui: General bugs or issues with the user interface itself, not the underlying data.
- voyage: Vessel voyage details -- port calls, ETA/ETD, routes taken, and voyage history.
- ais_ingress: Vessel position (AIS) data -- delayed, missing, or historic vessel positions.
- other: Use only if the issue genuinely does not fit any team above.

Read the issue carefully and pick the single team best positioned to resolve it."""


class IssueClassification(BaseModel):
    team: AssignedTeam = Field(description="The single team best positioned to resolve this issue.")
    confidence: float = Field(ge=0.0, le=1.0, description="How confident the classifier is (0.0-1.0).")
    reasoning: str = Field(description="One sentence explaining the team assignment.")
    requires_human_review: bool = Field(
        description="True if the assignment is uncertain enough that a human should double-check it."
    )


_classify_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", DEFAULT_SYSTEM_PROMPT),
        ("human", "Classify this issue report:\n\n{issue_text}"),
    ]
)
_classify_chain = _classify_prompt | llm_repository.get_model().with_structured_output(IssueClassification)


def classify(state: IssueResolverState) -> dict:
    try:
        result: IssueClassification = _classify_chain.invoke({"issue_text": state.redacted_input})
        logger.debug(
            "Classifier -- team=%s confidence=%.2f reasoning=%s",
            result.team.value,
            result.confidence,
            result.reasoning,
        )
        return {
            "assigned_team": result.team,
            "classification_confidence": result.confidence,
            "requires_human_review": result.requires_human_review,
        }
    except Exception as exc:
        logger.error("Classification failed (%s) -- defaulting to OTHER for human review.", exc)
        return {"assigned_team": AssignedTeam.OTHER, "classification_confidence": 0.0, "requires_human_review": True}

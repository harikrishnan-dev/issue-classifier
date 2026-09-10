"""cost_log_node node: logs the run's outcome and finalizes the answer."""

import logging

from src.dto.agent_io import AgentOutput
from src.models.issue_resolver_state import IssueResolverState

logger = logging.getLogger(__name__)


def cost_log_node(state: IssueResolverState) -> AgentOutput:
    team = state.assigned_team.value if state.assigned_team else None
    logger.info(
        "issue_resolver run complete team=%s valid=%s injection=%s",
        team,
        state.is_valid,
        state.injection_detected.value if state.injection_detected else None,
    )
    evaluation = state.evaluation or f"Issue routed to the '{team}' team and validated successfully."
    return AgentOutput(evaluation=evaluation)

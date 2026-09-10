"""final node: the graph's single terminal node.

Every path through the graph -- a blocked prompt injection, an inconclusive
injection check, a failed validation, or a successful classification --
converges here and this node produces the `evaluation` string `AgentOutput`
returns to the caller, plus one summary log line.

This replaces what used to be two separate nodes (`fallback` and
`cost_log_node`) that both fed into the same terminal step. Splitting
"build the safe/error message" from "build the success message and log it"
across two files didn't buy anything -- both were just picking one message
based on state fields the graph already routes on -- so the logic now lives
in one place.

Cost/token/latency tracking is intentionally NOT done here: that's what
LangSmith (or equivalent tracing) is for, and it does a far better job of it
than a hand-rolled log line would. The one `logger.info` call below is a
plain operational summary, not a substitute for tracing.
"""

import logging

from src.models.issue_classifier_state import InjectionStatus, IssueClassifierState

logger = logging.getLogger(__name__)


def final(state: IssueClassifierState) -> dict:
    team = state.assigned_team.value if state.assigned_team else None
    cases = (
        (
            state.injection_detected == InjectionStatus.YES,
            f"This request could not be processed because it looks like a prompt injection attempt "
            f"({state.injection_pattern}).",
        ),
        (
            state.injection_detected == InjectionStatus.NOT_ABLE_TO_DETECT,
            "This request could not be processed because we could not verify it was safe to process.",
        ),
        (state.is_valid is False, f"This request could not be processed: {state.validation_error}"),
    )
    default_message = f"Issue routed to the '{team}' team and validated successfully."
    message = next((msg for is_case, msg in cases if is_case), default_message)

    logger.info(
        "issue_classifier run complete team=%s valid=%s injection=%s",
        team,
        state.is_valid,
        state.injection_detected.value if state.injection_detected else None,
    )
    return {"evaluation": message}

"""Routing functions for the issue classifier agent graph.

These decide which node the graph moves to next based on the current
`IssueClassifierState`. Node logic lives in `nodes/`; graph assembly lives in
`graph.py`.
"""

from typing import Literal

from src.models.issue_classifier_state import InjectionStatus, IssueClassifierState


def route_after_injection_check(state: IssueClassifierState) -> Literal["final", "classify"]:
    # Fail safe: only a definite "no" proceeds. Both a confirmed injection
    # and an inconclusive guard call ("not able to detect") skip straight to
    # `final`, which builds the appropriate safe/error message itself.
    return "classify" if state.injection_detected == InjectionStatus.NO else "final"

"""Routing functions for the issue resolver agent graph.

These decide which node the graph moves to next based on the current
`IssueResolverState`. Node logic lives in `nodes.py`; graph assembly lives in
`graph.py`.
"""

from typing import Literal

from src.models.issue_resolver_state import InjectionStatus, IssueResolverState


def route_after_injection_check(state: IssueResolverState) -> Literal["fallback", "classify"]:
    # Fail safe: only a definite "no" proceeds. Both a confirmed injection
    # and an inconclusive guard call ("not able to detect") fall back.
    return "classify" if state.injection_detected == InjectionStatus.NO else "fallback"


def route_after_validate(state: IssueResolverState) -> Literal["fallback", "cost_log_node"]:
    return "cost_log_node" if state.is_valid else "fallback"

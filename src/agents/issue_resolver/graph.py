"""Builds and compiles the issue resolver agent graph.

Node logic lives one function per file under `nodes/`, and routing logic in
`edges.py`; this module wires those functions into a StateGraph via a
`build_graph` factory and exposes the module-level `graph` that
`langgraph.json` points at, plus a `run` helper for other callers (e.g. the
FastAPI backend) that just want to run one input through the graph without
managing it themselves.

Flow:
    pii_redacter -> injection_check -> [fallback | classify]
    classify -> validate -> [fallback | cost_log_node]
    fallback -> cost_log_node -> END
"""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.issue_resolver.edges import route_after_injection_check, route_after_validate
from src.agents.issue_resolver.nodes.classify import classify
from src.agents.issue_resolver.nodes.cost_log_node import cost_log_node
from src.agents.issue_resolver.nodes.fallback import fallback
from src.agents.issue_resolver.nodes.injection_check import injection_check
from src.agents.issue_resolver.nodes.pii_redacter import pii_redacter
from src.agents.issue_resolver.nodes.validate import validate
from src.dto.agent_io import AgentInput, AgentOutput
from src.models.issue_resolver_state import IssueResolverState


def build_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None, output_schema: Optional[type] = AgentOutput
) -> CompiledStateGraph:
    if output_schema is not None:
        builder = StateGraph[IssueResolverState, None, AgentInput, AgentOutput](
            IssueResolverState, input_schema=AgentInput, output_schema=output_schema
        )
    else:
        builder = StateGraph[IssueResolverState, None, AgentInput](IssueResolverState, input_schema=AgentInput)
    builder.add_node("pii_redacter", pii_redacter)
    builder.add_node("injection_check", injection_check)
    builder.add_node("classify", classify)
    # builder.add_node("validate", validate)
    builder.add_node("fallback", fallback)
    # builder.add_node("cost_log_node", cost_log_node)

    builder.add_edge(START, "pii_redacter")
    builder.add_edge("pii_redacter", "injection_check")
    builder.add_conditional_edges("injection_check", route_after_injection_check)
    builder.add_edge("classify", END)
    # builder.add_conditional_edges("validate", route_after_validate)
    # builder.add_edge("fallback", "cost_log_node")
    # builder.add_edge("cost_log_node", END)

    return builder.compile(checkpointer=checkpointer)


# `graph` is what langgraph.json points at. The LangGraph API/Studio platform
# manages checkpointing itself, so this instance must NOT have a custom
# checkpointer attached (the platform ignores/warns about it otherwise).
graph = build_graph()

# `graph.invoke()` filters its return value down to whatever `AgentOutput`
# declares (just `evaluation`), which drops fields like `redacted_input`
# that matter while the rest of the pipeline is still being wired up. This
# instance skips that filtering so `run` can hand back whatever state the
# active nodes actually produced.
_runner_graph = build_graph(output_schema=None)


def run(user_input: str) -> dict:
    """Run a single input through the graph and return the resulting state.

    No checkpointer/config needed: each call is a single, independent
    invocation with nothing to persist or resume across turns.
    """
    return _runner_graph.invoke({"user_input": user_input})

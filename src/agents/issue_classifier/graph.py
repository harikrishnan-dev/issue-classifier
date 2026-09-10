"""Builds and compiles the issue classifier agent graph.

Node logic lives one function per file under `nodes/`, and routing logic in
`edges.py`; this module wires those functions into a StateGraph via a
`build_graph` factory and exposes the module-level `graph` that
`langgraph.json` points at, plus a `run` helper for other callers (e.g. the
FastAPI backend) that just want to run one input through the graph without
managing it themselves.

Flow:
    pii_redacter -> injection_check -> [final | classify]
    classify -> validate -> final -> END

`final` is the graph's single terminal node -- every path (a blocked
injection, an inconclusive injection check, a failed validation, or a
successful classification) converges there.
"""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.issue_classifier.edges import route_after_injection_check
from src.agents.issue_classifier.nodes.classify_issues import make_classify_node
from src.agents.issue_classifier.nodes.final import final
from src.agents.issue_classifier.nodes.injection_check import GUARD_MODEL, make_injection_check_node
from src.agents.issue_classifier.nodes.pii_redacter import pii_redacter
from src.agents.issue_classifier.nodes.validate import validate
from src.dto.agent_io import AgentInput, AgentOutput
from src.models.issue_classifier_state import IssueClassifierState
from src.repository.llm_repository import LLMRepository
from src.store.anthropic_store import AnthropicStore


def build_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    output_schema: Optional[type] = AgentOutput,
    llm_repository: Optional[LLMRepository] = None,
    guard_llm_repository: Optional[LLMRepository] = None,
) -> CompiledStateGraph:
    """Build the graph, wiring each LLM-backed node to an `LLMRepository`.

    `llm_repository`/`guard_llm_repository` default to real Anthropic-backed
    repositories, but accepting them as parameters means this is the single
    place that decides which repository each node uses -- callers (tests
    included) can pass in a fake/stub repository instead, without patching
    module state inside the node files.
    """
    llm_repository = llm_repository or LLMRepository()
    guard_llm_repository = guard_llm_repository or LLMRepository(AnthropicStore(model=GUARD_MODEL))

    if output_schema is not None:
        builder = StateGraph[IssueClassifierState, None, AgentInput, AgentOutput](
            IssueClassifierState, input_schema=AgentInput, output_schema=output_schema
        )
    else:
        builder = StateGraph[IssueClassifierState, None, AgentInput](IssueClassifierState, input_schema=AgentInput)
    builder.add_node("pii_redacter", pii_redacter)
    builder.add_node("injection_check", make_injection_check_node(guard_llm_repository))
    builder.add_node("classify", make_classify_node(llm_repository))
    builder.add_node("validate", validate)
    builder.add_node("final", final)

    builder.add_edge(START, "pii_redacter")
    builder.add_edge("pii_redacter", "injection_check")
    builder.add_conditional_edges("injection_check", route_after_injection_check)
    builder.add_edge("classify", "validate")
    builder.add_edge("validate", "final")
    builder.add_edge("final", END)

    return builder.compile(checkpointer=checkpointer)


# `graph` is what langgraph.json points at. The LangGraph API/Studio platform
# manages checkpointing itself, so this instance must NOT have a custom
# checkpointer attached (the platform ignores/warns about it otherwise).
graph = build_graph()

# `graph.invoke()` filters its return value down to whatever `AgentOutput`
# declares (just `evaluation`), which drops fields like `redacted_input`,
# `assigned_team`, and `requires_human_review` that callers like the FastAPI
# backend need. This instance skips that filtering so `run` can hand back
# the full internal state.
_runner_graph = build_graph(output_schema=None)


def run(user_input: str) -> dict:
    """Run a single input through the graph and return the resulting state.

    No checkpointer/config needed: each call is a single, independent
    invocation with nothing to persist or resume across turns.
    """
    return _runner_graph.invoke({"user_input": user_input})

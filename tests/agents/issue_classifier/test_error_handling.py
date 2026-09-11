"""Unit tests proving the pipeline degrades gracefully when a Claude API
call fails, instead of raising and taking the whole run down.

Uses fake `LLMRepository`-shaped objects (no real Anthropic calls) whose
`get_model().with_structured_output(...)` returns a runnable that always
raises, simulating an API outage/error on the wire.
"""

from langchain_core.runnables import RunnableLambda

from src.agents.issue_classifier.graph import build_graph
from src.agents.issue_classifier.nodes.classify_issues import make_classify_node
from src.agents.issue_classifier.nodes.injection_check import make_injection_check_node
from src.models.issue_classifier_state import (
    AssignedTeam,
    InjectionJudgement,
    InjectionStatus,
    IssueClassifierState,
)


class _RaisingChatModel:
    """Stands in for `LLMRepository.get_model()`: any structured-output call
    raises, like a Claude API failure would."""

    def with_structured_output(self, schema):
        def _raise(_input):
            raise RuntimeError("simulated Claude API failure")

        return RunnableLambda(_raise)


class FailingLLMRepository:
    def get_model(self):
        return _RaisingChatModel()

    def invoke(self, messages):
        raise RuntimeError("simulated Claude API failure")

    def as_text(self, content):
        return str(content)


class _ClearChatModel:
    """Guard model that always judges input as legitimate, so tests can
    isolate a downstream (classify) failure without also failing the guard."""

    def with_structured_output(self, schema):
        def _ok(_input):
            return InjectionJudgement(
                is_injection=False, confidence=0.95, reasoning="Legitimate issue report.", detected_pattern=None
            )

        return RunnableLambda(_ok)


class ClearGuardLLMRepository:
    def get_model(self):
        return _ClearChatModel()

    def invoke(self, messages):
        return "ok"

    def as_text(self, content):
        return str(content)


def test_classify_node_falls_back_to_other_on_llm_failure():
    classify = make_classify_node(FailingLLMRepository())
    state = IssueClassifierState(user_input="my card was declined", redacted_input="my card was declined")

    result = classify(state)

    assert result == {"assigned_team": AssignedTeam.OTHER, "requires_human_review": True}


def test_injection_check_node_fails_safe_on_llm_failure():
    injection_check = make_injection_check_node(FailingLLMRepository())
    state = IssueClassifierState(user_input="my card was declined", redacted_input="my card was declined")

    result = injection_check(state)

    assert result == {"injection_detected": InjectionStatus.NOT_ABLE_TO_DETECT, "injection_pattern": None}


def test_graph_run_completes_when_guard_llm_fails():
    graph = build_graph(
        output_schema=None,
        llm_repository=ClearGuardLLMRepository(),
        guard_llm_repository=FailingLLMRepository(),
    )

    state = graph.invoke({"user_input": "my card was declined and I need help"})

    assert state["injection_detected"] == InjectionStatus.NOT_ABLE_TO_DETECT
    assert state.get("assigned_team") is None
    assert "could not be processed" in state["evaluation"]


def test_graph_run_completes_when_classify_llm_fails():
    graph = build_graph(
        output_schema=None,
        llm_repository=FailingLLMRepository(),
        guard_llm_repository=ClearGuardLLMRepository(),
    )

    state = graph.invoke({"user_input": "my card was declined and I need help"})

    assert state["injection_detected"] == InjectionStatus.NO
    assert state["assigned_team"] == AssignedTeam.OTHER
    assert state["requires_human_review"] is True
    assert state["is_valid"] is True
    assert "other" in state["evaluation"].lower()

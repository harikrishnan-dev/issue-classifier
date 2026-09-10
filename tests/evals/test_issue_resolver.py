"""End-to-end DeepEval suite for the issue_resolver agent.

No tracing is set up for this agent yet, so this uses the no-tracing
fallback shape: call the real app entry point (`run`), build a minimal
`LLMTestCase` from its output plus the golden's reference fields, and hand
that to `assert_test`.

Run with:
    deepeval test run tests/evals/test_issue_resolver.py
"""

import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase

from src.agents.issue_resolver.graph import run
from tests.evals.metrics import SINGLE_TURN_METRICS

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(file_path="tests/evals/.dataset.json")


def _actual_output_for(user_input: str) -> str:
    """Summarize the graph's resulting state into one string a judge LLM
    can evaluate.

    `run()` returns raw pipeline state rather than one final answer field:
    `validate`/`cost_log_node` (which would set `evaluation` for a
    successful classification) aren't wired into `build_graph()` yet, so
    `evaluation` is only present on the fallback (injection/invalid) path.
    """
    state = run(user_input) or {}
    injection = state.get("injection_detected")
    team = state.get("assigned_team")

    parts = [f"injection_detected={injection.value if injection else injection}"]
    if team:
        parts.append(f"assigned_team={team.value}")
    if state.get("evaluation"):
        parts.append(f"message={state['evaluation']}")
    if state.get("redacted_input"):
        parts.append(f"redacted_input={state['redacted_input']}")
    return "; ".join(parts)


@pytest.mark.parametrize("golden", dataset.goldens)
def test_issue_resolver(golden: Golden):
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=_actual_output_for(golden.input),
        expected_output=golden.expected_output,
    )
    assert_test(test_case=test_case, metrics=SINGLE_TURN_METRICS)

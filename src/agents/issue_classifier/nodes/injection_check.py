"""injection_check node: prompt injection detection using LLM-as-a-judge.

A dedicated guard LLM evaluates the redacted user input and decides whether
it's a legitimate issue report or an attempt to hijack/override the agent's
own instructions. Because it reasons about intent rather than matching
fixed strings, it generalises to novel phrasings that a regex blocklist
would miss.

PRODUCTION NOTE: the guard runs on a fast/cheap model (see GUARD_MODEL),
independent of whichever model the rest of the pipeline uses, to keep guard
latency low. In a real system, also log every detection event -- including
near-misses -- to build a continuous-improvement dataset, and rate-limit
callers that trigger repeated injection alerts.

The node function is built by `make_injection_check_node(llm_repository)`
rather than constructed at import time, so the `LLMRepository` it runs
against is injected by the caller (see `graph.py`) instead of being a
module-level singleton -- this is what lets tests substitute a fake/stub
repository.
"""

import logging
import os
from typing import Callable

from langchain_core.prompts import ChatPromptTemplate

from src.agents.issue_classifier.prompts import GUARD_SYSTEM_PROMPT
from src.models.issue_classifier_state import InjectionJudgement, InjectionStatus, IssueClassifierState
from src.repository.llm_repository import LLMRepository

logger = logging.getLogger(__name__)

GUARD_MODEL = os.getenv("ISSUE_CLASSIFIER_GUARD_MODEL", "claude-haiku-4-5-20251001")


GUARD_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", GUARD_SYSTEM_PROMPT),
        ("human", "Evaluate this user-submitted text:\n\n<input>\n{user_input}\n</input>"),
    ]
)


def make_injection_check_node(llm_repository: LLMRepository) -> Callable[[IssueClassifierState], dict]:
    """Build the `injection_check` node bound to a given `LLMRepository`.

    Fails safe: if the guard call itself errors, `injection_detected` is
    marked NOT_ABLE_TO_DETECT (not a definite yes/no) so downstream routing
    still treats it as unsafe rather than letting unvetted content through.
    """
    chain = GUARD_PROMPT | llm_repository.get_model().with_structured_output(InjectionJudgement)

    def injection_check(state: IssueClassifierState) -> dict:
        try:
            judgement: InjectionJudgement = chain.invoke({"user_input": state.redacted_input})
            logger.debug(
                "Guard LLM -- is_injection=%s confidence=%.2f reasoning=%s",
                judgement.is_injection,
                judgement.confidence,
                judgement.reasoning,
            )
            if judgement.is_injection:
                pattern = judgement.detected_pattern or "llm_judge_flagged"
                logger.warning("Injection detected by LLM judge: %s", pattern)
                return {"injection_detected": InjectionStatus.YES, "injection_pattern": pattern}
            return {"injection_detected": InjectionStatus.NO, "injection_pattern": None}
        except Exception:
            logger.exception("Guard LLM call failed -- unable to determine injection status.")
            return {"injection_detected": InjectionStatus.NOT_ABLE_TO_DETECT, "injection_pattern": None}

    return injection_check

"""Sentiment/priority heuristics for the chat frontend.

Sentiment and priority aren't modeled by any graph node yet, so these derive
them from simple keyword heuristics until a dedicated node exists.
"""

from src.frontend.dto import _NEGATIVE_WORDS, _POSITIVE_WORDS, _URGENT_WORDS
from src.models.issue_classifier_state import AssignedTeam


def sentiment_for(text: str) -> str:
    words = set(text.lower().split())
    return "negative" if words & _NEGATIVE_WORDS else "positive" if words & _POSITIVE_WORDS else "neutral"


def priority_for(text: str, team: AssignedTeam, is_valid: bool) -> str:
    if not is_valid:
        return "low"
    words = set(text.lower().split())
    return "high" if words & _URGENT_WORDS else "medium" if team == AssignedTeam.IDENTITY_SECURITY else "low"

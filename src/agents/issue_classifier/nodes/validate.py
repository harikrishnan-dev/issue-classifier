"""validate node: checks the classified issue has enough information to proceed."""

from src.models.issue_classifier_state import IssueClassifierState


def validate(state: IssueClassifierState) -> dict:
    if not state.redacted_input or not state.redacted_input.strip():
        return {"is_valid": False, "validation_error": "The issue description is empty."}
    if state.assigned_team is None:
        return {"is_valid": False, "validation_error": "The issue could not be routed to a team."}
    return {"is_valid": True, "validation_error": None}

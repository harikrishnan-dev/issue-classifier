"""fallback node: produces a safe response when injection is detected or validation fails."""

from src.models.issue_resolver_state import InjectionStatus, IssueResolverState


def fallback(state: IssueResolverState) -> dict:
    if state.injection_detected == InjectionStatus.YES:
        message = (
            "This request could not be processed because it looks like a prompt injection attempt "
            f"({state.injection_pattern})."
        )
    elif state.injection_detected == InjectionStatus.NOT_ABLE_TO_DETECT:
        message = "This request could not be processed because we could not verify it was safe to process."
    else:
        message = f"This request could not be processed: {state.validation_error}"
    return {"evaluation": message}

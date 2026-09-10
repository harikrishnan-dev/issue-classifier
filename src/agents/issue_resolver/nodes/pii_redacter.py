"""pii_redacter node: strips personally identifiable information from the
raw user input before it reaches any LLM call.
"""

from src.models.issue_resolver_state import IssueResolverState
from src.store.presidio_store import PresidioStore

presidio_store = PresidioStore()


def pii_redacter(state: IssueResolverState) -> dict[str, str]:
    return {"redacted_input": presidio_store.redact(state.user_input)}

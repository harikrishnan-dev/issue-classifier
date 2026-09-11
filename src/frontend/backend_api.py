"""FastAPI backend for the issue classifier chat frontend (index.html).

Runs each message through the issue_classifier LangGraph agent via `run()`
(see src/agents/issue_classifier/graph.py) and maps the resulting state onto
the fields the chat page renders.

The graph itself produces the routed team/validity/reasoning (via
`assigned_team`, `is_valid`, `evaluation`); sentiment and priority aren't
modeled by any node yet, so they're derived via keyword heuristics in
`src/frontend/utils.py` until a dedicated node exists for them.

Run with:
    uvicorn src.frontend.backend_api:app --reload --port 8000
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.agents.issue_classifier.graph import run
from src.frontend.dto import AnalyzeRequest, AnalyzeResponse, _TEAM_LABELS
from src.frontend.utils import priority_for, sentiment_for
from src.models.issue_classifier_state import AssignedTeam

logger = logging.getLogger(__name__)

app = FastAPI(title="Issue Classifier API")

# The chat page can be opened directly as a file:// page or served from a
# different port, so allow any origin rather than trying to enumerate them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        state = run(request.message) or {}
    except Exception:
        logger.exception("issue_classifier graph run failed unexpectedly.")
        state = {"evaluation": "This request could not be processed due to an unexpected error. Please try again."}

    team = state.get("assigned_team") or AssignedTeam.OTHER
    is_valid = bool(state.get("is_valid"))
    text = state.get("redacted_input") or request.message

    return AnalyzeResponse(
        redacted_message=text,
        token_count=len(text.split()),
        category=team.value,
        assigned_team=_TEAM_LABELS.get(team, "General / Unclassified"),
        sentiment=sentiment_for(text),
        priority=priority_for(text, team, is_valid),
        reasoning=state.get("evaluation") or "No reasoning available.",
    )

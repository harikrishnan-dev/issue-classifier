"""FastAPI backend for the issue resolver chat frontend (index.html).

Runs each message through the issue_resolver LangGraph agent via `run()`
(see src/agents/issue_resolver/graph.py) and maps the resulting state onto
the fields the chat page renders.

The graph itself produces the routed team/validity/reasoning (via
`assigned_team`, `is_valid`, `evaluation`); sentiment and priority aren't
modeled by any node yet, so they're derived here with simple keyword
heuristics until a dedicated node exists for them.

Run with:
    uvicorn src.frontend.backend_api:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.issue_resolver.graph import run
from src.models.issue_resolver_state import AssignedTeam

app = FastAPI(title="Issue Resolver API")

# The chat page can be opened directly as a file:// page or served from a
# different port, so allow any origin rather than trying to enumerate them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Human-friendly labels for the team the classifier assigns -- purely
# cosmetic, doesn't affect routing.
_TEAM_LABELS = {
    AssignedTeam.CARGO_MODELS: "Cargo Models",
    AssignedTeam.FREIGHT: "Freight",
    AssignedTeam.FLOWS: "Flows",
    AssignedTeam.COMPLIANCE: "Compliance",
    AssignedTeam.INSIGHTS: "Insights",
    AssignedTeam.UI: "UI",
    AssignedTeam.VOYAGE: "Voyage",
    AssignedTeam.AIS_INGRESS: "AIS Ingress",
    AssignedTeam.OTHER: "General / Unclassified",
}

_NEGATIVE_WORDS = {"angry", "frustrated", "terrible", "awful", "hate", "worst", "broken", "crash", "crashes"}
_POSITIVE_WORDS = {"great", "love", "thanks", "awesome", "good", "please"}
_URGENT_WORDS = {"urgent", "asap", "critical", "down", "blocked", "immediately"}


class AnalyzeRequest(BaseModel):
    message: str


class AnalyzeResponse(BaseModel):
    redacted_message: str
    token_count: int
    category: str
    assigned_team: str
    sentiment: str
    priority: str
    reasoning: str


def _sentiment_for(text: str) -> str:
    words = set(text.lower().split())
    if words & _NEGATIVE_WORDS:
        return "negative"
    if words & _POSITIVE_WORDS:
        return "positive"
    return "neutral"


def _priority_for(text: str, team: AssignedTeam, is_valid: bool) -> str:
    if not is_valid:
        return "low"
    if set(text.lower().split()) & _URGENT_WORDS:
        return "high"
    return "medium" if team == AssignedTeam.COMPLIANCE else "low"


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    # `graph.invoke()` filters its return value down to whatever
    # `AgentOutput` declares, so it comes back as `None` unless a node
    # further along the (currently partial) pipeline sets `evaluation`.
    state = run(request.message) or {}

    team = state.get("assigned_team") or AssignedTeam.OTHER
    is_valid = bool(state.get("is_valid"))
    text = state.get("redacted_input") or request.message

    return AnalyzeResponse(
        redacted_message=text,
        token_count=len(text.split()),
        category=team.value,
        assigned_team=_TEAM_LABELS.get(team, "General / Unclassified"),
        sentiment=_sentiment_for(text),
        priority=_priority_for(text, team, is_valid),
        reasoning=state.get("evaluation") or "No reasoning available.",
    )

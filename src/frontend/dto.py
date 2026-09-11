from src.models.issue_classifier_state import AssignedTeam
from pydantic import BaseModel

# Human-friendly labels for the team the classifier assigns -- purely
# cosmetic, doesn't affect routing.
_TEAM_LABELS = {
    AssignedTeam.CARD_LIFECYCLE: "Card Lifecycle",
    AssignedTeam.CARD_PAYMENTS: "Card Payments",
    AssignedTeam.TRANSFERS: "Transfers",
    AssignedTeam.TOPUP_CASH: "Top-Up & Cash",
    AssignedTeam.IDENTITY_SECURITY: "Identity & Security",
    AssignedTeam.CURRENCY_FEES: "Currency & Fees",
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

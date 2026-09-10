from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class InjectionStatus(str, Enum):
    YES = "yes"
    NO = "no"
    NOT_ABLE_TO_DETECT = "not_able_to_detect"


class InjectionJudgement(BaseModel):
    """Structured output of the `injection_check` node's guard LLM call."""

    is_injection: bool = Field(
        description="True if the input is a prompt injection attempt, False if it is a legitimate issue report."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="How confident the judge is in this decision (0.0 = uncertain, 1.0 = certain).",
    )
    reasoning: str = Field(description="One sentence explaining why this input was or was not flagged.")
    detected_pattern: Optional[str] = Field(
        default=None,
        description=(
            "Short label for the type of attack detected, e.g. 'role override', "
            "'instruction hijack'. Null if not an injection."
        ),
    )


class AssignedTeam(str, Enum):
    CARD_LIFECYCLE = "card_lifecycle"
    CARD_PAYMENTS = "card_payments"
    TRANSFERS = "transfers"
    TOPUP_CASH = "topup_cash"
    IDENTITY_SECURITY = "identity_security"
    CURRENCY_FEES = "currency_fees"
    OTHER = "other"


class IssueClassifierState(BaseModel):
    user_input: str
    redacted_input: Optional[str] = None
    injection_detected: Optional[InjectionStatus] = None
    injection_pattern: Optional[str] = None
    assigned_team: Optional[AssignedTeam] = None
    requires_human_review: Optional[bool] = None
    is_valid: Optional[bool] = None
    validation_error: Optional[str] = None
    evaluation: Optional[str] = None

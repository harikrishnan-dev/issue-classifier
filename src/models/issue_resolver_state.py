from enum import Enum
from typing import Optional

from pydantic import BaseModel


class InjectionStatus(str, Enum):
    YES = "yes"
    NO = "no"
    NOT_ABLE_TO_DETECT = "not_able_to_detect"


class AssignedTeam(str, Enum):
    CARGO_MODELS = "cargo_models"
    FREIGHT = "freight"
    FLOWS = "flows"
    COMPLIANCE = "compliance"
    INSIGHTS = "insights"
    UI = "ui"
    VOYAGE = "voyage"
    AIS_INGRESS = "ais_ingress"
    OTHER = "other"


class IssueResolverState(BaseModel):
    user_input: str
    redacted_input: Optional[str] = None
    injection_detected: Optional[InjectionStatus] = None
    injection_pattern: Optional[str] = None
    assigned_team: Optional[AssignedTeam] = None
    classification_confidence: Optional[float] = None
    requires_human_review: Optional[bool] = None
    is_valid: Optional[bool] = None
    validation_error: Optional[str] = None
    evaluation: Optional[str] = None

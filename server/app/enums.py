"""String enums replacing hardcoded status literals across the codebase."""

from enum import Enum


class PassFail(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class AdaptiveDecision(str, Enum):
    ADVANCE = "advance"
    STAY = "stay"
    DROP = "drop"
    ESCALATED = "escalated"


class PerformanceLevel(str, Enum):
    ADVANCED = "advanced"
    SATISFACTORY = "satisfactory"
    NEEDS_IMPROVEMENT = "needs_improvement"
    SUPPORT_NEEDED = "support_needed"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    ARCHIVED = "archived"


class SessionType(str, Enum):
    THERAPY = "therapy"
    BASELINE = "baseline"


class QueueItemStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED_TERMINAL = "failed_terminal"
    SKIPPED_DUE_TO_LOCK = "skipped_due_to_lock"

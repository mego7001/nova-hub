from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Set


SYSTEM_STATES: Set[str] = {
    "idle",
    "intake",
    "analysis",
    "awaiting_clarification",
    "awaiting_approval",
    "executing",
    "verifying",
    "blocked",
    "failed",
    "completed",
}


ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "idle": {"intake"},
    "intake": {"analysis"},
    "analysis": {"awaiting_clarification", "awaiting_approval", "executing", "blocked"},
    "awaiting_clarification": {"analysis"},
    "awaiting_approval": {"executing"},
    "executing": {"verifying", "failed", "blocked"},
    "verifying": {"completed", "failed", "blocked"},
    "blocked": set(),
    "failed": set(),
    "completed": set(),
}


@dataclass(frozen=True)
class TransitionEvidence:
    decision_ref: Optional[str] = None
    artifact_ref: Optional[str] = None
    verification_verdict: Optional[str] = None


class PolicyFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        current_state: str,
        attempted_state: str,
        reason: str,
    ) -> None:
        super().__init__(message)
        self.current_state = current_state
        self.attempted_state = attempted_state
        self.reason = reason


class SystemStateMachine:
    def __init__(self, initial_state: str = "idle") -> None:
        if initial_state not in SYSTEM_STATES:
            raise ValueError(f"Unknown system state: {initial_state}")
        self.state = initial_state

    def transition(self, next_state: str, evidence: Optional[TransitionEvidence] = None) -> str:
        if next_state not in SYSTEM_STATES:
            return self._block(next_state, "unknown_state")

        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if next_state not in allowed:
            return self._block(next_state, "illegal_transition")

        ev = evidence or TransitionEvidence()
        if self.state == "analysis" and next_state == "executing":
            if not ev.decision_ref:
                return self._block(next_state, "missing_decision_ref")
        if self.state == "executing" and next_state == "verifying":
            if not ev.artifact_ref:
                return self._block(next_state, "missing_artifact_ref")
        if self.state == "verifying" and next_state == "completed":
            if str(ev.verification_verdict or "").lower() != "pass":
                return self._block(next_state, "verification_not_passed")

        self.state = next_state
        return self.state

    def block(self, reason: str, attempted_state: str) -> None:
        self._block(attempted_state, reason)

    def _block(self, attempted_state: str, reason: str) -> str:
        prior = self.state
        self.state = "blocked"
        raise PolicyFailure(
            f"Policy failure: {reason} (from {prior} to {attempted_state})",
            current_state=prior,
            attempted_state=attempted_state,
            reason=reason,
        )

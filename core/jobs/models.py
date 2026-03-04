from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class JobArtifacts:
    last_diff_path: str = ""
    last_verify_report: str = ""
    last_plan_report: str = ""
    last_apply_report: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_diff_path": self.last_diff_path,
            "last_verify_report": self.last_verify_report,
            "last_plan_report": self.last_plan_report,
            "last_apply_report": self.last_apply_report,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "JobArtifacts":
        return JobArtifacts(
            last_diff_path=str(data.get("last_diff_path") or ""),
            last_verify_report=str(data.get("last_verify_report") or ""),
            last_plan_report=str(data.get("last_plan_report") or ""),
            last_apply_report=str(data.get("last_apply_report") or ""),
        )


@dataclass
class Job:
    job_id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    steps_total: int
    steps_done: int
    current_step_label: str
    last_safe_point_label: str
    last_safe_point_at: str
    pause_requested: bool
    preview_requested: bool
    last_error: Optional[str]
    waiting_reason: Optional[str] = None
    pending_diff_path: Optional[str] = None
    pending_suggestion_n: Optional[int] = None
    artifacts: JobArtifacts = field(default_factory=JobArtifacts)
    log_tail: List[str] = field(default_factory=list)
    recipe: str = ""
    recipe_options: Dict[str, Any] = field(default_factory=dict)
    next_step_index: int = 0
    cancel_requested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "project_id": self.project_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "steps_total": self.steps_total,
            "steps_done": self.steps_done,
            "current_step_label": self.current_step_label,
            "last_safe_point_label": self.last_safe_point_label,
            "last_safe_point_at": self.last_safe_point_at,
            "pause_requested": self.pause_requested,
            "preview_requested": self.preview_requested,
            "last_error": self.last_error,
            "waiting_reason": self.waiting_reason,
            "pending_diff_path": self.pending_diff_path,
            "pending_suggestion_n": self.pending_suggestion_n,
            "artifacts": self.artifacts.to_dict(),
            "log_tail": list(self.log_tail),
            "recipe": self.recipe,
            "recipe_options": dict(self.recipe_options),
            "next_step_index": self.next_step_index,
            "cancel_requested": self.cancel_requested,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Job":
        return Job(
            job_id=str(data.get("job_id") or ""),
            project_id=str(data.get("project_id") or ""),
            title=str(data.get("title") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            status=str(data.get("status") or "queued"),
            steps_total=int(data.get("steps_total") or 0),
            steps_done=int(data.get("steps_done") or 0),
            current_step_label=str(data.get("current_step_label") or ""),
            last_safe_point_label=str(data.get("last_safe_point_label") or ""),
            last_safe_point_at=str(data.get("last_safe_point_at") or ""),
            pause_requested=bool(data.get("pause_requested") or False),
            preview_requested=bool(data.get("preview_requested") or False),
            last_error=data.get("last_error"),
            waiting_reason=data.get("waiting_reason"),
            pending_diff_path=data.get("pending_diff_path"),
            pending_suggestion_n=data.get("pending_suggestion_n"),
            artifacts=JobArtifacts.from_dict(data.get("artifacts") or {}),
            log_tail=list(data.get("log_tail") or []),
            recipe=str(data.get("recipe") or ""),
            recipe_options=dict(data.get("recipe_options") or {}),
            next_step_index=int(data.get("next_step_index") or 0),
            cancel_requested=bool(data.get("cancel_requested") or False),
        )

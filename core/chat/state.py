from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChatState:
    session_id: str
    project_path: str = ""
    scanned: bool = False
    searched: bool = False
    planned: bool = False
    verified: bool = False
    last_diff_path: str = ""
    last_scan_paths: List[str] = field(default_factory=list)
    missing_requirements: List[str] = field(default_factory=list)
    last_recommendations: List[str] = field(default_factory=list)
    suggestions: List[Any] = field(default_factory=list)
    suggestion_status: Dict[str, Any] = field(default_factory=dict)
    last_reports: List[str] = field(default_factory=list)
    last_artifacts: Dict[str, List[str]] = field(default_factory=dict)
    awaiting_goal: Optional[str] = None
    awaiting_apply_confirm: bool = False
    pending_apply_diff_path: str = ""
    pending_apply_suggestion: Optional[int] = None
    system_state: str = ""

    # memory-only
    pending_secret_values: Dict[str, str] = field(default_factory=dict)
    session_secrets: List[str] = field(default_factory=list)

    def to_persisted(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "project_path": self.project_path,
            "last_scan_paths": self.last_scan_paths,
            "missing_requirements": self.missing_requirements,
            "last_recommendations": self.last_recommendations,
            "last_diff_path": self.last_diff_path,
            "suggestions": self.suggestions,
            "suggestion_status": self.suggestion_status,
            "system_state": self.system_state,
        }

    @staticmethod
    def from_dict(session_id: str, data: Dict[str, Any]) -> "ChatState":
        st = ChatState(session_id=session_id)
        st.project_path = data.get("project_path", "")
        st.last_scan_paths = data.get("last_scan_paths") or []
        st.missing_requirements = data.get("missing_requirements") or []
        st.last_recommendations = data.get("last_recommendations") or []
        st.last_diff_path = data.get("last_diff_path") or ""
        st.suggestions = data.get("suggestions") or []
        st.suggestion_status = data.get("suggestion_status") or {}
        st.system_state = data.get("system_state") or ""
        return st

    def to_status(self) -> Dict[str, Any]:
        return {
            "project_path": self.project_path,
            "scanned": self.scanned,
            "searched": self.searched,
            "planned": self.planned,
            "diff_ready": bool(self.last_diff_path),
            "verified": self.verified,
            "last_diff_path": self.last_diff_path,
            "last_reports": self.last_reports,
            "last_artifacts": self.last_artifacts,
            "suggestions": self.suggestions,
            "suggestion_status": self.suggestion_status,
            "pending_apply_diff_path": self.pending_apply_diff_path,
            "pending_apply_suggestion": self.pending_apply_suggestion,
            "system_state": self.system_state,
        }

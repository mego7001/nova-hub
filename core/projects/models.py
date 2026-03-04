from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProjectMeta:
    project_id: str
    name: str
    created_at: str
    source_hint: Optional[str] = None
    last_opened: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
            "source_hint": self.source_hint,
            "last_opened": self.last_opened,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ProjectMeta":
        return ProjectMeta(
            project_id=str(data.get("project_id") or ""),
            name=str(data.get("name") or ""),
            created_at=str(data.get("created_at") or ""),
            source_hint=data.get("source_hint"),
            last_opened=data.get("last_opened"),
        )


@dataclass
class ProjectPaths:
    project_root: str
    working: str
    preview: str
    docs: str
    extracted: str
    reports: str
    patches: str
    releases: str
    snapshots: str
    chat_path: str
    state_path: str
    meta_path: str
    index_path: str


@dataclass
class ProjectState:
    last_diff_path: str = ""
    suggestions: List[Any] = field(default_factory=list)
    last_reports: List[str] = field(default_factory=list)
    suggestion_status: Dict[str, Any] = field(default_factory=dict)
    security_gate: Dict[str, Any] = field(default_factory=dict)
    jarvis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_diff_path": self.last_diff_path,
            "suggestions": list(self.suggestions),
            "last_reports": list(self.last_reports),
            "suggestion_status": dict(self.suggestion_status),
            "security_gate": dict(self.security_gate or {}),
            "jarvis": dict(self.jarvis or {}),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ProjectState":
        return ProjectState(
            last_diff_path=str(data.get("last_diff_path") or ""),
            suggestions=list(data.get("suggestions") or []),
            last_reports=list(data.get("last_reports") or []),
            suggestion_status=dict(data.get("suggestion_status") or {}),
            security_gate=dict(data.get("security_gate") or {}),
            jarvis=dict(data.get("jarvis") or {}),
        )

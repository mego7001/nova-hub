import os
import re
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QObject, Signal, Slot
from ui.hud_qml.models import DictListModel

class CandidateManager(QObject):
    candidateChanged = Signal()
    applyProgress = Signal(float, str)
    verificationFinished = Signal(bool, str)

    def __init__(self, workspace_root: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._workspace_root = workspace_root
        
        self.diff_files_model = DictListModel(["path", "added", "removed"], parent=self)
        self.qa_findings_model = DictListModel(["severity", "code", "message", "context"], parent=self)
        self.qa_metrics_model = DictListModel(["section", "key", "value"], parent=self)

        self._pending_candidates: List[Dict[str, Any]] = []
        self._active_candidate_id = ""
        self._is_applying = False

    def get_active_candidate(self) -> Optional[Dict[str, Any]]:
        if not self._active_candidate_id:
            return None
        for c in self._pending_candidates:
            if str(c.get("id") or "") == self._active_candidate_id:
                return c
        return None

    def add_candidate(self, candidate: Dict[str, Any]):
        self._pending_candidates.append(candidate)
        self._active_candidate_id = str(candidate.get("id") or "")
        self.candidateChanged.emit()
        self._refresh_diff_model()

    def remove_candidate(self, candidate_id: str):
        self._pending_candidates = [c for c in self._pending_candidates if str(c.get("id") or "") != candidate_id]
        if self._active_candidate_id == candidate_id:
            self._active_candidate_id = ""
            if self._pending_candidates:
                self._active_candidate_id = str(self._pending_candidates[-1].get("id") or "")
        self.candidateChanged.emit()
        self._refresh_diff_model()

    def _refresh_diff_model(self):
        self.diff_files_model.clear()
        active = self.get_active_candidate()
        if not active:
            return
        diffs = active.get("files", [])
        rows = []
        for d in diffs:
            rows.append({
                "path": d.get("path", "unknown"),
                "added": d.get("added", 0),
                "removed": d.get("removed", 0)
            })
        self.diff_files_model.set_items(rows)

    def apply_candidate(self, project_path: str) -> bool:
        if not self.has_candidate:
            return False
        
        # logic for applying diffs to disk
        # This will eventually call into a core helper
        self._is_applying = True
        self.applyProgress.emit(0.1, "Starting apply...")
        
        # Simulating work for now, or calling existing logic
        # In a real refactor, we move the actual file I/O here or to a core service
        return True

    def verify_candidate(self, project_path: str):
        # logic for linting/testing
        self.applyProgress.emit(0.5, "Verifying changes...")
        # Emit verificationFinished when done
        pass

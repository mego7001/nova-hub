from __future__ import annotations
import json
import os
from typing import Any, Dict, List

from core.jobs.models import Job
from core.portable.paths import detect_base_dir, default_workspace_dir


class JobStorage:
    def __init__(self, workspace_root: str | None = None):
        base = detect_base_dir()
        self.workspace_root = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)

    def _jobs_dir(self, project_id: str) -> str:
        return os.path.join(self.workspace_root, "projects", project_id, "jobs")

    def _index_path(self, project_id: str) -> str:
        return os.path.join(self._jobs_dir(project_id), "jobs_index.json")

    def _job_path(self, project_id: str, job_id: str) -> str:
        return os.path.join(self._jobs_dir(project_id), f"{job_id}.json")

    def list_jobs(self, project_id: str) -> List[Dict[str, Any]]:
        index_path = self._index_path(project_id)
        if not os.path.exists(index_path):
            return []
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f) or []
            if isinstance(data, list):
                return data
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return []
        return []

    def load_job(self, project_id: str, job_id: str) -> Job:
        path = self._job_path(project_id, job_id)
        if not os.path.exists(path):
            raise FileNotFoundError("Job not found")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Job.from_dict(data or {})

    def save_job(self, job: Job) -> None:
        os.makedirs(self._jobs_dir(job.project_id), exist_ok=True)
        path = self._job_path(job.project_id, job.job_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(job.to_dict(), f, indent=2, ensure_ascii=True)
        self._update_index(job)

    def _update_index(self, job: Job) -> None:
        idx = self.list_jobs(job.project_id)
        summary = {
            "job_id": job.job_id,
            "title": job.title,
            "status": job.status,
            "updated_at": job.updated_at,
            "created_at": job.created_at,
            "steps_total": job.steps_total,
            "steps_done": job.steps_done,
            "current_step_label": job.current_step_label,
            "last_safe_point_label": job.last_safe_point_label,
            "last_safe_point_at": job.last_safe_point_at,
        }
        idx = [x for x in idx if x.get("job_id") != job.job_id]
        idx.insert(0, summary)
        with open(self._index_path(job.project_id), "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, ensure_ascii=True)

from __future__ import annotations
import os
import re
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from core.portable.paths import detect_base_dir, default_workspace_dir
from .models import ProjectMeta, ProjectPaths, ProjectState
from .storage import load_project_meta, save_project_meta, load_project_state, save_project_state, list_project_dirs
from core.jobs.storage import JobStorage

_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "outputs",
    "reports",
    "patches",
    "workspace",
}


class ProjectManager:
    def __init__(self, workspace_root: Optional[str] = None):
        base = detect_base_dir()
        self.workspace_root = workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base)
        self.projects_root = os.path.join(self.workspace_root, "projects")
        self.archived_root = os.path.join(self.workspace_root, "projects_archived")
        os.makedirs(self.projects_root, exist_ok=True)
        os.makedirs(self.archived_root, exist_ok=True)

    def add_project_from_folder(self, source_path: str) -> str:
        if not os.path.isdir(source_path):
            raise ValueError("Source folder does not exist")
        name = os.path.basename(os.path.abspath(source_path)) or "project"
        project_id = self._new_project_id(name)
        paths = self.get_project_paths(project_id)
        os.makedirs(paths.working, exist_ok=True)
        self._copy_tree(source_path, paths.working)
        meta = ProjectMeta(
            project_id=project_id,
            name=name,
            created_at=self._now(),
            source_hint=source_path,
            last_opened=self._now(),
        )
        save_project_meta(paths.meta_path, meta)
        save_project_state(paths.state_path, ProjectState())
        return project_id

    def add_project_from_zip(self, zip_path: str) -> str:
        if not os.path.isfile(zip_path):
            raise ValueError("Zip file does not exist")
        name = os.path.splitext(os.path.basename(zip_path))[0] or "project"
        project_id = self._new_project_id(name)
        paths = self.get_project_paths(project_id)
        os.makedirs(paths.working, exist_ok=True)
        self._safe_extract_zip(zip_path, paths.working)
        meta = ProjectMeta(
            project_id=project_id,
            name=name,
            created_at=self._now(),
            source_hint=zip_path,
            last_opened=self._now(),
        )
        save_project_meta(paths.meta_path, meta)
        save_project_state(paths.state_path, ProjectState())
        return project_id

    def list_projects(self, include_archived: bool = False) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        roots = [self.projects_root]
        if include_archived:
            roots.append(self.archived_root)
        for root in roots:
            for pdir in list_project_dirs(root):
                meta_path = os.path.join(pdir, "project.json")
                meta = load_project_meta(meta_path)
                if not meta:
                    continue
                state_path = os.path.join(pdir, "state.json")
                state = load_project_state(state_path)
                status = []
                if state.last_diff_path:
                    status.append("diff_ready")
                if any("verify_smoke" in r for r in state.last_reports):
                    status.append("verified")
                if state.last_reports:
                    status.append(f"reports:{len(state.last_reports)}")
                status_summary = ", ".join(status) if status else "idle"
                out.append(
                    {
                        "id": meta.project_id,
                        "name": meta.name,
                        "created_at": meta.created_at,
                        "last_opened": meta.last_opened or "",
                        "status_summary": status_summary,
                        "archived": root == self.archived_root,
                    }
                )
        return out

    def open_project(self, project_id: str) -> Dict[str, Optional[str]]:
        paths = self.get_project_paths(project_id)
        meta = load_project_meta(paths.meta_path)
        state = load_project_state(paths.state_path)
        transcript = ""
        if os.path.exists(paths.chat_path):
            try:
                with open(paths.chat_path, "r", encoding="utf-8") as f:
                    transcript = f.read()
            except (OSError, UnicodeDecodeError):
                transcript = ""
        if meta:
            meta.last_opened = self._now()
            save_project_meta(paths.meta_path, meta)
        return {
            "project_id": project_id,
            "name": meta.name if meta else project_id,
            "working": paths.working,
            "state_json": paths.state_path,
            "chat_md": paths.chat_path,
            "docs": paths.docs,
            "extracted": paths.extracted,
            "index_path": paths.index_path,
            "state": state.to_dict(),
            "transcript": transcript,
        }

    def rename_project(self, project_id: str, new_name: str) -> None:
        paths = self.get_project_paths(project_id)
        meta = load_project_meta(paths.meta_path)
        if not meta:
            raise ValueError("Project not found")
        meta.name = new_name.strip() or meta.name
        meta.last_opened = self._now()
        save_project_meta(paths.meta_path, meta)

    def archive_project(self, project_id: str) -> str:
        if self._has_active_jobs(project_id):
            raise RuntimeError("Stop job first")
        src = self._resolve_project_root(project_id)
        if not os.path.isdir(src):
            raise FileNotFoundError("Project not found")
        dst = os.path.join(self.archived_root, os.path.basename(src))
        if os.path.exists(dst):
            raise RuntimeError("Archive target already exists")
        shutil.move(src, dst)
        return dst

    def delete_project(self, project_id: str, confirm_token: str) -> None:
        if confirm_token != "DELETE":
            raise ValueError("Confirmation token required")
        if self._has_active_jobs(project_id):
            raise RuntimeError("Stop job first")
        src = self._resolve_project_root(project_id)
        if not os.path.isdir(src):
            raise FileNotFoundError("Project not found")
        shutil.rmtree(src)

    def _has_active_jobs(self, project_id: str) -> bool:
        storage = JobStorage(self.workspace_root)
        jobs = storage.list_jobs(project_id)
        for j in jobs:
            if j.get("status") not in ("completed", "failed", "cancelled"):
                return True
        return False

    def clear_project_files(self, project_id: str) -> None:
        if self._has_active_jobs(project_id):
            raise RuntimeError("Stop job first")
        paths = self.get_project_paths(project_id)
        targets = [
            paths.working,
            paths.preview,
            paths.docs,
            paths.extracted,
            paths.reports,
            paths.patches,
            paths.releases,
            os.path.join(paths.project_root, "run_logs"),
        ]
        for p in targets:
            if os.path.isdir(p):
                shutil.rmtree(p)
            os.makedirs(p, exist_ok=True)
        if os.path.exists(paths.index_path):
            try:
                os.remove(paths.index_path)
            except OSError:
                pass

    def restore_project_from_snapshot(self, project_id: str, snapshot_path: str) -> None:
        if self._has_active_jobs(project_id):
            raise RuntimeError("Stop job first")
        paths = self.get_project_paths(project_id)
        snap_root = paths.snapshots
        abs_snap = os.path.abspath(snapshot_path)
        if not abs_snap.startswith(os.path.abspath(snap_root) + os.sep):
            raise ValueError("Snapshot must be under project snapshots folder")
        if not os.path.isfile(abs_snap):
            raise FileNotFoundError("Snapshot not found")
        if not abs_snap.lower().endswith(".zip"):
            raise ValueError("Snapshot must be a .zip file")
        # clear working before restore
        if os.path.isdir(paths.working):
            shutil.rmtree(paths.working)
        os.makedirs(paths.working, exist_ok=True)
        self._safe_extract_zip(abs_snap, paths.working)

    def get_project_paths(self, project_id: str) -> ProjectPaths:
        root = self._resolve_project_root(project_id)
        working = os.path.join(root, "working")
        preview = os.path.join(root, "preview")
        docs = os.path.join(root, "docs")
        extracted = os.path.join(root, "extracted")
        reports = os.path.join(root, "reports")
        patches = os.path.join(root, "patches")
        releases = os.path.join(root, "releases")
        snapshots = os.path.join(root, "snapshots")
        chat_path = os.path.join(root, "chat.md")
        state_path = os.path.join(root, "state.json")
        meta_path = os.path.join(root, "project.json")
        index_path = os.path.join(root, "index.json")
        for p in [root, working, preview, docs, extracted, reports, patches, releases, snapshots]:
            os.makedirs(p, exist_ok=True)
        return ProjectPaths(
            project_root=root,
            working=working,
            preview=preview,
            docs=docs,
            extracted=extracted,
            reports=reports,
            patches=patches,
            releases=releases,
            snapshots=snapshots,
            chat_path=chat_path,
            state_path=state_path,
            meta_path=meta_path,
            index_path=index_path,
        )

    def load_state(self, project_id: str) -> ProjectState:
        paths = self.get_project_paths(project_id)
        return load_project_state(paths.state_path)

    def save_state(self, project_id: str, state: ProjectState) -> None:
        paths = self.get_project_paths(project_id)
        save_project_state(paths.state_path, state)

    def update_last_opened(self, project_id: str) -> None:
        paths = self.get_project_paths(project_id)
        meta = load_project_meta(paths.meta_path)
        if not meta:
            return
        meta.last_opened = self._now()
        save_project_meta(paths.meta_path, meta)

    def build_preview(self, project_id: str) -> str:
        paths = self.get_project_paths(project_id)
        if os.path.isdir(paths.preview):
            shutil.rmtree(paths.preview)
        os.makedirs(paths.preview, exist_ok=True)
        self._copy_tree(paths.working, paths.preview)
        return paths.preview

    def _copy_tree(self, src: str, dst: str) -> None:
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            if rel == ".":
                rel = ""
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            target_dir = os.path.join(dst, rel)
            os.makedirs(target_dir, exist_ok=True)
            for name in files:
                if name in (".DS_Store",):
                    continue
                if name.endswith(".pyc"):
                    continue
                src_path = os.path.join(root, name)
                dst_path = os.path.join(target_dir, name)
                shutil.copy2(src_path, dst_path)

    def _safe_extract_zip(self, zip_path: str, dest: str) -> None:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                target = os.path.abspath(os.path.join(dest, member))
                if not target.startswith(os.path.abspath(dest) + os.sep):
                    raise ValueError("Unsafe path in zip file")
            zf.extractall(dest)

    def _new_project_id(self, name: str) -> str:
        base = self._sanitize_name(name)
        suffix = uuid.uuid4().hex[:8]
        return f"{base}-{suffix}"

    def _sanitize_name(self, name: str) -> str:
        n = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
        return n.strip("-") or "project"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _resolve_project_root(self, project_id: str) -> str:
        pid = str(project_id or "").strip()
        if not pid:
            raise ValueError("Project id is required")
        if Path(pid).is_absolute():
            raise ValueError("Project id must be relative")

        projects_root = Path(self.projects_root).resolve(strict=False)
        project_root = (projects_root / pid).resolve(strict=False)
        if project_root == projects_root:
            raise ValueError("Project id must resolve inside projects root")
        try:
            project_root.relative_to(projects_root)
        except ValueError as e:
            raise ValueError("Project id escapes projects root") from e
        return str(project_root)


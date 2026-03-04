from __future__ import annotations
import os, subprocess
from typing import Any, Dict, Optional
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration

def _run_git(repo: str, args: list[str]) -> str:
    repo = os.path.abspath(repo)
    if not os.path.isdir(repo):
        raise FileNotFoundError(f"Repo path not found: {repo}")
    cmd = ["git","-C",repo,*args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as e:
        raise RuntimeError("git executable not found on PATH") from e
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    if p.returncode != 0:
        raise RuntimeError(f"git failed (code {p.returncode}): {' '.join(cmd)}\n{out}")
    return out

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    repo = str(config.get("repo_path") or ".")
    allow_commit = bool(config.get("allow_commit", False))

    def status(repo_path: Optional[str]=None)->Dict[str,Any]:
        r = repo_path or repo
        return {"repo": os.path.abspath(r), "status": _run_git(r, ["status","--porcelain=v1","-b"])}

    def diff(repo_path: Optional[str]=None, args: Optional[list[str]]=None)->Dict[str,Any]:
        r = repo_path or repo
        return {"repo": os.path.abspath(r), "diff": _run_git(r, ["diff", *(args or [])])}

    def commit(message: str, repo_path: Optional[str]=None, all: bool=False)->Dict[str,Any]:
        if not allow_commit:
            raise PermissionError("git.commit disabled by config (set allow_commit=true).")
        r = repo_path or repo
        if not message.strip():
            raise ValueError("Commit message required")
        a = ["commit","-m",message]
        if all: a.insert(1,"-a")
        return {"repo": os.path.abspath(r), "result": _run_git(r, a)}

    registry.register_tool(ToolRegistration("git.status", manifest.id, "git", "git_status", status, "Git status", os.path.abspath(repo)))
    registry.register_tool(ToolRegistration("git.diff", manifest.id, "git", "git_diff", diff, "Git diff", os.path.abspath(repo)))
    registry.register_tool(ToolRegistration("git.commit", manifest.id, "git", "git_commit", commit, "Git commit (approval + allow_commit=true)", os.path.abspath(repo)))

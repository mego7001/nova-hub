from __future__ import annotations
import fnmatch
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration

_DEFAULT_EXCLUDES = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "outputs",
    "logs",
    "reports",
    "patches",
]

_LANG_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c_cpp_header",
    ".hpp": "c_cpp_header",
    ".hh": "c_cpp_header",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".m": "objective_c",
    ".mm": "objective_cpp",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".md": "markdown",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".sql": "sql",
    ".sh": "shell",
    ".ps1": "powershell",
}

_DEP_MANIFESTS = {"requirements.txt", "pyproject.toml", "package.json"}

_ENTRYPOINT_NAMES = {"main.py", "app.py", "cli.py", "__main__.py"}


def _norm_path(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/")


def _matches_any(path: str, patterns: List[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def _is_excluded(rel_path: str, excludes: List[str]) -> bool:
    rel_path = _norm_path(rel_path).lstrip("./")
    parts = [p for p in rel_path.split("/") if p]

    for pat in excludes:
        if not pat:
            continue
        pat_norm = _norm_path(pat).strip("/")
        if "/" in pat_norm or "*" in pat_norm or "?" in pat_norm:
            if fnmatch.fnmatch(rel_path, pat_norm):
                return True
        else:
            if pat_norm in parts:
                return True
    return False


def _guess_language(path: str) -> Optional[str]:
    _, ext = os.path.splitext(path.lower())
    return _LANG_BY_EXT.get(ext)


def _is_binary_sample(path: str, max_probe: int = 4096) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_probe)
        return b"\x00" in chunk
    except OSError:
        return False


def _count_loc(path: str, max_bytes: int) -> Tuple[int, bool]:
    try:
        with open(path, "rb") as f:
            data = f.read(max_bytes)
        if b"\x00" in data:
            return 0, True
        return data.count(b"\n"), False
    except OSError:
        return 0, False


def _write_report_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def _write_report_md(path: str, payload: Dict[str, Any]) -> None:
    lines = []
    lines.append("# Project Scan Report")
    lines.append("")
    lines.append(f"Timestamp: {payload.get('timestamp')}")
    lines.append(f"Root: {payload.get('root_path')}")
    lines.append("")

    stats = payload.get("stats") or {}
    lines.append("## Stats")
    lines.append(f"- Files scanned: {stats.get('file_count', 0)}")
    lines.append(f"- Total bytes: {stats.get('total_bytes', 0)}")
    lines.append(f"- LOC estimate: {stats.get('loc_estimate', 0)}")
    lines.append(f"- Binary files: {stats.get('binary_files', 0)}")
    lines.append("")

    lines.append("## Languages")
    langs = payload.get("languages") or {}
    if not langs:
        lines.append("- (none)")
    else:
        for k in sorted(langs.keys()):
            v = langs[k]
            lines.append(f"- {k}: files={v.get('files', 0)}, loc={v.get('loc', 0)}")
    lines.append("")

    lines.append("## Dependency Manifests")
    deps = payload.get("dependency_manifests") or []
    if not deps:
        lines.append("- (none)")
    else:
        for p in deps:
            lines.append(f"- {p}")
    lines.append("")

    lines.append("## Likely Entrypoints")
    eps = payload.get("entrypoints") or []
    if not eps:
        lines.append("- (none)")
    else:
        for p in eps:
            lines.append(f"- {p}")
    lines.append("")

    lines.append("## Largest Files (Top 20)")
    largest = payload.get("largest_files") or []
    if not largest:
        lines.append("- (none)")
    else:
        for item in largest:
            lines.append(f"- {item.get('path')} ({item.get('bytes')} bytes)")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    default_excludes = list(config.get("default_exclude_globs") or _DEFAULT_EXCLUDES)
    max_file_bytes = int(config.get("max_file_bytes") or 200000)

    def scan_repo(
        root_path: str = ".",
        include_globs: Optional[List[str]] = None,
        exclude_globs: Optional[List[str]] = None,
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        root = os.path.abspath(root_path)
        includes = [str(x) for x in (include_globs or []) if str(x).strip()]
        excludes = [str(x) for x in (exclude_globs or default_excludes) if str(x).strip()]

        file_count = 0
        total_bytes = 0
        loc_estimate = 0
        binary_files = 0
        languages: Dict[str, Dict[str, int]] = {}
        dependency_manifests: List[str] = []
        entrypoints: List[str] = []
        largest_files: List[Dict[str, Any]] = []

        if not os.path.isdir(root):
            raise FileNotFoundError(f"Root path not found: {root}")

        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir == ".":
                rel_dir = ""
            rel_dir_norm = _norm_path(rel_dir)

            # prune excluded directories
            keep_dirs = []
            for d in dirnames:
                rel_d = _norm_path(os.path.join(rel_dir_norm, d)) if rel_dir_norm else d
                if _is_excluded(rel_d, excludes):
                    continue
                keep_dirs.append(d)
            dirnames[:] = keep_dirs

            for name in filenames:
                rel_file = _norm_path(os.path.join(rel_dir_norm, name)) if rel_dir_norm else name
                if _is_excluded(rel_file, excludes):
                    continue
                if includes and not _matches_any(rel_file, includes):
                    continue

                abs_path = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(abs_path)
                except OSError:
                    size = 0

                file_count += 1
                total_bytes += int(size or 0)

                if name in _DEP_MANIFESTS or fnmatch.fnmatch(name, "*.csproj"):
                    dependency_manifests.append(rel_file)

                if name in _ENTRYPOINT_NAMES or fnmatch.fnmatch(name, "run_*.py"):
                    entrypoints.append(rel_file)

                lang = _guess_language(name)
                if lang:
                    languages.setdefault(lang, {"files": 0, "loc": 0})
                    languages[lang]["files"] += 1

                loc, is_bin = _count_loc(abs_path, max_file_bytes)
                if is_bin:
                    binary_files += 1
                else:
                    loc_estimate += loc
                    if lang:
                        languages[lang]["loc"] += loc

                largest_files.append({"path": rel_file, "bytes": int(size or 0)})

        largest_files = sorted(largest_files, key=lambda x: x.get("bytes", 0), reverse=True)[:20]
        dependency_manifests = sorted(set(dependency_manifests))
        entrypoints = sorted(set(entrypoints))

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "root_path": root,
            "config": {
                "default_exclude_globs": default_excludes,
                "max_file_bytes": max_file_bytes,
            },
            "applied": {
                "include_globs": includes,
                "exclude_globs": excludes,
            },
            "stats": {
                "file_count": file_count,
                "total_bytes": total_bytes,
                "loc_estimate": loc_estimate,
                "binary_files": binary_files,
            },
            "languages": languages,
            "dependency_manifests": dependency_manifests,
            "entrypoints": entrypoints,
            "largest_files": largest_files,
        }

        if write_reports:
            reports_dir = os.path.join(root, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            json_path = os.path.join(reports_dir, "project_scan.json")
            md_path = os.path.join(reports_dir, "project_scan.md")
            _write_report_json(json_path, payload)
            _write_report_md(md_path, payload)
            payload["report_paths"] = [json_path, md_path]
            payload["artifact_ref"] = json_path

        return payload

    registry.register_tool(
        ToolRegistration(
            tool_id="project.scan_repo",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="project_scan",
            handler=scan_repo,
            description="Scan repository tree and write reports",
            default_target=".",
        )
    )


from __future__ import annotations
import fnmatch
import json
import os
import re
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

_RISKY_PATTERNS = [
    (r"\beval\s*\(", "risky_eval"),
    (r"\bexec\s*\(", "risky_exec"),
    (r"\bos\.system\s*\(", "risky_os_system"),
    (r"\bsubprocess\.(Popen|call|run)\s*\(", "risky_subprocess"),
    (r"\bsubprocess\.run\s*\(.*shell\s*=\s*True", "risky_shell_true"),
    (r"\bpickle\.load\s*\(", "risky_pickle_load"),
    (r"\byaml\.load\s*\(", "risky_yaml_load"),
]


def _abs_path(path: str) -> str:
    if not path:
        raise ValueError("path is required")
    return os.path.abspath(path)


def _is_binary_sample(path: str, max_probe: int = 4096) -> bool:
    with open(path, "rb") as f:
        chunk = f.read(max_probe)
    return b"\x00" in chunk


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


def _count_loc(path: str, max_bytes: int = 200000) -> Tuple[int, bool]:
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
    lines.append("# Repository Search Report")
    lines.append("")
    lines.append(f"Timestamp: {payload.get('timestamp')}")
    lines.append(f"Root: {payload.get('root_path')}")
    lines.append("")

    lines.append(f"Total matches: {payload.get('total_matches', 0)}")
    lines.append("")

    lines.append("## Top Files by Hits")
    top = payload.get("hotspots", {}).get("files_with_most_hits") or []
    if not top:
        lines.append("- (none)")
    else:
        for item in top:
            lines.append(f"- {item.get('path')} ({item.get('hits')} hits)")
    lines.append("")

    lines.append("## Recommended Focus Areas")
    rec = []
    suspicious = payload.get("hotspots", {}).get("suspicious_files") or []
    if suspicious:
        rec.append("Review files with unusually high hit counts or size.")
    cfg = payload.get("hotspots", {}).get("config_hotspots") or []
    if cfg:
        rec.append("Audit configuration files for secrets and risky defaults.")
    if not rec:
        rec.append("No obvious hotspots detected; review task markers first.")
    for r in rec:
        lines.append(f"- {r}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def list_dir(path: str = ".") -> Dict[str, Any]:
        p = _abs_path(path)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Path not found: {p}")
        if not os.path.isdir(p):
            raise NotADirectoryError(f"Not a directory: {p}")

        entries: List[Dict[str, Any]] = []
        for name in os.listdir(p):
            full = os.path.join(p, name)
            try:
                is_dir = os.path.isdir(full)
                size = os.path.getsize(full) if not is_dir else None
            except OSError:
                is_dir = False
                size = None
            entries.append({"name": name, "path": full, "is_dir": is_dir, "size": size})

        entries.sort(key=lambda x: (not x.get("is_dir", False), x.get("name", "")))
        return {"path": p, "count": len(entries), "entries": entries}

    def read_text(path: str, max_bytes: int = 200000) -> Dict[str, Any]:
        p = _abs_path(path)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Path not found: {p}")
        if os.path.isdir(p):
            raise IsADirectoryError(f"Path is a directory: {p}")

        if _is_binary_sample(p):
            raise ValueError("Binary file detected; refusing to read as text")

        with open(p, "rb") as f:
            data = f.read(int(max_bytes))
            truncated = f.read(1) != b""

        try:
            text = data.decode("utf-8")
            encoding = "utf-8"
        except UnicodeDecodeError:
            text = data.decode("latin-1", errors="replace")
            encoding = "latin-1"

        return {
            "path": p,
            "encoding": encoding,
            "bytes_read": len(data),
            "truncated": truncated,
            "text": text,
        }

    def repo_search(
        root_path: str = ".",
        query: Optional[str] = None,
        regex: bool = False,
        extensions: Optional[List[str]] = None,
        max_matches: int = 500,
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        root = _abs_path(root_path)
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Root path not found: {root}")

        excludes = list(_DEFAULT_EXCLUDES)
        exts = [e.lower().lstrip(".") for e in (extensions or []) if str(e).strip()]
        max_matches = int(max_matches) if max_matches is not None else 500

        auto_terms = ["TO" + "DO", "FIX" + "ME", "HA" + "CK", "X" * 3]
        hardcoded_re = re.compile(r"([A-Za-z]:\\\\|/)([^\\s\"']+)")
        comment_code_re = re.compile(r"^[\\s#//;]+.*[{}();]|\\b(class|def|function|return|if|for|while)\\b")
        risky_res = [(re.compile(pat, re.IGNORECASE), tag) for pat, tag in _RISKY_PATTERNS]

        matches: List[Dict[str, Any]] = []
        file_hits: Dict[str, int] = {}
        largest_files: List[Dict[str, Any]] = []
        suspicious_files: List[Dict[str, Any]] = []
        config_hotspots: List[str] = []

        for dirpath, dirnames, filenames in os.walk(root):
            rel_dir = os.path.relpath(dirpath, root)
            if rel_dir == ".":
                rel_dir = ""
            rel_dir_norm = _norm_path(rel_dir)

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

                if exts:
                    ext = os.path.splitext(name)[1].lower().lstrip(".")
                    if ext not in exts:
                        continue

                abs_path = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(abs_path)
                except OSError:
                    size = 0
                largest_files.append({"path": rel_file, "bytes": int(size or 0)})

                lower_name = name.lower()
                if lower_name in {"requirements.txt", "pyproject.toml", "package.json"}:
                    config_hotspots.append(rel_file)
                if fnmatch.fnmatch(lower_name, "*.yml") or fnmatch.fnmatch(lower_name, "*.yaml"):
                    config_hotspots.append(rel_file)
                if fnmatch.fnmatch(lower_name, "*.json") and "package-lock" not in lower_name:
                    config_hotspots.append(rel_file)
                if lower_name in {".env", ".env.example", "settings.py", "config.py"}:
                    config_hotspots.append(rel_file)

                if _is_binary_sample(abs_path):
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        for i, line in enumerate(f, 1):
                            line_stripped = line.rstrip("\n")
                            if query:
                                if regex:
                                    if not re.search(query, line_stripped):
                                        continue
                                    tag = "query_regex"
                                else:
                                    if query not in line_stripped:
                                        continue
                                    tag = "query"
                                matches.append(
                                    {
                                        "type": tag,
                                        "path": rel_file,
                                        "line": i,
                                        "excerpt": line_stripped.strip(),
                                    }
                                )
                                file_hits[rel_file] = file_hits.get(rel_file, 0) + 1
                            else:
                                hit = False
                                for term in auto_terms:
                                    if term in line_stripped:
                                        matches.append(
                                            {
                                                "type": "todo",
                                                "path": rel_file,
                                                "line": i,
                                                "excerpt": line_stripped.strip(),
                                            }
                                        )
                                        file_hits[rel_file] = file_hits.get(rel_file, 0) + 1
                                        hit = True
                                        break
                                if hit:
                                    if len(matches) >= max_matches:
                                        break
                                    continue

                                if hardcoded_re.search(line_stripped):
                                    matches.append(
                                        {
                                            "type": "hardcoded_path",
                                            "path": rel_file,
                                            "line": i,
                                            "excerpt": line_stripped.strip(),
                                        }
                                    )
                                    file_hits[rel_file] = file_hits.get(rel_file, 0) + 1
                                elif comment_code_re.search(line_stripped) and line_stripped.lstrip().startswith(("#", "//", ";")):
                                    matches.append(
                                        {
                                            "type": "commented_code",
                                            "path": rel_file,
                                            "line": i,
                                            "excerpt": line_stripped.strip(),
                                        }
                                    )
                                    file_hits[rel_file] = file_hits.get(rel_file, 0) + 1
                                else:
                                    for reg, tag in risky_res:
                                        if reg.search(line_stripped):
                                            matches.append(
                                                {
                                                    "type": tag,
                                                    "path": rel_file,
                                                    "line": i,
                                                    "excerpt": line_stripped.strip(),
                                                }
                                            )
                                            file_hits[rel_file] = file_hits.get(rel_file, 0) + 1
                                            break

                            if len(matches) >= max_matches:
                                break
                    if len(matches) >= max_matches:
                        break
                except OSError:
                    continue

            if len(matches) >= max_matches:
                break

        largest_files = sorted(largest_files, key=lambda x: x.get("bytes", 0), reverse=True)[:20]

        for path, hits in sorted(file_hits.items(), key=lambda x: x[1], reverse=True)[:10]:
            loc, is_bin = _count_loc(os.path.join(root, path))
            suspicious = hits >= 10 or (not is_bin and loc >= 1200)
            if suspicious:
                suspicious_files.append({"path": path, "hits": hits, "loc_estimate": loc})

        files_with_most_hits = [
            {"path": p, "hits": h}
            for p, h in sorted(file_hits.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "root_path": root,
            "query": query,
            "regex": bool(regex),
            "extensions": exts,
            "max_matches": max_matches,
            "total_matches": len(matches),
            "matches": matches,
            "hotspots": {
                "files_with_most_hits": files_with_most_hits,
                "largest_files": largest_files,
                "suspicious_files": suspicious_files,
                "config_hotspots": sorted(set(config_hotspots)),
            },
        }

        if write_reports:
            reports_dir = os.path.join(root, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            json_path = os.path.join(reports_dir, "repo_search.json")
            md_path = os.path.join(reports_dir, "repo_search.md")
            _write_report_json(json_path, payload)
            _write_report_md(md_path, payload)
            payload["report_paths"] = [json_path, md_path]
            payload["artifact_ref"] = json_path

        return payload

    registry.register_tool(
        ToolRegistration(
            tool_id="fs.list_dir",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="fs_list_dir",
            handler=list_dir,
            description="List directory entries",
            default_target=".",
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="fs.read_text",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="fs_read_text",
            handler=read_text,
            description="Read a text file safely (binary guarded)",
            default_target=None,
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="repo.search",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="repo_search",
            handler=repo_search,
            description="Search repository for task markers, risks, and hotspots",
            default_target=".",
        )
    )

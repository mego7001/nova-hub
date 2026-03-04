from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration


class PatchApplyError(Exception):
    pass


def _abs_path(path: str) -> str:
    if not path:
        raise ValueError("path is required")
    return os.path.abspath(path)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def _safe_relpath(path: str) -> str:
    p = path.replace("\\", "/")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    if p.startswith("/") or re.match(r"^[A-Za-z]:/", p):
        raise PatchApplyError(f"Absolute path not allowed: {path}")
    if ".." in p.split("/"):
        raise PatchApplyError(f"Path traversal not allowed: {path}")
    return p


def _resolve_under_root(root: str, relpath: str) -> str:
    abs_path = os.path.abspath(os.path.join(root, relpath))
    root_abs = os.path.abspath(root)
    if not abs_path.startswith(root_abs + os.sep) and abs_path != root_abs:
        raise PatchApplyError(f"Path escapes target_root: {relpath}")
    return abs_path


def _parse_unified_diff(diff_text: str) -> List[Dict[str, Any]]:
    patches: List[Dict[str, Any]] = []
    lines = diff_text.splitlines()
    i = 0
    current: Optional[Dict[str, Any]] = None

    hunk_header_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    while i < len(lines):
        line = lines[i]
        if line.startswith("--- "):
            old_path = line[4:].strip()
            i += 1
            if i >= len(lines) or not lines[i].startswith("+++ "):
                raise PatchApplyError("Invalid diff: missing +++ after ---")
            new_path = lines[i][4:].strip()
            current = {
                "old_path": old_path,
                "new_path": new_path,
                "hunks": [],
            }
            patches.append(current)
            i += 1
            continue

        if line.startswith("@@ "):
            if current is None:
                raise PatchApplyError("Hunk without file header")
            m = hunk_header_re.match(line)
            if not m:
                raise PatchApplyError(f"Invalid hunk header: {line}")
            hunk = {
                "header": line,
                "old_start": int(m.group(1)),
                "old_count": int(m.group(2) or "1"),
                "new_start": int(m.group(3)),
                "new_count": int(m.group(4) or "1"),
                "lines": [],
            }
            i += 1
            while i < len(lines):
                l = lines[i]
                if l.startswith("@@ ") or l.startswith("--- "):
                    break
                if not l.startswith((" ", "+", "-", "\\")):
                    raise PatchApplyError(f"Invalid hunk line: {l}")
                if l.startswith("\\"):
                    i += 1
                    continue
                hunk["lines"].append(l)
                i += 1
            current["hunks"].append(hunk)
            continue

        i += 1

    if not patches:
        raise PatchApplyError("No file patches found in diff")
    if sum(len(p.get("hunks") or []) for p in patches) == 0:
        raise PatchApplyError("No hunks parsed from diff")
    for p in patches:
        if not p.get("hunks"):
            label = p.get("new_path") or p.get("old_path") or "(unknown)"
            raise PatchApplyError(f"No hunks parsed for file: {label}")

    return patches


def _apply_hunks(original: str, hunks: List[Dict[str, Any]], file_label: str) -> str:
    orig_lines = original.splitlines()
    out_lines = orig_lines[:]
    offset = 0

    for h in hunks:
        old_start = h["old_start"] - 1
        idx = old_start + offset

        scan_idx = max(0, min(len(out_lines), idx))

        def try_apply(at: int) -> Optional[List[str]]:
            before = out_lines[:at]
            cur = out_lines[at:]
            result = []
            j = 0
            for hl in h["lines"]:
                tag = hl[:1]
                text = hl[1:]
                if tag == " ":
                    if j >= len(cur) or cur[j] != text:
                        return None
                    result.append(cur[j])
                    j += 1
                elif tag == "-":
                    if j >= len(cur) or cur[j] != text:
                        return None
                    j += 1
                elif tag == "+":
                    result.append(text)
                else:
                    return None
            after = cur[j:]
            return before + result + after

        applied = False
        for delta in range(0, 4):
            for sign in (1, -1):
                cand = scan_idx + (delta * sign)
                if cand < 0 or cand > len(out_lines):
                    continue
                res = try_apply(cand)
                if res is not None:
                    out_lines = res
                    offset = len(out_lines) - len(orig_lines)
                    applied = True
                    break
            if applied:
                break

        if not applied:
            context = [l[1:] for l in h["lines"] if l.startswith(" ")][:3]
            raise PatchApplyError(
                f"Context mismatch in {file_label} at {h['header']} (context: {context})"
            )

    return "\n".join(out_lines) + ("\n" if original.endswith("\n") else "")


def create_patch_apply_handler(config: Dict[str, Any]):
    default_backup_suffix = str(config.get("default_backup_suffix") or ".bak")
    default_reports_dir = str(config.get("default_reports_dir") or "reports")

    def patch_apply(
        diff_path: str,
        target_root: str = ".",
        create_backup: bool = True,
        backup_suffix: str = ".bak",
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        if not diff_path or not str(diff_path).strip():
            raise ValueError("diff_path is required")

        root = _abs_path(target_root)
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Target root not found: {root}")

        diff_abs = _abs_path(diff_path)
        if not os.path.exists(diff_abs):
            raise FileNotFoundError(f"Diff not found: {diff_abs}")

        report_dir = os.path.join(root, default_reports_dir)
        os.makedirs(report_dir, exist_ok=True)

        diff_text = _read_text(diff_abs)
        patches = _parse_unified_diff(diff_text)

        results: List[Dict[str, Any]] = []
        success = 0
        failed = 0

        for p in patches:
            old_path = p["old_path"]
            new_path = p["new_path"]
            target_rel: Optional[str] = None

            if old_path == "/dev/null":
                target_rel = _safe_relpath(new_path)
            elif new_path == "/dev/null":
                target_rel = _safe_relpath(old_path)
            else:
                target_rel = _safe_relpath(new_path)

            try:
                abs_path = _resolve_under_root(root, target_rel)

                exists = os.path.exists(abs_path)
                original = _read_text(abs_path) if exists else ""
                new_content = _apply_hunks(original, p["hunks"], target_rel)
                if new_content == original:
                    raise PatchApplyError(f"No content changes applied to {target_rel}")

                backup_path = None
                if create_backup and exists:
                    backup_path = abs_path + (backup_suffix or default_backup_suffix)
                    _write_text(backup_path, original)

                _write_text(abs_path, new_content)

                results.append({
                    "path": target_rel,
                    "status": "success",
                    "backup_path": backup_path,
                })
                success += 1
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                failed += 1
                backup_path = None
                try:
                    abs_path = _resolve_under_root(root, target_rel) if target_rel else None
                    if abs_path and os.path.exists(abs_path + (backup_suffix or default_backup_suffix)):
                        backup_path = abs_path + (backup_suffix or default_backup_suffix)
                        _write_text(abs_path, _read_text(backup_path))
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
                results.append({
                    "path": target_rel or "(unknown)",
                    "status": "failed",
                    "backup_path": backup_path,
                    "message": str(e),
                })

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "diff_path": diff_abs,
            "target_root": root,
            "create_backup": bool(create_backup),
            "backup_suffix": backup_suffix or default_backup_suffix,
            "files": results,
            "totals": {"success_count": success, "failed_count": failed},
        }

        report_paths: List[str] = []
        if write_reports:
            json_path = os.path.join(report_dir, "patch_apply.json")
            md_path = os.path.join(report_dir, "patch_apply.md")
            _write_json(json_path, payload)

            lines = []
            lines.append("# Patch Apply Report")
            lines.append("")
            lines.append(f"Timestamp: {payload['timestamp']}")
            lines.append(f"Diff: {payload['diff_path']}")
            lines.append(f"Target Root: {payload['target_root']}")
            lines.append("")
            lines.append("## Results")
            for r in results:
                lines.append(f"- {r.get('path')}: {r.get('status')} ({r.get('message','')})")
            lines.append("")
            lines.append("## Totals")
            lines.append(f"- Success: {success}")
            lines.append(f"- Failed: {failed}")
            _write_text(md_path, "\n".join(lines) + "\n")

            report_paths = [json_path, md_path]

        payload["report_paths"] = report_paths
        if report_paths:
            payload["artifact_ref"] = report_paths[0]
        return payload

    return patch_apply


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    patch_apply = create_patch_apply_handler(config)
    registry.register_tool(
        ToolRegistration(
            tool_id="patch.apply",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="patch_apply",
            handler=patch_apply,
            description="Apply a unified diff file with backups (approval required)",
            default_target=None,
        )
    )


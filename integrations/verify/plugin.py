from __future__ import annotations
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.security.process_allowlist import validate_command, CommandNotAllowed


def _abs_path(path: str) -> str:
    if not path:
        raise ValueError("path is required")
    return os.path.abspath(path)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=True)


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _run_cmd(cmd: List[str], cwd: str, timeout_sec: int) -> Dict[str, Any]:
    try:
        validate_command(cmd, allowed_entries=["run_chat.py", "run_ui.py", "main.py", "app.py", "__main__.py"])
    except CommandNotAllowed as e:
        return {
            "command": " ".join(cmd),
            "returncode": None,
            "stdout": "",
            "stderr": str(e),
            "status": "blocked",
        }
    try:
        p = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return {
            "command": " ".join(cmd),
            "returncode": p.returncode,
            "stdout": (p.stdout or ""),
            "stderr": (p.stderr or ""),
            "status": "success" if p.returncode == 0 else "failed",
        }
    except FileNotFoundError:
        return {
            "command": " ".join(cmd),
            "returncode": None,
            "stdout": "",
            "stderr": "not installed",
            "status": "not_installed",
        }
    except subprocess.TimeoutExpired as e:
        return {
            "command": " ".join(cmd),
            "returncode": None,
            "stdout": e.stdout or "",
            "stderr": f"timeout after {timeout_sec}s",
            "status": "timeout",
        }


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    timeout_sec = int(config.get("timeout_sec") or 60)
    reports_dir_name = str(config.get("reports_dir") or "reports")

    def verify_smoke(
        target_root: str = ".",
        run_compileall: bool = True,
        run_tool_list: bool = True,
        run_optional_audit: bool = False,
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        root = _abs_path(target_root)
        if not os.path.isdir(root):
            raise FileNotFoundError(f"Target root not found: {root}")

        results: List[Dict[str, Any]] = []

        if run_compileall:
            results.append(_run_cmd(["python", "-m", "compileall", root], root, timeout_sec))

        if run_tool_list:
            results.append(_run_cmd(["python", "main.py", "--list-tools"], root, timeout_sec))

        if run_optional_audit:
            res = _run_cmd(["python", "-m", "ruff", "check", "."], root, timeout_sec)
            if res.get("status") == "failed":
                stderr = (res.get("stderr") or "")
                if "No module named ruff" in stderr:
                    res["status"] = "not_installed"
                    res["returncode"] = None
                    res["stderr"] = "not installed"
            results.append(res)

        success_count = sum(1 for r in results if r.get("status") == "success")
        failed_count = sum(1 for r in results if r.get("status") in ("failed", "timeout"))
        not_installed_count = sum(1 for r in results if r.get("status") == "not_installed")

        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "target_root": root,
            "timeout_sec": timeout_sec,
            "results": results,
            "totals": {
                "success_count": success_count,
                "failed_count": failed_count,
                "not_installed_count": not_installed_count,
            },
        }

        report_paths: List[str] = []
        if write_reports:
            reports_dir = os.path.join(root, reports_dir_name)
            os.makedirs(reports_dir, exist_ok=True)
            json_path = os.path.join(reports_dir, "verify_smoke.json")
            md_path = os.path.join(reports_dir, "verify_smoke.md")
            _write_json(json_path, payload)

            lines = []
            lines.append("# Verify Smoke Report")
            lines.append("")
            lines.append(f"Timestamp: {payload['timestamp']}")
            lines.append(f"Target Root: {payload['target_root']}")
            lines.append("")
            lines.append("## Checks")
            for r in results:
                status = r.get("status")
                cmd = r.get("command")
                stderr = (r.get("stderr") or "").strip()
                stderr_excerpt = stderr[:200] + ("..." if len(stderr) > 200 else "")
                lines.append(f"- {status}: {cmd}")
                if status != "success" and stderr_excerpt:
                    lines.append(f"  - stderr: {stderr_excerpt}")
            lines.append("")
            lines.append("## Recommendation")
            if failed_count > 0:
                lines.append("- Fix failing checks and re-run verify.smoke.")
            elif not_installed_count > 0:
                lines.append("- Install missing optional tools to expand coverage.")
            else:
                lines.append("- Smoke checks passed. Proceed with deeper tests if needed.")

            _write_text(md_path, "\n".join(lines) + "\n")
            report_paths = [json_path, md_path]

        payload["report_paths"] = report_paths
        if report_paths:
            payload["artifact_ref"] = report_paths[0]
        return payload

    registry.register_tool(
        ToolRegistration(
            tool_id="verify.smoke",
            plugin_id=manifest.id,
            tool_group="process_exec",
            op="verify_smoke",
            handler=verify_smoke,
            description="Run smoke checks (compileall, tool list, optional audit)",
            default_target=None,
        )
    )


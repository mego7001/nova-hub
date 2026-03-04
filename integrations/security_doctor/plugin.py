from __future__ import annotations
import os
from typing import Any, Dict, Optional

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.portable.paths import detect_base_dir, default_workspace_dir
from core.reporting.writer import ReportWriter
from core.security.secrets import SecretsManager
from core.security.security_doctor import run_security_audit

_CTX: Dict[str, Any] = {}


def set_ui_context(runner, registry, project_root: str, workspace_root: Optional[str] = None) -> None:
    _CTX["runner"] = runner
    _CTX["registry"] = registry
    _CTX["project_root"] = project_root
    if workspace_root:
        _CTX["workspace_root"] = workspace_root


def _format_report_md(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("# Security Audit Report")
    lines.append("")
    lines.append(f"Timestamp: {report.get('timestamp')}")
    lines.append(f"Workspace: {report.get('workspace_root')}")
    if report.get("project_id"):
        lines.append(f"Project: {report.get('project_id')}")
    lines.append("")
    summary = report.get("summary") or {}
    lines.append("## Summary")
    lines.append(f"- OK: {summary.get('OK', 0)}")
    lines.append(f"- WARNING: {summary.get('WARNING', 0)}")
    lines.append(f"- CRITICAL: {summary.get('CRITICAL', 0)}")
    lines.append("")
    lines.append("## Findings")
    findings = report.get("findings") or []
    if not findings:
        lines.append("- (none)")
    else:
        for f in findings:
            lines.append(f"- [{f.get('severity')}] {f.get('checkId')}: {f.get('title')}")
            detail = f.get("detail") or ""
            if detail:
                lines.append(f"  - detail: {detail}")
            remediation = f.get("remediation")
            if remediation:
                lines.append(f"  - remediation: {remediation}")
            evidence = f.get("evidence") or []
            for ev in evidence[:5]:
                path = ev.get("path")
                line = ev.get("line")
                excerpt = ev.get("excerpt")
                ev_line = f"  - evidence: {path}"
                if line:
                    ev_line += f":{line}"
                if excerpt:
                    ev_line += f" — {excerpt}"
                lines.append(ev_line)
    lines.append("")
    gate = report.get("security_gate") or {}
    lines.append("## Security Gate")
    lines.append(f"- blocked_online_project: {gate.get('blocked_online_project', False)}")
    crits = gate.get("critical_findings") or []
    if crits:
        lines.append("- critical_findings:")
        for cid in crits:
            lines.append(f"  - {cid}")
    lines.append("")
    return "\n".join(lines) + "\n"


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def security_audit(project_id: str = "", write_reports: bool = True) -> Dict[str, Any]:
        base_dir = _CTX.get("project_root") or detect_base_dir()
        workspace = _CTX.get("workspace_root") or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base_dir)
        report = run_security_audit(workspace_root=workspace, project_id=project_id or None)

        report_paths = []
        if write_reports:
            runner = _CTX.get("runner")
            reg = _CTX.get("registry")
            if runner is None or reg is None:
                raise PermissionError("Security audit report writing requires UI context for approvals.")
            writer = ReportWriter(runner=runner, registry=reg, workspace_root=workspace, base_dir=base_dir)
            # Ensure we only write to workspace/reports
            ws_reports = os.path.abspath(os.path.join(workspace, "reports"))
            json_path = writer.write_report_json("security_audit.json", report, redact=SecretsManager.redact_text)
            md_path = writer.write_report_md("security_audit.md", _format_report_md(report), redact=SecretsManager.redact_text)
            for p in (json_path, md_path):
                abs_p = os.path.abspath(p)
                if not (abs_p.startswith(ws_reports + os.sep) or abs_p == ws_reports):
                    raise PermissionError("Security audit reports must be under workspace/reports")
            report_paths = [json_path, md_path]

        report["report_paths"] = report_paths
        if report_paths:
            report["artifact_ref"] = report_paths[0]
        return report

    registry.register_tool(
        ToolRegistration(
            tool_id="security.audit",
            plugin_id=manifest.id,
            tool_group="fs_read",
            op="security_audit",
            handler=security_audit,
            description="Run security audit (read-only; report writing may require approval)",
            default_target=None,
        )
    )

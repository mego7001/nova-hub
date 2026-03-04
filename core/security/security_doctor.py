from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.portable.paths import detect_base_dir, default_workspace_dir
from core.security.secrets import SecretsManager
from core.security import process_allowlist


_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "outputs",
    "logs",
    "patches",
    "releases",
}

_SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"ASIA[0-9A-Z]{16}"),  # AWS temp key
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),  # GitHub
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # Google API
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bapi[_-]?key\s*[:=]\s*[A-Za-z0-9\-_]{8,}"),
    re.compile(r"(?i)\bsecret\s*[:=]\s*[A-Za-z0-9\-_]{8,}"),
    re.compile(r"(?i)\bpassword\s*[:=]\s*[^\\s]{6,}"),
    re.compile(r"(?i)\btoken\s*[:=]\s*[A-Za-z0-9\-_]{8,}"),
]

_REDACT_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)password\\s*[:=]\\s*[^\\s]+"),
    re.compile(r"(?i)api[_-]?key\\s*[:=]\\s*[^\\s]+"),
    re.compile(r"(?i)secret\\s*[:=]\\s*[^\\s]+"),
    re.compile(r"(?i)token\\s*[:=]\\s*[^\\s]+"),
]

_SUSPICIOUS_EXTS_CRITICAL = {".pem", ".key", ".pfx", ".p12", ".kdbx"}
_SUSPICIOUS_EXTS_WARN = {
    ".exe",
    ".dll",
    ".bat",
    ".ps1",
    ".sh",
    ".cmd",
    ".msi",
    ".jar",
}

_GATE_PREFIXES = ("SECRETS_", "ALLOWLIST_", "WS_SYMLINK_")


@dataclass
class SecurityFinding:
    checkId: str
    severity: str  # OK | WARNING | CRITICAL
    title: str
    detail: str
    remediation: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "checkId": self.checkId,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
        }
        if self.remediation:
            out["remediation"] = self.remediation
        if self.evidence:
            out["evidence"] = self.evidence
        return out


def run_security_audit(
    workspace_root: Optional[str] = None,
    project_id: str | None = None,
) -> Dict[str, Any]:
    base_dir = detect_base_dir()
    workspace = os.path.abspath(workspace_root or os.environ.get("NH_WORKSPACE") or default_workspace_dir(base_dir))
    findings: List[SecurityFinding] = []

    _check_workspace_boundary(workspace, base_dir, findings)
    _check_symlinks(workspace, findings, project_id=project_id)
    _check_secrets_hygiene(workspace, findings)
    _check_process_allowlist(findings)
    _check_online_defaults(workspace, findings)
    _check_suspicious_artifacts(workspace, findings)
    _check_permissions_best_effort(workspace, findings)

    summary = _summarize(findings)
    gate = compute_security_gate(findings)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "workspace_root": workspace,
        "project_id": project_id or "",
        "summary": summary,
        "findings": [f.to_dict() for f in findings],
        "security_gate": gate,
    }


def compute_security_gate(findings: List[SecurityFinding]) -> Dict[str, Any]:
    critical = [
        f.checkId for f in findings
        if f.severity == "CRITICAL" and any(f.checkId.startswith(p) for p in _GATE_PREFIXES)
    ]
    return {
        "blocked_online_project": bool(critical),
        "critical_findings": critical,
        "last_audit_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _summarize(findings: List[SecurityFinding]) -> Dict[str, int]:
    counts = {"OK": 0, "WARNING": 0, "CRITICAL": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1
    return counts


def _redact_text(text: str) -> str:
    redacted = SecretsManager.redact_text(text or "")
    for pat in _REDACT_PATTERNS:
        redacted = pat.sub("[REDACTED]", redacted)
    return redacted


def _is_symlink_or_junction(path: str) -> bool:
    try:
        return os.path.islink(path) or os.path.realpath(path) != os.path.abspath(path)
    except OSError:
        return False


def _check_workspace_boundary(workspace: str, base_dir: str, findings: List[SecurityFinding]) -> None:
    if not os.path.isdir(workspace):
        findings.append(SecurityFinding(
            checkId="WS_BOUNDARY_MISSING",
            severity="CRITICAL",
            title="Workspace directory missing",
            detail=f"Workspace root not found: {workspace}",
        ))
        return
    ws = os.path.abspath(workspace)
    bd = os.path.abspath(base_dir)
    if not (ws.startswith(bd + os.sep) or ws == bd):
        findings.append(SecurityFinding(
            checkId="WS_BOUNDARY_OUTSIDE_BASE",
            severity="WARNING",
            title="Workspace outside base dir",
            detail=f"Workspace root {ws} is outside base dir {bd}. Ensure workspace-only enforcement.",
        ))
    else:
        findings.append(SecurityFinding(
            checkId="WS_BOUNDARY_OK",
            severity="OK",
            title="Workspace boundary OK",
            detail=f"Workspace root is under base dir: {ws}",
        ))


def _check_symlinks(workspace: str, findings: List[SecurityFinding], project_id: str | None = None) -> None:
    if _is_symlink_or_junction(workspace):
        findings.append(SecurityFinding(
            checkId="WS_SYMLINK_ROOT",
            severity="CRITICAL",
            title="Workspace root is a symlink/junction",
            detail=f"{workspace} resolves to {os.path.realpath(workspace)}; this can bypass workspace-only enforcement.",
        ))
    else:
        findings.append(SecurityFinding(
            checkId="WS_SYMLINK_ROOT_OK",
            severity="OK",
            title="Workspace root is not a symlink",
            detail=f"{workspace} is not a symlink/junction.",
        ))

    projects_dir = os.path.join(workspace, "projects")
    if not os.path.isdir(projects_dir):
        return
    for name in os.listdir(projects_dir):
        if project_id and name != project_id:
            continue
        proj_root = os.path.join(projects_dir, name)
        if not os.path.isdir(proj_root):
            continue
        working = os.path.join(proj_root, "working")
        if os.path.isdir(working) and _is_symlink_or_junction(working):
            findings.append(SecurityFinding(
                checkId="WS_SYMLINK_PROJECT",
                severity="CRITICAL",
                title="Project working folder is a symlink/junction",
                detail=f"{working} resolves to {os.path.realpath(working)}; this can bypass workspace-only enforcement.",
                evidence=[{"path": working}],
            ))


def _iter_files(root: str) -> Iterable[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        parts = set(rel.split(os.sep))
        if any(p in _EXCLUDE_DIRS for p in parts):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
        for name in filenames:
            yield os.path.join(dirpath, name)


def _is_binary_sample(path: str, max_probe: int = 4096) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(max_probe)
        return b"\x00" in chunk
    except OSError:
        return True


def _check_secrets_hygiene(workspace: str, findings: List[SecurityFinding]) -> None:
    evidence: List[Dict[str, Any]] = []
    hit_files: List[str] = []
    max_evidence = 10

    for path in _iter_files(workspace):
        if len(evidence) >= max_evidence:
            break
        low = path.lower()
        # focus on reports/transcripts/extracted/docs/chat
        if "reports" not in low and "docs" not in low and "extracted" not in low and "chat" not in low:
            continue
        if os.path.isdir(path):
            continue
        if os.path.getsize(path) > 2_000_000:
            continue
        if _is_binary_sample(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for pat in _SECRET_PATTERNS:
                        if pat.search(line):
                            if path not in hit_files:
                                hit_files.append(path)
                            excerpt = _redact_text(line.strip())[:200]
                            evidence.append({"path": path, "line": i, "excerpt": excerpt})
                            break
                    if len(evidence) >= max_evidence:
                        break
        except OSError:
            continue

    if hit_files:
        findings.append(SecurityFinding(
            checkId="SECRETS_LEAKED",
            severity="CRITICAL",
            title="Potential secrets found in workspace artifacts",
            detail=_redact_text(f"Found possible secrets in {len(hit_files)} file(s)."),
            remediation="Remove secrets from reports/transcripts or rotate keys; keep secrets out of workspace artifacts.",
            evidence=evidence,
        ))
    else:
        findings.append(SecurityFinding(
            checkId="SECRETS_SCAN_OK",
            severity="OK",
            title="No obvious secrets in scanned artifacts",
            detail="Reports/transcripts/extracted/docs scans did not find secret-like patterns.",
        ))

    # .env outside workspace/secrets
    env_hits = []
    for path in _iter_files(workspace):
        if path.lower().endswith(".env") and "workspace\\secrets" not in path.lower():
            env_hits.append(path)
            if len(env_hits) >= 5:
                break
    if env_hits:
        findings.append(SecurityFinding(
            checkId="SECRETS_ENV_FILE_OUTSIDE",
            severity="WARNING",
            title=".env files found outside workspace/secrets",
            detail="Environment files outside the secrets folder can expose tokens.",
            remediation="Move .env into workspace/secrets or remove from workspace.",
            evidence=[{"path": p} for p in env_hits],
        ))


def _check_process_allowlist(findings: List[SecurityFinding]) -> None:
    deny = getattr(process_allowlist, "_DENY_EXEC", set())
    allow = getattr(process_allowlist, "_ALLOWED_EXEC", set())
    deny_ok = {"cmd", "powershell", "pwsh"}.issubset(set(deny))
    allow_ok = not any(x in set(allow) for x in ("cmd", "powershell", "pwsh"))

    if not (deny_ok and allow_ok):
        findings.append(SecurityFinding(
            checkId="ALLOWLIST_SHELLS",
            severity="CRITICAL",
            title="Process allowlist permits shells",
            detail="Shell executables appear in allowlist or missing from deny list.",
            remediation="Ensure cmd/powershell/pwsh are denied and never allowlisted.",
        ))
    else:
        findings.append(SecurityFinding(
            checkId="ALLOWLIST_SHELLS_OK",
            severity="OK",
            title="Shell executables are denied",
            detail="Process allowlist denies cmd/powershell/pwsh.",
        ))

    try:
        process_allowlist.validate_command(["python", "-c", "print('hi')"])
        findings.append(SecurityFinding(
            checkId="ALLOWLIST_PYTHON_C",
            severity="CRITICAL",
            title="python -c is permitted",
            detail="python -c should be denied by the process allowlist.",
            remediation="Deny python -c in process allowlist.",
        ))
    except (ValueError, RuntimeError, OSError):
        findings.append(SecurityFinding(
            checkId="ALLOWLIST_PYTHON_C_OK",
            severity="OK",
            title="python -c is denied",
            detail="Process allowlist rejects python -c.",
        ))


def _check_online_defaults(workspace: str, findings: List[SecurityFinding]) -> None:
    prefs_root = os.path.join(workspace, "projects")
    enabled_projects = []
    for root, _dirs, files in os.walk(prefs_root):
        for name in files:
            if name == "conversation_prefs.json":
                path = os.path.join(root, name)
                try:
                    import json
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                    if bool(data.get("online_enabled")):
                        enabled_projects.append(path)
                except (OSError, ValueError):
                    continue
    if enabled_projects:
        findings.append(SecurityFinding(
            checkId="ONLINE_PREF_ENABLED",
            severity="WARNING",
            title="Online AI enabled in one or more projects",
            detail=f"Found online_enabled=true in {len(enabled_projects)} project preference file(s).",
            remediation="Disable Online AI unless explicitly needed.",
            evidence=[{"path": p} for p in enabled_projects[:5]],
        ))
    else:
        findings.append(SecurityFinding(
            checkId="ONLINE_PREF_OFF",
            severity="OK",
            title="Online AI disabled by default",
            detail="No projects have online_enabled set to true.",
        ))


def _check_suspicious_artifacts(workspace: str, findings: List[SecurityFinding]) -> None:
    suspicious_warn = []
    suspicious_critical = []
    for path in _iter_files(workspace):
        ext = os.path.splitext(path)[1].lower()
        if ext in _SUSPICIOUS_EXTS_CRITICAL:
            suspicious_critical.append(path)
            if len(suspicious_critical) >= 5:
                break
        elif ext in _SUSPICIOUS_EXTS_WARN:
            suspicious_warn.append(path)
    if suspicious_critical:
        findings.append(SecurityFinding(
            checkId="SECRETS_PRIVATE_KEY_FILES",
            severity="CRITICAL",
            title="Private key or credential files found",
            detail="Sensitive key material appears in workspace.",
            remediation="Remove credential files from workspace or move to a secure vault.",
            evidence=[{"path": p} for p in suspicious_critical],
        ))
    if suspicious_warn:
        findings.append(SecurityFinding(
            checkId="ARTIFACTS_EXECUTABLES",
            severity="WARNING",
            title="Executable artifacts found",
            detail="Executable/binary artifacts can expand attack surface.",
            remediation="Remove unexpected executables from workspace.",
            evidence=[{"path": p} for p in suspicious_warn[:10]],
        ))
    if not suspicious_warn and not suspicious_critical:
        findings.append(SecurityFinding(
            checkId="ARTIFACTS_OK",
            severity="OK",
            title="No suspicious artifacts detected",
            detail="Workspace scan did not find obvious executable or credential artifacts.",
        ))


def _check_permissions_best_effort(workspace: str, findings: List[SecurityFinding]) -> None:
    if os.name == "nt":
        findings.append(SecurityFinding(
            checkId="PERMS_WINDOWS_LIMITED",
            severity="OK",
            title="Windows permission checks limited",
            detail="ACL checks are limited on Windows in this audit. Review workspace permissions manually.",
        ))
        return

    def _perm_bits(path: str) -> int:
        return os.stat(path).st_mode & 0o777

    def _check(path: str, label: str) -> None:
        try:
            bits = _perm_bits(path)
        except OSError:
            return
        world_w = bool(bits & 0o002)
        group_w = bool(bits & 0o020)
        world_r = bool(bits & 0o004)
        if world_w:
            findings.append(SecurityFinding(
                checkId="PERMS_WORLD_WRITABLE",
                severity="CRITICAL",
                title=f"{label} is world-writable",
                detail=f"{path} mode={oct(bits)} allows world write.",
                remediation=f"chmod 700 {path}",
            ))
        elif group_w:
            findings.append(SecurityFinding(
                checkId="PERMS_GROUP_WRITABLE",
                severity="WARNING",
                title=f"{label} is group-writable",
                detail=f"{path} mode={oct(bits)} allows group write.",
                remediation=f"chmod 700 {path}",
            ))
        elif world_r and "secrets" in label.lower():
            findings.append(SecurityFinding(
                checkId="PERMS_SECRETS_READABLE",
                severity="WARNING",
                title=f"{label} is world-readable",
                detail=f"{path} mode={oct(bits)} allows world read.",
                remediation=f"chmod 700 {path}",
            ))
        else:
            findings.append(SecurityFinding(
                checkId=f"PERMS_{label.upper().replace(' ', '_')}_OK",
                severity="OK",
                title=f"{label} permissions OK",
                detail=f"{path} mode={oct(bits)}",
            ))

    _check(workspace, "Workspace")
    secrets_dir = os.path.join(workspace, "secrets")
    if os.path.isdir(secrets_dir):
        _check(secrets_dir, "Workspace Secrets")



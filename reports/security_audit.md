# Security Audit Report

Timestamp: 2026-02-06T06:04:23.669342Z
Workspace: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace

## Summary
- OK: 7
- WARNING: 1
- CRITICAL: 0

## Findings
- [OK] WS_BOUNDARY_OK: Workspace boundary OK
  - detail: Workspace root is under base dir: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace
- [OK] WS_SYMLINK_ROOT_OK: Workspace root is not a symlink
  - detail: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace is not a symlink/junction.
- [OK] SECRETS_SCAN_OK: No obvious secrets in scanned artifacts
  - detail: Reports/transcripts/extracted/docs scans did not find secret-like patterns.
- [OK] ALLOWLIST_SHELLS_OK: Shell executables are denied
  - detail: Process allowlist denies cmd/powershell/pwsh.
- [OK] ALLOWLIST_PYTHON_C_OK: python -c is denied
  - detail: Process allowlist rejects python -c.
- [OK] ONLINE_PREF_OFF: Online AI disabled by default
  - detail: No projects have online_enabled set to true.
- [WARNING] ARTIFACTS_EXECUTABLES: Executable artifacts found
  - detail: Executable/binary artifacts can expand attack surface.
  - remediation: Remove unexpected executables from workspace.
  - evidence: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace\projects\novahub_review-6c9090df\working\nova_hub\launchers\open_quick_links.bat
  - evidence: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace\projects\novahub_review-6c9090df\working\nova_hub\launchers\open_quick_links.ps1
  - evidence: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace\projects\novahub_review-6c9090df\working\nova_hub\launchers\start_novahub.bat
  - evidence: C:\Users\Victus\Downloads\nova_hub_v1_release\nova_hub\workspace\projects\novahub_review-6c9090df\working\nova_hub\launchers\start_novahub.ps1
- [OK] PERMS_WINDOWS_LIMITED: Windows permission checks limited
  - detail: ACL checks are limited on Windows in this audit. Review workspace permissions manually.

## Security Gate
- blocked_online_project: False


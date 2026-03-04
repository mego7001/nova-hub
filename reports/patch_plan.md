# Patch Plan

## Goal
Prepare safe mechanical patches for repo hygiene

## Constraints
Do not change source code without explicit request

## Inputs
- reports/project_scan.json: found
- reports/repo_search.json: found
- reports/audit_python.json: missing

## Selected Files
- integrations/conical_app/plugin.py (hotspot: most hits)
- integrations/fs_read_tools/plugin.py (hotspot: most hits)
- integrations/halftone_app/plugin.py (hotspot: most hits)
- configs/approvals.yaml (hotspot: most hits)
- .gitignore (hotspot: most hits)
- docs/QUICKSTART.md (hotspot: most hits)
- integrations/deepseek/plugin.py (hotspot: most hits)
- configs/tool_policy.yaml (hotspot: most hits)
- integrations/core_examples/plugin.py (hotspot: most hits)
- integrations/nesting_app/plugin.py (hotspot: most hits)

## Proposed Steps
- Add .env and report/patch output folders to .gitignore to avoid committing local outputs.

## Acceptance Checks
- reports/patch_plan.md exists and describes steps
- patches/plan_001.diff exists (may be empty if no safe changes)

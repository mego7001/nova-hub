from __future__ import annotations

import json

from core.audit_spine import ProjectAuditSpine


def test_project_audit_spine_read_events_returns_bounded_tail(tmp_path) -> None:
    workspace = str(tmp_path)
    project_id = "proj_tail"
    spine = ProjectAuditSpine(project_id=project_id, workspace_root=workspace)

    with open(spine.path, "w", encoding="utf-8") as f:
        for i in range(1200):
            f.write(json.dumps({"event_id": f"e{i}", "idx": i}) + "\n")

    events = spine.read_events(limit=40)
    assert len(events) == 40
    assert int(events[0]["idx"]) == 1160
    assert int(events[-1]["idx"]) == 1199

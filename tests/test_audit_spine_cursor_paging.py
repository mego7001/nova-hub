from __future__ import annotations

import json

from core.audit_spine import ProjectAuditSpine


def test_project_audit_spine_read_events_page_uses_cursor(tmp_path) -> None:
    workspace = str(tmp_path)
    project_id = "proj_page"
    spine = ProjectAuditSpine(project_id=project_id, workspace_root=workspace)

    with open(spine.path, "w", encoding="utf-8") as f:
        for i in range(10):
            f.write(json.dumps({"event_id": f"e{i}", "idx": i}) + "\n")

    page1 = spine.read_events_page(limit=3, cursor=0)
    assert [int(x["idx"]) for x in page1["events"]] == [0, 1, 2]
    assert page1["next_cursor"] == 3
    assert page1["has_more"] is True

    page2 = spine.read_events_page(limit=3, cursor=page1["next_cursor"])
    assert [int(x["idx"]) for x in page2["events"]] == [3, 4, 5]

    direct = spine.read_events(limit=3, cursor=3)
    assert [int(x["idx"]) for x in direct] == [3, 4, 5]

from pathlib import Path
import tempfile

from core.projects.manager import ProjectManager
from ui.hud_qml.controller import GENERAL_CHAT_ID, HUDController


def _make_project(workspace: str, name: str) -> str:
    seed = Path(workspace) / f"{name}_src"
    seed.mkdir(parents=True, exist_ok=True)
    (seed / "main.py").write_text("print('seed')\n", encoding="utf-8")
    pm = ProjectManager(workspace_root=workspace)
    return pm.add_project_from_folder(str(seed))


def test_palette_actions_include_core_items():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        project_id = _make_project(workspace, "p1")
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.select_project(project_id)

        actions = controller.getPaletteActions()
        ids = {str(a.get("id") or "") for a in actions}

        assert any(i.startswith("project.switch:") for i in ids)
        assert f"project.switch:{GENERAL_CHAT_ID}" in ids
        assert "project.create" in ids
        assert "apply.queue" in ids
        assert "verify.run" in ids
        assert "security.audit" in ids
        assert "hud.refresh" in ids
        assert "qa.refresh" in ids
        assert "threed.activate" in ids
        assert "threed.sample" in ids
        assert "reports.open" in ids

        reports_action = next(a for a in actions if str(a.get("id")) == "reports.open")
        assert str(reports_action.get("badge") or "").startswith("OK")
        assert "prints workspace reports path only" in str(reports_action.get("description") or "").lower()


def test_run_palette_action_routes_to_internal_methods():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        p1 = _make_project(workspace, "p1")
        p2 = _make_project(workspace, "p2")
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.select_project(p1)

        calls = []
        controller.refresh_projects = lambda: calls.append("projects")  # type: ignore[method-assign]
        controller.refresh_jobs = lambda: calls.append("jobs")  # type: ignore[method-assign]
        controller.refresh_timeline = lambda: calls.append("timeline")  # type: ignore[method-assign]
        controller.refreshQaReport = lambda: calls.append("qa")  # type: ignore[method-assign]

        ok_refresh = controller.runPaletteAction("hud.refresh", "")
        assert ok_refresh is True
        assert calls == ["projects", "jobs", "timeline"]

        ok_qa = controller.runPaletteAction("qa.refresh", "")
        assert ok_qa is True
        assert calls[-1] == "qa"

        queue_calls = []
        controller.queue_apply = lambda: queue_calls.append("apply")  # type: ignore[method-assign]
        controller._tools_missing = []
        controller._confirmation_mode = "none"
        controller._busy_count = 0
        ok_apply = controller.runPaletteAction("apply.queue", "")
        assert ok_apply is True
        assert queue_calls == ["apply"]

        ok_switch = controller.runPaletteAction(f"project.switch:{p2}", "")
        assert ok_switch is True
        assert controller.currentProjectId == p2

        ok_general = controller.runPaletteAction(f"project.switch:{GENERAL_CHAT_ID}", "")
        assert ok_general is True
        assert controller.currentProjectId == GENERAL_CHAT_ID

        ok_create_missing_query = controller.runPaletteAction("project.create", "")
        assert ok_create_missing_query is False

        ok_create = controller.runPaletteAction("project.create", "palette created")
        assert ok_create is True
        assert controller.currentProjectId != GENERAL_CHAT_ID


def test_reports_open_badge_and_description_follow_capabilities():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        project_id = _make_project(workspace, "p_reports")
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.select_project(project_id)

        # No folder-open/list tools: path-only fallback.
        reports_action = next(a for a in controller.getPaletteActions() if str(a.get("id")) == "reports.open")
        assert str(reports_action.get("badge") or "").startswith("OK")
        assert str(reports_action.get("badge") or "") == "OK (path)"
        assert "prints workspace reports path only" in str(reports_action.get("description") or "").lower()

        # fs.list_dir available: fs mode.
        controller._registry.tools["fs.list_dir"] = object()  # type: ignore[index]
        reports_action = next(a for a in controller.getPaletteActions() if str(a.get("id")) == "reports.open")
        assert str(reports_action.get("badge") or "").startswith("OK")
        assert str(reports_action.get("badge") or "") == "OK (fs)"
        assert "fs.list_dir" in str(reports_action.get("description") or "")

        # desktop.open_folder available: direct open mode.
        controller._registry.tools["desktop.open_folder"] = object()  # type: ignore[index]
        reports_action = next(a for a in controller.getPaletteActions() if str(a.get("id")) == "reports.open")
        assert str(reports_action.get("badge") or "").startswith("OK")
        assert str(reports_action.get("badge") or "") == "OK"
        assert "Open workspace reports folder" in str(reports_action.get("description") or "")

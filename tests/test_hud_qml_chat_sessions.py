from pathlib import Path
import tempfile

from core.projects.manager import ProjectManager
from ui.hud_qml.controller import CHAT_SESSION_PREFIX, GENERAL_CHAT_ID, HUDController


def test_chat_sessions_are_separate_from_projects():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )

        assert controller.chatsModel.count() >= 1
        first_chat = controller.chatsModel.get(0)
        assert str(first_chat.get("chat_id") or "") == GENERAL_CHAT_ID

        for i in range(controller.projectsModel.count()):
            row = controller.projectsModel.get(i)
            assert str(row.get("project_id") or "") != GENERAL_CHAT_ID

        before_projects = controller.projectsModel.count()
        before_chats = controller.chatsModel.count()
        new_chat_id = controller.create_chat()

        assert new_chat_id.startswith(CHAT_SESSION_PREFIX)
        assert controller.currentChatId == new_chat_id
        assert controller.chatsModel.count() == before_chats + 1
        assert controller.projectsModel.count() == before_projects


def test_chat_can_convert_to_project_with_message_migration():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        chat_id = controller.create_chat()
        controller.send_message("hello from chat session")

        controller.send_message("/project Converted Session")
        project_id = controller.currentProjectId
        assert project_id != GENERAL_CHAT_ID
        assert not project_id.startswith(CHAT_SESSION_PREFIX)

        pm = ProjectManager(workspace_root=workspace)
        paths = pm.get_project_paths(project_id)
        log_path = Path(paths.project_root) / "hud_messages.jsonl"
        text = log_path.read_text(encoding="utf-8")
        assert "hello from chat session" in text

        converted_row = None
        for i in range(controller.chatsModel.count()):
            row = controller.chatsModel.get(i)
            if str(row.get("chat_id") or "") == chat_id:
                converted_row = row
                break
        assert converted_row is not None
        assert str(converted_row.get("status") or "") == "converted"
        assert str(converted_row.get("linked_project_id") or "") == project_id

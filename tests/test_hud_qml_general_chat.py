from pathlib import Path
import tempfile
from types import SimpleNamespace

from core.projects.manager import ProjectManager
from core.plugin_engine.registry import PluginRegistration, ToolRegistration
from ui.hud_qml.controller import GENERAL_CHAT_ID, HUDController


def test_general_chat_is_available_without_projects():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        assert controller.currentProjectId == GENERAL_CHAT_ID
        assert controller.applyEnabled is False

        controller.send_message("hello general mode")
        assert controller.messagesModel.count() >= 2
        assert controller.hasPendingApproval is False
        assert controller.latestReplyPreview
        assert controller.latestReplyPreview != "No replies yet."


def test_general_chat_greeting_has_human_reply():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.send_message("صباح الخير")
        assert "صباح النور" in controller.latestReplyPreview


def test_general_chat_project_create_command_switches_context():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        assert controller.currentProjectId == GENERAL_CHAT_ID

        controller.send_message("/project Demo Project")
        assert controller.currentProjectId != GENERAL_CHAT_ID
        assert controller.currentProjectId

        pm = ProjectManager(workspace_root=workspace)
        ids = {str(p.get("id") or "") for p in pm.list_projects(include_archived=False)}
        assert controller.currentProjectId in ids


def test_general_chat_apply_is_blocked_with_hint():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.select_project(GENERAL_CHAT_ID)
        controller.queue_apply()

        assert controller.hasPendingApproval is True
        assert controller.confirmationReadOnly is True
        assert "general chat mode" in controller.confirmationSummary.lower()


def test_general_chat_api_probe_command_returns_status():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.send_message("/api")
        assert "api probe" in controller.latestReplyPreview.lower()
        assert "deepseek" in controller.latestReplyPreview.lower()
        assert "gemini" in controller.latestReplyPreview.lower()


def test_general_chat_uses_available_llm_provider_reply():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller._registry.register_plugin(
            PluginRegistration(
                plugin_id="deepseek",
                kind="integration",
                name="DeepSeek",
                version="1.0",
                entrypoint="tests.fake",
                tool_groups=["deepseek"],
                config={"api_key": "test-key"},
            )
        )

        def fake_chat(prompt: str, system: str = "", temperature: float = 0.0):
            assert "Conversation context" in prompt
            return {"choices": [{"message": {"content": "رد تفاعلي من المزود"}}]}

        controller._registry.register_tool(
            ToolRegistration(
                tool_id="deepseek.chat",
                plugin_id="deepseek",
                tool_group="deepseek",
                op="deepseek_chat",
                handler=fake_chat,
                description="fake",
                default_target="fake",
            )
        )

        controller.send_message("ازيك")
        assert "رد تفاعلي" in controller.latestReplyPreview


def test_general_chat_local_fallback_is_contextual_not_constant():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )
        controller.send_message("how are you")
        reply_1 = controller.latestReplyPreview
        controller.send_message("what is your name")
        reply_2 = controller.latestReplyPreview

        assert reply_1
        assert reply_2
        assert reply_1 != reply_2
        assert "online ai is required" not in reply_1.lower()
        assert "online ai is required" not in reply_2.lower()


def test_general_chat_filters_canned_brain_reply():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as workspace:
        controller = HUDController(
            project_root=str(root),
            workspace_root=workspace,
            backend_enabled=False,
            background_tasks=False,
        )

        class _CannedBrain:
            def respond(self, _message: str, _context=None):
                return SimpleNamespace(
                    reply_text="General chat message saved. Use /project <name> anytime to start a project workspace.",
                    suggested_actions=[],
                    requires_confirmation=False,
                )

        controller._conversation_brain = _CannedBrain()
        controller.send_message("Need practical next step for onboarding")
        reply = controller.latestReplyPreview

        assert reply
        assert "general chat message saved" not in reply.lower()
        assert "need practical next step for onboarding".lower() in reply.lower() or "step" in reply.lower()

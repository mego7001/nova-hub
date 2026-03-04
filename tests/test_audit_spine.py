import json
import os
import tempfile
import unittest

from core.audit_spine import AuditSpine
from core.chat.orchestrator import ChatOrchestrator
from core.chat.state import ChatState
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.system_state_machine import SystemStateMachine, PolicyFailure
from core.records.record_store import RecordStore


class DummyRunner:
    def execute_registered_tool(self, tool, **kwargs):
        return tool.handler(**kwargs)


class TestAuditSpine(unittest.TestCase):
    def test_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spine = AuditSpine("m1", tmp)
            spine.emit("intent_captured", {"input": "hi"})
            spine.emit("decision_recorded", {"decision_type": "execute"})
            with open(spine.path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            spine.emit("run_started", {"run_state": "executing"})
            with open(spine.path, "r", encoding="utf-8") as f:
                lines2 = [line.strip() for line in f if line.strip()]
            self.assertEqual(len(lines2), 3)
            self.assertEqual(json.loads(lines2[0])["event_id"], first["event_id"])

    def test_run_chain_has_required_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NH_WORKSPACE"] = tmp
            project_root = tmp
            proj = os.path.join(tmp, "proj")
            os.makedirs(proj, exist_ok=True)

            registry = PluginRegistry()
            registry.register_plugin(
                type(
                    "P",
                    (),
                    {
                        "plugin_id": "test",
                        "kind": "test",
                        "name": "test",
                        "version": "0",
                        "entrypoint": "test",
                        "tool_groups": [],
                        "config": {},
                    },
                )()
            )

            def scan_handler(**kwargs):
                return {
                    "report_paths": [os.path.join(tmp, "reports", "scan.json")],
                    "stats": {"file_count": 1, "loc_estimate": 10},
                    "languages": {"py": 1},
                    "entrypoints": [],
                    "dependency_manifests": [],
                }

            def search_handler(**kwargs):
                return {
                    "report_paths": [os.path.join(tmp, "reports", "search.json")],
                    "total_matches": 0,
                    "hotspots": {"files_with_most_hits": []},
                }

            def verify_handler(**kwargs):
                return {
                    "report_paths": [os.path.join(tmp, "reports", "verify.json")],
                    "totals": {"failed_count": 0},
                }

            registry.register_tool(
                ToolRegistration(
                    tool_id="project.scan_repo",
                    plugin_id="test",
                    tool_group="fs_read",
                    op="scan_repo",
                    handler=scan_handler,
                    description="scan",
                    default_target=None,
                )
            )
            registry.register_tool(
                ToolRegistration(
                    tool_id="repo.search",
                    plugin_id="test",
                    tool_group="fs_read",
                    op="search",
                    handler=search_handler,
                    description="search",
                    default_target=None,
                )
            )
            registry.register_tool(
                ToolRegistration(
                    tool_id="verify.smoke",
                    plugin_id="test",
                    tool_group="verify",
                    op="smoke",
                    handler=verify_handler,
                    description="verify",
                    default_target=None,
                )
            )

            orch = ChatOrchestrator(project_root=project_root, runner=DummyRunner(), registry=registry)
            orch.handle_message("analyze", project_path=proj, session_id="m1", write_reports=False)

            spine = AuditSpine("m1", os.path.join(tmp, "reports"))
            timeline = spine.timeline()
            run_id = ""
            for evt in timeline:
                if evt.get("event_type") == "run_started":
                    run_id = evt.get("run_id") or ""
                    break
            self.assertTrue(run_id)
            chain = spine.run_chain(run_id)
            event_types = [e.get("event_type") for e in chain]
            for required in [
                "run_started",
                "tool_invoked",
                "artifact_registered",
                "verification_completed",
                "run_completed",
            ]:
                self.assertIn(required, event_types)

    def test_policy_failure_emits_event_and_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NH_WORKSPACE"] = tmp
            orch = ChatOrchestrator(project_root=tmp, runner=DummyRunner(), registry=PluginRegistry())
            state = ChatState(session_id="m2")
            orch._active_state = state
            orch._active_session_id = "m2"
            orch._state_machine = SystemStateMachine("analysis")
            orch._records = RecordStore(os.path.join(tmp, "reports"))
            orch._audit = AuditSpine("m2", os.path.join(tmp, "reports"))
            with self.assertRaises(PolicyFailure):
                orch._transition_state(state, "executing")
            self.assertEqual(state.system_state, "blocked")
            timeline = orch._audit.timeline()
            self.assertTrue(any(e.get("event_type") == "policy_failure" for e in timeline))


if __name__ == "__main__":
    unittest.main()

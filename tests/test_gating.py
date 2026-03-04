import os
import tempfile
import unittest

from core.chat.orchestrator import ChatOrchestrator
from core.chat.state import ChatState
from core.plugin_engine.registry import PluginRegistry
from core.plugin_engine.registry import ToolRegistration
from core.system_state_machine import SystemStateMachine, TransitionEvidence, PolicyFailure
from core.records.record_store import RecordStore, DecisionRecord


class DummyRunner:
    def execute_registered_tool(self, *args, **kwargs):
        raise RuntimeError("not used in test")


class TestGating(unittest.TestCase):
    def test_missing_decision_blocks_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NH_WORKSPACE"] = tmp
            orch = ChatOrchestrator(project_root=tmp, runner=DummyRunner(), registry=PluginRegistry())
            state = ChatState(session_id="s1")
            orch._state_machine = SystemStateMachine("analysis")
            orch._records = RecordStore(os.path.join(tmp, "reports"))
            orch._active_state = state
            orch._active_session_id = "s1"
            with self.assertRaises(PolicyFailure):
                orch._transition_state(state, "executing", TransitionEvidence(decision_ref="decision:missing"))
            self.assertEqual(state.system_state, "blocked")

    def test_missing_artifact_blocks_verifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NH_WORKSPACE"] = tmp
            orch = ChatOrchestrator(project_root=tmp, runner=DummyRunner(), registry=PluginRegistry())
            state = ChatState(session_id="s2")
            orch._state_machine = SystemStateMachine("analysis")
            store = RecordStore(os.path.join(tmp, "reports"))
            orch._records = store
            orch._active_state = state
            orch._active_session_id = "s2"
            decision_id = "decision:test"
            store.add_decision(DecisionRecord(
                decision_id=decision_id,
                mission_id="s2",
                intent_id="intent:test",
                operator_id="operator",
                decision_type="execute",
                decision_outcome="approved",
                recorded_at="now",
            ))
            orch._current_intent_id = "intent:test"
            orch._transition_state(state, "executing", TransitionEvidence(decision_ref=decision_id))
            with self.assertRaises(PolicyFailure):
                orch._transition_state(state, "verifying", TransitionEvidence(artifact_ref="artifact:missing"))
            self.assertEqual(state.system_state, "blocked")

    def test_tool_execution_blocked_without_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NH_WORKSPACE"] = tmp
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
            registry.register_tool(
                ToolRegistration(
                    tool_id="test.noop",
                    plugin_id="test",
                    tool_group="fs_read",
                    op="noop",
                    handler=lambda: {"ok": True},
                    description="noop",
                    default_target=None,
                )
            )
            orch = ChatOrchestrator(project_root=tmp, runner=DummyRunner(), registry=registry)
            state = ChatState(session_id="s3")
            orch._active_state = state
            orch._active_session_id = "s3"
            orch._records = RecordStore(os.path.join(tmp, "reports"))
            decision_id = "decision:ok"
            orch._records.add_decision(DecisionRecord(
                decision_id=decision_id,
                mission_id="s3",
                intent_id="intent:test",
                operator_id="operator",
                decision_type="execute",
                decision_outcome="approved",
                recorded_at="now",
            ))
            orch._state_machine = SystemStateMachine("executing")
            orch._current_run_id = ""
            with self.assertRaises(PolicyFailure):
                orch._run_tool("test.noop")
            self.assertEqual(state.system_state, "blocked")


if __name__ == "__main__":
    unittest.main()

import unittest

from core.system_state_machine import SystemStateMachine, TransitionEvidence


class TestSystemStateMachine(unittest.TestCase):
    def test_runtime_failure_marks_failed_not_blocked(self) -> None:
        sm = SystemStateMachine("idle")
        sm.transition("intake")
        sm.transition("analysis")
        sm.transition("executing", TransitionEvidence(decision_ref="decision:test"))
        sm.transition("failed")
        self.assertEqual(sm.state, "failed")


if __name__ == "__main__":
    unittest.main()

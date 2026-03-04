from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.conversation import jarvis_core
from core.conversation.confirmation import is_confirmation, is_rejection
from core.conversation.intent_parser import parse_intent_soft


class JarvisSimulator:
    def __init__(self, pinned_goal: str = "") -> None:
        self.ctx: Dict[str, Any] = {"jarvis": {}}
        if pinned_goal:
            self.ctx["jarvis"]["pinned_goal"] = pinned_goal
        self.pending_action: Dict[str, Any] | None = None
        self.pending_candidate: Dict[str, Any] | None = None
        self.topic_hash: str = ""
        self.executed: List[Dict[str, Any]] = []
        self.logged_notes: List[str] = []

    def handle(self, message: str) -> str:
        text = (message or "").strip()
        if not text:
            return jarvis_core.generate_reply(text, self.ctx)

        if self.pending_action:
            if is_confirmation(text):
                self.executed.append(self.pending_action)
                self.pending_action = None
                return "CONFIRMED"
            if is_rejection(text):
                self.pending_action = None
                return "CANCELLED"

        if self.pending_candidate:
            if jarvis_core.is_user_adjusting(text):
                self.pending_candidate = None
                self.topic_hash = ""
                return "ADJUSTED"
            if jarvis_core.is_user_insisting(text) or is_confirmation(text):
                level = jarvis_core.warning_level(
                    self.ctx,
                    {"topic_hash": self.topic_hash, "insist": True, "risky": True},
                )
                warning = jarvis_core.warning_text(level)
                if level >= 3:
                    jarvis_core.record_documentary_warning(self.ctx)
                    self.logged_notes.append(jarvis_core.documentary_log_note())
                    self.pending_action = self.pending_candidate
                    self.pending_candidate = None
                return warning

        intent = parse_intent_soft(text)
        intent_result = jarvis_core.assess_intent(text, self.ctx)
        action: Dict[str, Any] = {}
        if intent.get("confidence") == "HIGH":
            action = intent_result.proposed_action

        if action and (intent_result.conflict or intent_result.risk_signal == "high"):
            if intent_result.conflict:
                disagree, question = jarvis_core.manage_disagreement(self.ctx, action)
                jarvis_core.update_last_disagreement(self.ctx, intent_result.topic_hash, disagree)
                jarvis_core.warning_level(
                    self.ctx,
                    {"topic_hash": intent_result.topic_hash, "insist": False, "risky": True},
                )
                self.pending_candidate = action
                self.topic_hash = intent_result.topic_hash
                return f"{disagree} {question}"
            level = jarvis_core.warning_level(
                self.ctx,
                {"topic_hash": intent_result.topic_hash, "insist": False, "risky": True},
            )
            self.pending_candidate = action
            self.topic_hash = intent_result.topic_hash
            return jarvis_core.warning_text(level)

        return jarvis_core.generate_reply(text, self.ctx)


class RecoveryTracker:
    def __init__(self) -> None:
        self.pending_reminder: str = ""

    def on_failure(self, event: Dict[str, Any]) -> str:
        plan, reminder = jarvis_core.recovery_mode({}, event)
        self.pending_reminder = reminder
        return plan

    def on_success(self) -> str:
        if not self.pending_reminder:
            return ""
        reminder = self.pending_reminder
        self.pending_reminder = ""
        return reminder


def _record(results: List[Dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    results.append({"name": name, "passed": passed, "detail": detail})


def run_tests() -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    # 1) Disagreement
    try:
        sim = JarvisSimulator(pinned_goal="Keep stability")
        msg = "apply diff1.diff and ignore the goal"
        resp = sim.handle(msg)
        ok = ("أنا مش موافق" in resp) and (resp.count("تحب نكمّل في اتجاهك ولا نعدّل المسار؟") == 1)
        ok = ok and (len(sim.executed) == 0)
        detail = "Disagreement + single question + no execution"
        _record(results, "Disagreement", ok, detail)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        _record(results, "Disagreement", False, f"Exception: {e}")

    # 2) Graduated warnings
    try:
        sim = JarvisSimulator()
        w1 = sim.handle("apply diff1.diff")
        w2 = sim.handle("كمّل")
        w3 = sim.handle("كمّل")
        ok = w1 != w2 and w2 == jarvis_core.warning_text(2)
        ok = ok and ("؟" not in w2)
        ok = ok and (w3 == jarvis_core.warning_text(3))
        ok = ok and (jarvis_core.documentary_log_note() in sim.logged_notes)
        _record(results, "Graduated Warnings", ok, "Level 2 differs, no question spam, level 3 logged")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        _record(results, "Graduated Warnings", False, f"Exception: {e}")

    # 3) Confirmation gating
    try:
        sim = JarvisSimulator()
        sim.handle("apply diff1.diff")
        sim.handle("كمّل")
        sim.handle("كمّل")
        pre = len(sim.executed)
        sim.handle("yes")
        post = len(sim.executed)
        ok = (pre == 0) and (post == 1)
        _record(results, "Confirmation Gating", ok, "No execution without explicit confirm")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        _record(results, "Confirmation Gating", False, f"Exception: {e}")

    # 4) Recovery Mode
    try:
        tracker = RecoveryTracker()
        plan = tracker.on_failure({"type": "verify_failed"})
        reminder = tracker.on_success()
        reminder2 = tracker.on_success()
        ok = ("خطة" in plan or "خلّينا" in plan) and reminder == "بالمناسبة، النتيجة دي كانت ضمن السيناريو اللي اتذكر قبل كده." and reminder2 == ""
        _record(results, "Recovery Mode", ok, "Plan first, reminder once after success")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        _record(results, "Recovery Mode", False, f"Exception: {e}")

    # 5) Persistence
    try:
        ctx = {"jarvis": {}}
        lvl1 = jarvis_core.warning_level(ctx, {"topic_hash": "abc", "insist": False, "risky": True})
        persisted = ctx["jarvis"]
        ctx2 = {"jarvis": persisted}
        lvl2 = jarvis_core.warning_level(ctx2, {"topic_hash": "abc", "insist": True, "risky": True})
        ok = (lvl1 == 1) and (lvl2 == 2) and (ctx2["jarvis"]["warning_state"]["level"] == 2)
        _record(results, "Persistence", ok, "Warning level persists across sessions")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        _record(results, "Persistence", False, f"Exception: {e}")

    return results


def write_reports(results: List[Dict[str, Any]]) -> None:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    total = len(results)
    passed = len([r for r in results if r["passed"]])
    failed = total - passed
    limitations = [
        "Simulator mirrors Jarvis Core flow; it does not drive the Qt UI.",
        "Tool execution gating is simulated; UI button flows are not exercised.",
    ]

    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    payload = {
        "generated_at": _now_iso(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": results,
        "limitations": limitations,
    }
    json_path = os.path.join(reports_dir, "jarvis_core_qa.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    lines = []
    lines.append("# Jarvis Core QA")
    lines.append("")
    lines.append(f"Generated at: {payload['generated_at']}")
    lines.append(f"Summary: {passed} passed / {failed} failed")
    lines.append("")
    lines.append("## Tests")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- [{status}] {r['name']}: {r['detail']}")
    lines.append("")
    lines.append("## Limitations")
    for lim in limitations:
        lines.append(f"- {lim}")
    lines.append("")
    md_path = os.path.join(reports_dir, "jarvis_core_qa.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    results = run_tests()
    write_reports(results)
    failed = [r for r in results if not r["passed"]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

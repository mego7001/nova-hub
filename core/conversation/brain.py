from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.conversation.intent_parser import parse_intent_soft
from core.engineering import extract as engineering_extract
from core.llm.router import LLMRouter
from core.reasoning.agent import ReasoningAgent


@dataclass
class BrainResult:
    reply_text: str
    suggested_actions: List[Dict[str, Any]]
    requires_confirmation: bool
    routing: Optional[Dict[str, Any]] = None


class ConversationalBrain:
    def __init__(self, router: LLMRouter | None = None, registry: Any = None, runner: Any = None):
        self.router = router or LLMRouter()
        self.registry = registry
        self.runner = runner
        self.agent = None
        if registry and runner:
            self.agent = ReasoningAgent(self.router, registry, runner)

    def respond(self, message: str, context: Dict[str, Any] | None = None) -> BrainResult:
        text = (message or "").strip()
        if not text:
            return BrainResult(
                reply_text="أنا معاك. قولّي إيه اللي مضايقك في المشروع؟",
                suggested_actions=[],
                requires_confirmation=False,
            )

        intent = parse_intent_soft(text)
        suggested: List[Dict[str, Any]] = []
        reply = ""
        routing: Optional[Dict[str, Any]] = None
        prefs = (context or {}).get("prefs") or {}
        level = str(prefs.get("explanation_level") or "normal").lower()
        risk = str(prefs.get("risk_posture") or "balanced").lower()
        pinned_goal = str(prefs.get("pinned_goal") or "").strip()
        state = (context or {}).get("state")
        online_enabled = bool((context or {}).get("online_enabled"))
        project_id = str((context or {}).get("project_id") or "")
        mode = str((context or {}).get("mode") or "general")
        session_id = str((context or {}).get("session_id") or "")
        ollama_model_override = str((context or {}).get("ollama_model_override") or "").strip()

        explain = self._explain_suggestion(text, state)
        if explain:
            return BrainResult(reply_text=explain, suggested_actions=[], requires_confirmation=False)

        if engineering_extract.is_engineering_query(text):
            project_id = str((context or {}).get("project_id") or "")
            workspace_root = (context or {}).get("workspace_root")
            project_path = (context or {}).get("project_path")
            res = engineering_extract.run_engineering_brain(
                text,
                project_id=project_id,
                workspace_root=workspace_root,
                project_path=project_path,
                online_enabled=online_enabled,
                router=self.router,
            )
            reply = res.get("reply") or ""
            return BrainResult(reply_text=reply, suggested_actions=[], requires_confirmation=False)

        conf = str(intent.get("confidence") or "NONE").upper()
        offline_conf = "high"
        if conf in ("LOW", "NONE"):
            offline_conf = "low"
        elif conf == "MEDIUM":
            offline_conf = "medium"

        routed = self.router.route(
            "conversation",
            prompt=text,
            online_enabled=online_enabled,
            project_id=project_id,
            offline_confidence=offline_conf,
            extracted_text_len=0,
            parser_ok=True,
            mode=mode,
            request_kind="chat",
            session_id=session_id,
            model_override=ollama_model_override,
        )
        routed_meta = routed.get("_routing")
        if isinstance(routed_meta, dict):
            routing = routed_meta

        if routed.get("text"):
            reply = routed.get("text") or ""
            if routed.get("mode") == "online":
                reply = "Nova (online): " + reply
        elif intent["confidence"] == "NONE":
            reply = self._format_reply(
                level,
                ack="فاهمك.",
                body=[
                    "لو تحب، أقدر أراجع الصورة بسرعة وأقولك أولويات واضحة.",
                ],
                question="إيه الجزء اللي حاسس إنه تقيل أو مش مظبوط؟",
                options=self._options_for_risk(risk),
            )
        elif intent["confidence"] in ("LOW", "MEDIUM"):
            reply = self._format_reply(
                level,
                ack="تمام، وصلتني الفكرة.",
                body=[],
                question="تحب أبدأ تنفيذ دلوقتي ولا نوضح الهدف الأول؟",
                options=[],
            )
            if intent.get("intent") and intent.get("intent") != "unknown":
                suggested.append(self._action_from_intent(intent))
        else:
            body = ["أقدر أبدأ الإجراء ده فورًا بعد تأكيدك."]
            if pinned_goal and level != "short":
                body.append(f"الهدف المثبت عندي: {pinned_goal}")
            if intent.get("intent") and intent.get("intent") != "unknown":
                suggested.append(self._action_from_intent(intent))

            # If it is a high-confidence intent that requires reasoning, use the agent.
            if self.agent and intent.get("intent") in ("analyze", "search", "plan", "pipeline"):
                agent_res = self.agent.solve(text, context=context)
                if agent_res.get("results"):
                    reply = agent_res.get("reply") or reply

        return BrainResult(
            reply_text=reply,
            suggested_actions=[a for a in suggested if a],
            requires_confirmation=False,
            routing=routing,
        )

    def _format_reply(
        self,
        level: str,
        ack: str,
        body: List[str],
        question: str | None,
        options: List[str],
    ) -> str:
        lines: List[str] = [ack]
        if level == "short":
            if body:
                lines.append(body[0])
            if question:
                lines.append(question)
            return "\n".join([l for l in lines if l])[:800]

        lines.extend(body)
        if level == "detailed" and options:
            lines.append("اختيارات سريعة:")
            for opt in options[:3]:
                lines.append(f"- {opt}")
        if question:
            lines.append(question)
        return "\n".join([l for l in lines if l])[:1200]

    def _options_for_risk(self, risk: str) -> List[str]:
        if risk == "conservative":
            return [
                "نراجع الوضع الحالي ونحدد المخاطر قبل أي خطوة.",
                "نبدأ بتحليل خفيف بدون تغييرات.",
                "نطلع اقتراحات آمنة فقط.",
            ]
        if risk == "aggressive":
            return [
                "نبدأ تحليل شامل مع اقتراحات أوسع.",
                "نجهز خطة تعديل أكبر لكن تحت التأكيد.",
                "نشتغل على أكثر النقاط تأثيرًا بسرعة.",
            ]
        return [
            "نعمل تحليل سريع ونحدد الأولويات.",
            "نطلع اقتراحات معقولة بدون مخاطرة.",
            "نبدأ بخطوة صغيرة ونقيّم النتيجة.",
        ]

    def _explain_suggestion(self, message: str, state: Any) -> str:
        import re

        if not state:
            return ""
        m = re.search(r"(?:اقتراح|suggestion)\s*#?\s*(\d+)", message, re.IGNORECASE)
        if not m:
            return ""
        try:
            idx = int(m.group(1))
        except (TypeError, ValueError):
            return ""
        suggestions = getattr(state, "suggestions", None) or []
        if idx < 1 or idx > len(suggestions):
            return "مش لاقي الاقتراح ده."
        s = suggestions[idx - 1]
        lines = [
            f"ليه الاقتراح #{idx}: {s.get('title')}",
            f"السبب: {s.get('rationale') or s.get('reason') or ''}",
        ]
        evidence = s.get("evidence") or []
        if evidence:
            lines.append("أدلة:")
            for ev in evidence[:5]:
                line = f"- {ev.get('path')}"
                if ev.get("line"):
                    line += f":{ev.get('line')}"
                if ev.get("excerpt"):
                    line += f" - {ev.get('excerpt')}"
                lines.append(line)
        return "\n".join(lines)

    def _action_from_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        action = {"type": intent.get("intent"), "description": ""}
        if intent.get("intent") == "analyze":
            action["description"] = "Analyze the current project"
        elif intent.get("intent") == "search":
            action["description"] = "Find task-marker hotspots in the project"
        elif intent.get("intent") == "verify":
            action["description"] = "Run verification checks"
        elif intent.get("intent") == "plan":
            goal = intent.get("goal") or ""
            action["description"] = "Plan fixes" + (f" for: {goal}" if goal else "")
            action["goal"] = goal
        elif intent.get("intent") == "apply":
            diff_path = intent.get("diff_path") or ""
            action["description"] = "Apply planned diff" + (f": {diff_path}" if diff_path else "")
            action["diff_path"] = diff_path
        elif intent.get("intent") == "pipeline":
            goal = intent.get("goal") or ""
            action["description"] = "Run pipeline" + (f" for: {goal}" if goal else "")
            action["goal"] = goal
        elif intent.get("intent") == "execute":
            num = intent.get("number") or ""
            action["description"] = f"Execute suggestion {num}"
            action["number"] = num
        else:
            return {}
        return action

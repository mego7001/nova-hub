from __future__ import annotations
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import inspect
import hashlib

from core.chat.state import ChatState
from core.chat.intents import parse_intent, extract_goal, extract_diff_path
from core.security.secrets import SecretsManager
from core.reporting.writer import ReportWriter
from core.security import required_secrets
from core.security.status import get_key_status
from core.assistant.suggestions import build_suggestions
from core.assistant.executor import pick_suggestion, suggestion_goal, init_status, update_status
from core.projects.manager import ProjectManager
from core.ingest.index_store import IndexStore
from core.analyze.dependency_graph import build_dependency_graph
from core.analyze.entrypoints import detect_entrypoints
from core.analyze.risk import score_risks
from core.conversation.prefs import load_prefs
from core.retrieval.search import search_index
from core.plugin_engine.registry import PluginRegistry
from core.plugin_engine.loader import PluginLoader
from core.permission_guard.tool_policy import ToolPolicy
from core.permission_guard.approval_flow import ApprovalFlow
from core.task_engine.runner import Runner
from core.tooling.invoker import InvokeContext, invoke_tool
from core.system_state_machine import SystemStateMachine, TransitionEvidence, PolicyFailure
from core.audit_spine import AuditSpine, ProjectAuditSpine
from core.records.record_store import RecordStore, DecisionRecord, RunRecord
from core.language.normalization import normalize_input
from core.conversation import jarvis_core

_ALLOWED_KEYS = {
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_DEFAULT_CHAT_ID",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
}


class ChatOrchestrator:
    def __init__(self, project_root: str, runner: Runner, registry: PluginRegistry):
        self.project_root = project_root
        self.runner = runner
        self.registry = registry
        self.secrets = SecretsManager(workspace_root=os.environ.get("NH_WORKSPACE"))
        self.writer = ReportWriter(runner, registry, workspace_root=os.environ.get("NH_WORKSPACE"), base_dir=project_root)
        self.projects = ProjectManager(os.environ.get("NH_WORKSPACE"))
        self._state_machine: Optional[SystemStateMachine] = None
        self._active_state: Optional[ChatState] = None
        self._active_session_id: Optional[str] = None
        self._records: Optional[RecordStore] = None
        self._current_intent_id: str = ""
        self._current_decision_id: str = ""
        self._current_run_id: str = ""
        self._audit: Optional[AuditSpine] = None

    def handle_message(
        self,
        user_message: str,
        project_path: str,
        session_id: str = "default",
        write_reports: bool = True,
    ) -> Dict[str, Any]:
        state = self._load_state(session_id)
        self._active_state = state
        self._active_session_id = session_id
        if state.system_state == "blocked":
            response = "System blocked by policy failure. Operator reset required."
            return self._finalize(session_id, state, [], SecretsManager.redact_text(user_message), response, write_reports)
        if project_path:
            state.project_path = project_path

        actions: List[Dict[str, Any]] = []
        user_redacted = SecretsManager.redact_text(user_message)
        norm = normalize_input(user_message)

        # Secret onboarding
        extracted = self._extract_keys(user_message)
        if extracted:
            state.pending_secret_values.update(extracted)
            response = (
                "I detected API keys. Choose one:\n"
                "- Reply 'save' to store them in .env (requires approval)\n"
                "- Reply 'session' to use only for this session"
            )
            return self._finalize(session_id, state, actions, user_redacted, response, write_reports)

        if state.pending_secret_values:
            low = norm.normalized_input.lower()
            if "save" in low:
                try:
                    self._save_secrets_via_tool(state.pending_secret_values)
                    response = "Saved keys to workspace secrets."
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                    response = f"Failed to save secrets: {e}"
                state.pending_secret_values = {}
            elif "session" in low or "use" in low:
                for k, v in state.pending_secret_values.items():
                    self.secrets.set_temp(k, v)
                state.session_secrets = list(state.pending_secret_values.keys())
                state.pending_secret_values = {}
                response = "Using keys for this session only."
            else:
                response = "Reply with 'save' to store in .env or 'session' to use only for this session."
            return self._finalize(session_id, state, actions, user_redacted, response, write_reports)

        if "save keys" in norm.normalized_input.lower() or "Ø§Ø­ÙØ¸ Ø§Ù„Ù…ÙØ§ØªÙŠØ­" in norm.normalized_input.lower():
            mem = self.secrets.temp_keys()
            if not mem:
                response = "No keys in memory to save."
                return self._finalize(session_id, state, actions, user_redacted, response, write_reports)
            try:
                self._save_secrets_via_tool(mem)
                response = f"Saved {len(mem)} keys to workspace secrets."
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                response = f"Failed to save secrets: {e}"
            return self._finalize(session_id, state, actions, user_redacted, response, write_reports)

        # Ensure project
        if not state.project_path:
            response = "Please select a project folder first."
            return self._finalize(session_id, state, actions, user_redacted, response, write_reports)

        intent = parse_intent(norm.normalized_input)
        low = norm.normalized_input.lower()
        self._records = RecordStore(self._records_dir())
        self._current_intent_id = self._make_intent_id(session_id)
        self._current_decision_id = ""
        self._current_run_id = ""
        self._audit = AuditSpine(session_id, self._records_dir())
        self._audit.emit(
            "intent_captured",
            {
                "input": user_redacted,
                "detected_languages": norm.detected_languages,
                "input_style": norm.input_style,
            },
            intent_id=self._current_intent_id,
        )
        self._state_machine = SystemStateMachine("idle")
        try:
            self._transition_state(state, "intake")
            self._transition_state(state, "analysis")
        except PolicyFailure as e:
            state.system_state = "blocked"
            response = f"Policy failure: {e}"
            return self._finalize(session_id, state, actions, user_redacted, response, write_reports)

        if state.awaiting_goal:
            goal = user_message.strip()
            intent = {"intent": state.awaiting_goal, "goal": goal}
            state.awaiting_goal = None

        if state.pending_apply_diff_path:
            if low in ("y", "yes", "apply", "apply yes", "Ù†Ø¹Ù…"):
                intent = {
                    "intent": "apply",
                    "diff_path": state.pending_apply_diff_path,
                    "confirmed": True,
                    "suggestion_number": state.pending_apply_suggestion,
                }
            elif low in ("n", "no", "cancel", "Ù„Ø§"):
                response = "Okay, not applying any diff."
                state.pending_apply_diff_path = ""
                state.pending_apply_suggestion = None
                return self._finalize(session_id, state, actions, user_redacted, response, write_reports)
            else:
                response = "Reply 'yes' to apply or 'no' to cancel."
                return self._finalize(session_id, state, actions, user_redacted, response, write_reports)

        response_lines: List[str] = []

        if intent["intent"] == "unknown":
            explain = self._explain_suggestion(user_message, state)
            if explain:
                response_lines.append(explain)
                return self._finalize(session_id, state, actions, user_redacted, "\n".join(response_lines), write_reports)

        if intent["intent"] == "set_project":
            p = intent.get("project_path") or state.project_path
            if p:
                state.project_path = p
                response_lines.append(f"Project set to: {p}")
            else:
                response_lines.append("Please provide a project path.")

        elif intent["intent"] == "analyze":
            try:
                decision_ref = self._make_decision_ref(intent, state)
                self._transition_state(state, "executing", TransitionEvidence(decision_ref=decision_ref))
                scan_res = self._run_tool("project.scan_repo", root_path=state.project_path, write_reports=True)
                actions.append(self._action("project.scan_repo", scan_res))
                state.scanned = True
                search_res = self._run_tool("repo.search", root_path=state.project_path, query=None, write_reports=True)
                actions.append(self._action("repo.search", search_res))
                state.searched = True
                artifact_ref = self._artifact_ref_from_result(search_res) or self._artifact_ref_from_result(scan_res)
                self._transition_state(state, "verifying", TransitionEvidence(artifact_ref=artifact_ref))
                verify_res = self._run_tool("verify.smoke", target_root=state.project_path, write_reports=True)
                actions.append(self._action("verify.smoke", verify_res))
                state.verified = self._verify_passed(verify_res)
                verdict = "pass" if state.verified else "fail"
                self._emit_timeline(session_id, state.project_path, "verify.result", {"verdict": verdict})
                if self._audit:
                    self._audit.emit(
                        "verification_completed",
                        {"verdict": verdict},
                        intent_id=self._current_intent_id,
                        decision_id=self._current_decision_id,
                        run_id=self._current_run_id,
                    )
                if state.verified:
                    self._transition_state(state, "completed", TransitionEvidence(verification_verdict=verdict))
                    self._jarvis_maybe_remind(session_id, state.project_path, response_lines)
                else:
                    self._transition_state(state, "failed", TransitionEvidence(verification_verdict=verdict))
                    self._jarvis_record_failure(session_id, state.project_path, "verify_failed", response_lines)

                doc_index = self._load_doc_index(state.project_path)
                prefs = self._load_prefs_from_path(state.project_path)
                suggestions = build_suggestions(scan_res, search_res, verify_res, doc_index, risk_posture=prefs.get("risk_posture", "balanced"))
                state.suggestions = suggestions
                state.suggestion_status = self._init_suggestion_status(suggestions, state.suggestion_status)
                risks = score_risks(state.project_path, search_res)
                entrypoints = detect_entrypoints(state.project_path)
                deps = build_dependency_graph(state.project_path)
                response_lines.append(self._summarize_scan(scan_res))
                response_lines.append(self._summarize_search(search_res))
                response_lines.append(self._summarize_verify(verify_res))
                response_lines.append(self._summarize_risks(risks))
                response_lines.append(self._summarize_entrypoints(entrypoints))
                response_lines.append(self._summarize_subsystems(deps))
                response_lines.append(self._summarize_quick_wins(suggestions))
                response_lines.append(self._format_suggestions(suggestions))
                response_lines.append("Next: type 'Ù†ÙÙ‘Ø° 1' or 'apply 1' to execute a suggestion.")
            except PolicyFailure:
                raise
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                actions.append(self._action_error("analyze", e))
                response_lines.append(f"Analyze failed: {e}")

        elif intent["intent"] == "scan":
            try:
                res = self._run_tool("project.scan_repo", root_path=state.project_path, write_reports=True)
                actions.append(self._action("project.scan_repo", res))
                state.scanned = True
                state.last_scan_paths = res.get("report_paths") or []
                response_lines.append(self._summarize_scan(res))
                response_lines.append("Next: run 'search' or 'plan'.")
            except PolicyFailure:
                raise
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                actions.append(self._action_error("project.scan_repo", e))
                response_lines.append(f"Scan failed: {e}")

        elif intent["intent"] == "search":
            try:
                res = self._run_tool("repo.search", root_path=state.project_path, query=None, write_reports=True)
                actions.append(self._action("repo.search", res))
                state.searched = True
                response_lines.append(self._summarize_search(res))
                response_lines.append("Next: run 'plan' with a goal.")
            except PolicyFailure:
                raise
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                actions.append(self._action_error("repo.search", e))
                response_lines.append(f"Search failed: {e}")

        elif intent["intent"] == "plan":
            goal = intent.get("goal") or ""
            if not goal:
                state.awaiting_goal = "plan"
                self._transition_state(state, "awaiting_clarification")
                response_lines.append("What is the goal for the fix plan?")
            else:
                try:
                    res = self._run_tool("patch.plan", target_root=state.project_path, goal=goal, max_files=10, write_reports=True)
                    actions.append(self._action("patch.plan", res))
                    state.planned = True
                    state.last_diff_path = res.get("diff_path") or ""
                    response_lines.append(self._summarize_plan(res))
                    response_lines.append("Next: type 'apply' to apply the diff or 'verify'.")
                except PolicyFailure:
                    raise
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                    actions.append(self._action_error("patch.plan", e))
                    response_lines.append(f"Planning failed: {e}")

        elif intent["intent"] == "apply":
            diff_path = intent.get("diff_path") or state.last_diff_path
            if not diff_path:
                response_lines.append("No diff found. Provide a .diff path.")
            else:
                if not intent.get("confirmed"):
                    self._transition_state(state, "awaiting_approval")
                    state.pending_apply_diff_path = diff_path
                    if intent.get("suggestion_number"):
                        try:
                            state.pending_apply_suggestion = int(intent.get("suggestion_number"))
                        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                            state.pending_apply_suggestion = None
                    response_lines.append(f"Apply diff {diff_path}? Reply 'yes' to confirm.")
                else:
                    try:
                        decision_ref = self._make_decision_ref(intent, state)
                        self._transition_state(state, "executing", TransitionEvidence(decision_ref=decision_ref))
                        res = self._run_tool("patch.apply", diff_path=diff_path, target_root=state.project_path, write_reports=True)
                        actions.append(self._action("patch.apply", res))
                        self._emit_timeline(session_id, state.project_path, "patch.apply.result", {"status": "ok", "diff_path": diff_path})
                        response_lines.append(self._summarize_apply(res))
                        # verify after apply when triggered by suggestion
                        if intent.get("suggestion_number"):
                            artifact_ref = self._artifact_ref_from_result(res)
                            self._transition_state(state, "verifying", TransitionEvidence(artifact_ref=artifact_ref))
                            vres = self._run_tool("verify.smoke", target_root=state.project_path, write_reports=True)
                            actions.append(self._action("verify.smoke", vres))
                            response_lines.append(self._summarize_verify(vres))
                            verdict = "pass" if self._verify_passed(vres) else "fail"
                            self._emit_timeline(session_id, state.project_path, "verify.result", {"verdict": verdict})
                            if self._audit:
                                self._audit.emit(
                                    "verification_completed",
                                    {"verdict": verdict},
                                    intent_id=self._current_intent_id,
                                    decision_id=self._current_decision_id,
                                    run_id=self._current_run_id,
                                )
                            if verdict == "pass":
                                self._transition_state(state, "completed", TransitionEvidence(verification_verdict=verdict))
                                self._jarvis_maybe_remind(session_id, state.project_path, response_lines)
                            else:
                                self._transition_state(state, "failed", TransitionEvidence(verification_verdict=verdict))
                                self._jarvis_record_failure(session_id, state.project_path, "verify_failed", response_lines)
                            self._update_suggestion_status(
                                state,
                                int(intent.get("suggestion_number")),
                                "applied" if self._verify_passed(vres) else "failed",
                                diff_path=diff_path,
                                error=None if self._verify_passed(vres) else "verify failed",
                            )
                        else:
                            # generic apply without suggestion
                            pass
                    except PolicyFailure:
                        raise
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                        actions.append(self._action_error("patch.apply", e))
                        response_lines.append(f"Apply failed: {e}")
                        self._emit_timeline(session_id, state.project_path, "patch.apply.result", {"status": "error", "error": str(e), "diff_path": diff_path})
                        self._jarvis_record_failure(session_id, state.project_path, "patch_apply_failed", response_lines)
                        if intent.get("suggestion_number"):
                            self._update_suggestion_status(state, int(intent.get("suggestion_number")), "failed", diff_path=diff_path, error=str(e))
                    finally:
                        state.pending_apply_diff_path = ""
                        state.pending_apply_suggestion = None

        elif intent["intent"] == "verify":
            try:
                decision_ref = self._make_decision_ref(intent, state)
                self._transition_state(state, "executing", TransitionEvidence(decision_ref=decision_ref))
                artifact_ref = state.last_diff_path or (state.last_reports[0] if state.last_reports else "")
                self._transition_state(state, "verifying", TransitionEvidence(artifact_ref=artifact_ref))
                res = self._run_tool("verify.smoke", target_root=state.project_path, write_reports=True)
                actions.append(self._action("verify.smoke", res))
                state.verified = self._verify_passed(res)
                verdict = "pass" if state.verified else "fail"
                self._emit_timeline(session_id, state.project_path, "verify.result", {"verdict": verdict})
                if self._audit:
                    self._audit.emit(
                        "verification_completed",
                        {"verdict": verdict},
                        intent_id=self._current_intent_id,
                        decision_id=self._current_decision_id,
                        run_id=self._current_run_id,
                    )
                if state.verified:
                    self._transition_state(state, "completed", TransitionEvidence(verification_verdict=verdict))
                    self._jarvis_maybe_remind(session_id, state.project_path, response_lines)
                else:
                    self._transition_state(state, "failed", TransitionEvidence(verification_verdict=verdict))
                    self._jarvis_record_failure(session_id, state.project_path, "verify_failed", response_lines)
                response_lines.append(self._summarize_verify(res))
            except PolicyFailure:
                raise
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                actions.append(self._action_error("verify.smoke", e))
                response_lines.append(f"Verify failed: {e}")
                self._jarvis_record_failure(session_id, state.project_path, "verify_failed", response_lines)

        elif intent["intent"] == "execute":
            try:
                num = int(intent.get("number") or 0)
                suggestion = pick_suggestion(state.suggestions or [], num)
                goal = suggestion_goal(suggestion)
                if not goal:
                    response_lines.append("Suggestion has no goal; cannot execute.")
                else:
                    res = self._run_tool("patch.plan", target_root=state.project_path, goal=goal, max_files=10, write_reports=True)
                    actions.append(self._action("patch.plan", res))
                    state.planned = True
                    state.last_diff_path = res.get("diff_path") or ""
                    response_lines.append(self._summarize_plan(res))
                    if state.last_diff_path:
                        self._transition_state(state, "awaiting_approval")
                        state.pending_apply_diff_path = state.last_diff_path
                        state.pending_apply_suggestion = num
                        self._update_suggestion_status(state, num, "diff_ready", diff_path=state.last_diff_path, error=None)
                        response_lines.append(f"Confirm apply for {state.last_diff_path}? Reply 'yes' to apply.")
            except PolicyFailure:
                raise
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                actions.append(self._action_error("execute", e))
                if intent.get("number"):
                    try:
                        self._update_suggestion_status(state, int(intent.get("number")), "failed", diff_path="", error=str(e))
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        pass
                response_lines.append(f"Execute failed: {e}")

        elif intent["intent"] == "pipeline":
            goal = intent.get("goal") or ""
            apply_diff = "apply" in low or "Ã˜ÂªÃ˜Â·Ã˜Â¨Ã™Å Ã™â€š" in low
            if not goal:
                state.awaiting_goal = "pipeline"
                self._transition_state(state, "awaiting_clarification")
                response_lines.append("What is the pipeline goal?")
            else:
                try:
                    decision_ref = self._make_decision_ref(intent, state)
                    self._transition_state(state, "executing", TransitionEvidence(decision_ref=decision_ref))
                    res = self._run_tool("pipeline.run", target_root=state.project_path, goal=goal, apply_diff=apply_diff, write_reports=True)
                    actions.append(self._action("pipeline.run", res))
                    artifact_ref = self._artifact_ref_from_result(res)
                    self._transition_state(state, "verifying", TransitionEvidence(artifact_ref=artifact_ref))
                    verdict = "pass" if str(res.get("final_verdict") or "").upper() == "PASS" else "fail"
                    self._emit_timeline(session_id, state.project_path, "pipeline.result", {"verdict": verdict})
                    if self._audit:
                        self._audit.emit(
                            "verification_completed",
                            {"verdict": verdict},
                            intent_id=self._current_intent_id,
                            decision_id=self._current_decision_id,
                            run_id=self._current_run_id,
                        )
                    if verdict == "pass":
                        self._transition_state(state, "completed", TransitionEvidence(verification_verdict=verdict))
                        self._jarvis_maybe_remind(session_id, state.project_path, response_lines)
                    else:
                        self._transition_state(state, "failed", TransitionEvidence(verification_verdict=verdict))
                        self._jarvis_record_failure(session_id, state.project_path, "pipeline_failed", response_lines)
                    response_lines.append("Pipeline completed. See reports/pipeline_run.*")
                except PolicyFailure:
                    raise
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                    actions.append(self._action_error("pipeline.run", e))
                    response_lines.append(f"Pipeline failed: {e}")
                    self._jarvis_record_failure(session_id, state.project_path, "pipeline_failed", response_lines)
        elif intent["intent"] == "help" or intent["intent"] == "unknown":
            response_lines.append("Try: analyze, scan, search, plan <goal>, apply, verify, pipeline <goal>, Ù†ÙÙ‘Ø° 1")

        response = "\n".join([line for line in response_lines if line]).strip() or "(no response)"

        state.last_recommendations = self._recommendations_from_response(response_lines)
        state.last_reports = self._extract_reports(actions)
        state.last_artifacts = self._extract_artifacts(actions)
        if actions:
            self._write_session_latest(state, actions)

        return self._finalize(session_id, state, actions, user_redacted, response, write_reports)


    def _records_dir(self) -> str:
        path = self._report_path("decision_records.json")
        return os.path.dirname(path)

    def _persist_blocked_state(self) -> None:
        if not self._active_state:
            return
        self._active_state.system_state = "blocked"
        try:
            sid = self._active_session_id or self._active_state.session_id
            self._save_state(sid, self._active_state)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _transition_state(self, state: ChatState, next_state: str, evidence: Optional[TransitionEvidence] = None) -> None:
        if self._state_machine is None:
            self._persist_blocked_state()
            raise PolicyFailure("Policy failure: state machine missing", "unknown", next_state, "state_machine_missing")
        try:
            ev = evidence or TransitionEvidence()
            if next_state == "executing":
                if not self._records or not self._records.has_decision(ev.decision_ref or ""):
                    if self._audit:
                        self._audit.emit(
                            "policy_failure",
                            {"reason": "missing_decision_record"},
                            intent_id=self._current_intent_id,
                            decision_id=ev.decision_ref,
                            run_id=self._current_run_id,
                        )
                    self._persist_blocked_state()
                    raise PolicyFailure("Policy failure: missing decision record", state.system_state or "analysis", next_state, "missing_decision_record")
                self._current_decision_id = ev.decision_ref or ""
                self._current_run_id = self._start_run(state, self._current_decision_id)
            if next_state == "verifying":
                if not self._current_run_id or not self._records or not self._records.has_artifact(self._current_run_id, ev.artifact_ref or ""):
                    if self._audit:
                        self._audit.emit(
                            "policy_failure",
                            {"reason": "missing_artifact_record"},
                            intent_id=self._current_intent_id,
                            decision_id=self._current_decision_id,
                            run_id=self._current_run_id,
                        )
                    self._persist_blocked_state()
                    raise PolicyFailure("Policy failure: missing artifact record", state.system_state or "executing", next_state, "missing_artifact_record")
            self._state_machine.transition(next_state, evidence)
            state.system_state = self._state_machine.state
            if self._audit and next_state in ("failed", "completed"):
                self._audit.emit(
                    "run_failed" if next_state == "failed" else "run_completed",
                    {"state": next_state},
                    intent_id=self._current_intent_id,
                    decision_id=self._current_decision_id,
                    run_id=self._current_run_id,
                )
        except PolicyFailure:
            state.system_state = "blocked"
            self._persist_blocked_state()
            raise

    def _make_intent_id(self, session_id: str) -> str:
        return f"intent:{session_id}:{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"

    def _make_decision_ref(self, intent: Dict[str, Any], state: ChatState) -> str:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        tag = str(intent.get("intent") or "unknown")
        decision_id = f"decision:{state.session_id}:{tag}:{ts}"
        if not self._records:
            self._records = RecordStore(self._records_dir())
        rec = DecisionRecord(
            decision_id=decision_id,
            mission_id=state.session_id,
            intent_id=self._current_intent_id or self._make_intent_id(state.session_id),
            operator_id="operator",
            decision_type="execute" if tag not in ("verify", "clarify") else tag,
            decision_outcome="approved",
            recorded_at=ts,
        )
        self._records.add_decision(rec)
        if self._audit:
            self._audit.emit(
                "decision_recorded",
                {"decision_type": rec.decision_type, "decision_outcome": rec.decision_outcome},
                intent_id=rec.intent_id,
                decision_id=rec.decision_id,
            )
        return decision_id

    def _start_run(self, state: ChatState, decision_id: str) -> str:
        run_id = f"run:{state.session_id}:{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}"
        if not self._records:
            self._records = RecordStore(self._records_dir())
        rec = RunRecord(
            run_id=run_id,
            mission_id=state.session_id,
            intent_id=self._current_intent_id or self._make_intent_id(state.session_id),
            decision_id=decision_id,
            run_phase="execution",
            run_state="executing",
            started_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        self._records.add_run(rec)
        if self._audit:
            self._audit.emit(
                "run_started",
                {"run_phase": rec.run_phase, "run_state": rec.run_state},
                intent_id=rec.intent_id,
                decision_id=rec.decision_id,
                run_id=rec.run_id,
            )
        return run_id

    def _artifact_ref_from_result(self, result: Any) -> str:
        if not isinstance(result, dict):
            return ""
        if isinstance(result.get("artifact_ref"), str) and result.get("artifact_ref"):
            return str(result.get("artifact_ref"))
        for key in ("diff_path", "out_dxf", "out_file"):
            val = result.get(key)
            if isinstance(val, str) and val:
                return val
        rp = result.get("report_paths")
        if isinstance(rp, list) and rp:
            return str(rp[0])
        return ""

    def _register_artifacts_from_result(self, result: Any) -> str:
        if not isinstance(result, dict):
            return ""
        if not self._records or not self._current_run_id:
            return ""
        primary = ""
        artifact_ref = result.get("artifact_ref")
        if isinstance(artifact_ref, str) and artifact_ref:
            self._records.add_artifact(self._current_run_id, artifact_ref)
            primary = artifact_ref
            if self._audit:
                self._audit.emit(
                    "artifact_registered",
                    {"artifact_ref": artifact_ref, "fingerprint": _fingerprint(artifact_ref)},
                    intent_id=self._current_intent_id,
                    decision_id=self._current_decision_id,
                    run_id=self._current_run_id,
                )
        rp = result.get("report_paths")
        if isinstance(rp, list):
            for p in rp:
                if isinstance(p, str) and p:
                    self._records.add_artifact(self._current_run_id, p)
                    if not primary:
                        primary = p
                    if self._audit:
                        self._audit.emit(
                            "artifact_registered",
                            {"artifact_ref": p, "fingerprint": _fingerprint(p)},
                            intent_id=self._current_intent_id,
                            decision_id=self._current_decision_id,
                            run_id=self._current_run_id,
                        )
        for key in ("diff_path", "out_dxf", "out_file"):
            val = result.get(key)
            if isinstance(val, str) and val:
                self._records.add_artifact(self._current_run_id, val)
                if not primary:
                    primary = val
                if self._audit:
                    self._audit.emit(
                        "artifact_registered",
                        {"artifact_ref": val, "fingerprint": _fingerprint(val)},
                        intent_id=self._current_intent_id,
                        decision_id=self._current_decision_id,
                        run_id=self._current_run_id,
                    )
        if primary and not result.get("artifact_ref"):
            result["artifact_ref"] = primary
        return primary

    def _missing_keys_for_tool(self, tool_id: str) -> list[str]:
        required = required_secrets.required_keys_for_tool(tool_id)
        status = get_key_status(self.secrets, required)
        return [k for k, v in status.items() if v != "present"]

    def _run_tool(self, tool_id: str, **kwargs) -> Dict[str, Any]:
        try:
            if self._state_machine is None:
                raise PolicyFailure("Policy failure: state machine missing", "unknown", "executing", "state_machine_missing")
            if self._state_machine.state not in ("analysis", "executing", "verifying"):
                self._state_machine.block("tool_execution_not_allowed", attempted_state="executing")
            if self._state_machine.state == "executing":
                if not self._current_run_id or not self._records or not self._records.has_run(self._current_run_id):
                    self._state_machine.block("missing_run_record", attempted_state="executing")
        except PolicyFailure as err:
            if self._audit:
                self._audit.emit(
                    "policy_failure",
                    {"reason": err.reason, "attempted_state": err.attempted_state},
                    intent_id=self._current_intent_id,
                    decision_id=self._current_decision_id,
                    run_id=self._current_run_id,
                )
            self._persist_blocked_state()
            raise
        missing = self._missing_keys_for_tool(tool_id)
        if missing:
            raise PermissionError("Missing keys: " + ", ".join(missing) + ". Import api.txt to continue.")
        tool = self.registry.tools.get(tool_id)
        if not tool:
            raise ValueError(f"Tool not found: {tool_id}")
        sig = inspect.signature(tool.handler)
        accepts_target = "target" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        clean = dict(kwargs)
        explicit_target = clean.pop("target", None)
        target = explicit_target or clean.get("target_root") or tool.default_target
        if self._audit:
            self._audit.emit(
                "tool_invoked",
                {"tool_id": tool.tool_id, "tool_group": tool.tool_group, "target": target},
                intent_id=self._current_intent_id,
                decision_id=self._current_decision_id,
                run_id=self._current_run_id,
            )
        session_id = self._active_session_id or ""
        project_path = self._active_state.project_path if self._active_state else ""
        self._emit_timeline(
            session_id,
            project_path,
            "tool.start",
            {"tool_id": tool.tool_id, "tool_group": tool.tool_group, "target": target},
        )
        project_id = os.path.basename(os.path.normpath(project_path)) if project_path else ""
        invoke_ctx = InvokeContext(
            runner=self.runner,
            registry=self.registry,
            session_id=session_id,
            project_id=project_id,
            mode="",
        )

        try:
            if accepts_target:
                result = invoke_tool(tool_id, {**clean, "target": target}, invoke_ctx)
                if self._state_machine and self._state_machine.state == "executing":
                    self._register_artifacts_from_result(result)
                self._emit_timeline(session_id, project_path, "tool.finish", {"tool_id": tool.tool_id, "status": "ok"})
                return result

            if target is not None:
                original_target = tool.default_target
                tool.default_target = target
                try:
                    result = invoke_tool(tool_id, clean, invoke_ctx)
                    if self._state_machine and self._state_machine.state == "executing":
                        self._register_artifacts_from_result(result)
                    self._emit_timeline(session_id, project_path, "tool.finish", {"tool_id": tool.tool_id, "status": "ok"})
                    return result
                finally:
                    tool.default_target = original_target

            result = invoke_tool(tool_id, clean, invoke_ctx)
            if self._state_machine and self._state_machine.state == "executing":
                self._register_artifacts_from_result(result)
            self._emit_timeline(session_id, project_path, "tool.finish", {"tool_id": tool.tool_id, "status": "ok"})
            return result
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            self._emit_timeline(session_id, project_path, "tool.finish", {"tool_id": tool.tool_id, "status": "error", "error": str(e)})
            raise

    def _save_secrets_via_tool(self, values: Dict[str, str]) -> None:
        env_path = self.secrets.env_path
        content = self.secrets._update_env_content(values)
        self._run_tool("fs.write_text", path=env_path, text=content, target=env_path)
        for k, v in values.items():
            self.secrets.set_temp(k, v)

    def _extract_keys(self, message: str) -> Dict[str, str]:
        found: Dict[str, str] = {}
        for line in message.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("\"").strip("'")
            if k in _ALLOWED_KEYS and v:
                found[k] = v
        return found

    def _finalize(self, session_id: str, state: ChatState, actions: List[Dict[str, Any]], user_redacted: str, response: str, write_reports: bool) -> Dict[str, Any]:
        if self._state_machine is not None:
            state.system_state = self._state_machine.state
        if write_reports:
            self._append_transcript(session_id, "User", user_redacted)
            self._append_transcript(session_id, "Nova", response)
            self._save_state(session_id, state)
            report_paths = [self._report_path(f"chat_transcript_{session_id}.md")]
        else:
            report_paths = []
        return {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "session_id": session_id,
            "project_path": state.project_path,
            "response": response,
            "actions": actions,
            "state": state.to_status(),
            "display_user_message": user_redacted,
            "report_paths": report_paths,
        }

    def _resolve_project_id(self, session_id: str, project_path: str) -> Optional[str]:
        if session_id:
            ws_root = self.projects.workspace_root
            direct = os.path.join(ws_root, "projects", session_id)
            if os.path.isdir(direct):
                return session_id
        if project_path:
            ws_root = self.projects.workspace_root
            root = os.path.abspath(os.path.join(ws_root, "projects"))
            abs_path = os.path.abspath(project_path)
            if abs_path.startswith(root + os.sep):
                rel = os.path.relpath(abs_path, root)
                parts = rel.split(os.sep)
                if parts:
                    return parts[0]
        return None

    def _load_jarvis_context(self, session_id: str, project_path: str) -> Tuple[Dict[str, Any], Optional[str], Any]:
        project_id = self._resolve_project_id(session_id, project_path)
        if not project_id:
            return {"jarvis": {}}, None, None
        try:
            state = self.projects.load_state(project_id)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return {"jarvis": {}}, project_id, None
        jarvis = dict(getattr(state, "jarvis", {}) or {})
        return {"jarvis": jarvis}, project_id, state

    def _persist_jarvis_context(self, project_id: Optional[str], state: Any, ctx: Dict[str, Any]) -> None:
        if not project_id or state is None:
            return
        state.jarvis = dict((ctx or {}).get("jarvis") or {})
        try:
            self.projects.save_state(project_id, state)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _timeline(self, session_id: str, project_path: str) -> Optional[ProjectAuditSpine]:
        project_id = self._resolve_project_id(session_id, project_path)
        if not project_id:
            return None
        try:
            return ProjectAuditSpine(project_id, workspace_root=self.projects.workspace_root)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return None

    def _emit_timeline(self, session_id: str, project_path: str, event_type: str, payload: Dict[str, Any]) -> None:
        spine = self._timeline(session_id, project_path)
        if not spine:
            return
        try:
            spine.emit(event_type, payload)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _jarvis_record_failure(self, session_id: str, project_path: str, failure_type: str, response_lines: List[str]) -> None:
        ctx, project_id, pstate = self._load_jarvis_context(session_id, project_path)
        jarvis_core.update_last_outcome(ctx, failure_type, resolved=False)
        plan, _ = jarvis_core.recovery_mode(ctx, {"type": failure_type})
        if plan:
            response_lines.append(plan)
        self._persist_jarvis_context(project_id, pstate, ctx)

    def _jarvis_maybe_remind(self, session_id: str, project_path: str, response_lines: List[str]) -> None:
        ctx, project_id, pstate = self._load_jarvis_context(session_id, project_path)
        jarvis = dict((ctx or {}).get("jarvis") or {})
        last = jarvis.get("last_outcome") or {}
        if not last or last.get("resolved"):
            return
        _, reminder = jarvis_core.recovery_mode(ctx, {"type": last.get("type")})
        if reminder:
            response_lines.append(reminder)
        jarvis_core.update_last_outcome(ctx, str(last.get("type") or "unknown"), resolved=True)
        self._persist_jarvis_context(project_id, pstate, ctx)

    def _load_state(self, session_id: str) -> ChatState:
        path = self._report_path(f"chat_sessions/{session_id}.json", prefer_existing=True)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return ChatState.from_dict(session_id, data)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                return ChatState(session_id=session_id)
        return ChatState(session_id=session_id)

    def _save_state(self, session_id: str, state: ChatState) -> None:
        self.writer.write_report_json(f"chat_sessions/{session_id}.json", state.to_persisted(), redact=SecretsManager.redact_text)

    def _append_transcript(self, session_id: str, role: str, text: str) -> None:
        path = self._report_path(f"chat_transcript_{session_id}.md", prefer_existing=True)
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        existing = ""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = f.read()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                existing = ""
        block = f"## {ts} - {role}\n{text}\n\n"
        self.writer.write_report_md(f"chat_transcript_{session_id}.md", existing + block, redact=SecretsManager.redact_text)

    def _write_session_latest(self, state: ChatState, actions: List[Dict[str, Any]]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "project_path": state.project_path,
            "status": state.to_status(),
            "actions": actions,
        }
        self.writer.write_report_json("session_latest.json", payload, redact=SecretsManager.redact_text)

        lines = []
        lines.append("# Session Latest")
        lines.append("")
        lines.append(f"Project: {state.project_path}")
        lines.append("")
        lines.append("## Actions")
        for a in actions:
            lines.append(f"- {a.get('tool_id')}: {a.get('status')}")
        lines.append("")
        lines.append("## Status")
        s = state.to_status()
        lines.append(f"- scanned: {s['scanned']}")
        lines.append(f"- searched: {s['searched']}")
        lines.append(f"- planned: {s['planned']}")
        lines.append(f"- diff_ready: {s['diff_ready']}")
        lines.append(f"- verified: {s['verified']}")
        self.writer.write_report_md("session_latest.md", "\n".join(lines) + "\n", redact=SecretsManager.redact_text)

    def _report_path(self, rel: str, prefer_existing: bool = False) -> str:
        ws = os.environ.get("NH_WORKSPACE")
        candidates = []
        if ws:
            candidates.append(os.path.join(ws, "reports", rel))
        candidates.append(os.path.join(self.project_root, "reports", rel))
        if prefer_existing:
            for p in candidates:
                if os.path.exists(p):
                    return p
        return candidates[0]

    def _action(self, tool_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"tool_id": tool_id, "status": "success", "result": self._summarize_result(result)}

    def _action_error(self, tool_id: str, error: Exception) -> Dict[str, Any]:
        return {"tool_id": tool_id, "status": "failed", "error": str(error)}

    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {"value": str(result)}
        summary: Dict[str, Any] = {}
        for k in ["report_paths", "diff_path", "selected_files", "totals", "results", "files", "stats", "languages", "entrypoints", "dependency_manifests", "hotspots"]:
            if k in result:
                summary[k] = result.get(k)
        return summary

    def _summarize_scan(self, res: Dict[str, Any]) -> str:
        stats = res.get("stats") or {}
        languages = res.get("languages") or {}
        entries = res.get("entrypoints") or []
        manifests = res.get("dependency_manifests") or []
        return (
            f"Scan complete. Files: {stats.get('file_count', 0)}, LOC~ {stats.get('loc_estimate', 0)}.\n"
            f"Entrypoints: {', '.join(entries[:5]) or '(none)'}\n"
            f"Manifests: {', '.join(manifests[:5]) or '(none)'}\n"
            f"Languages: {', '.join(list(languages.keys())[:5]) or '(none)'}"
        )

    def _summarize_search(self, res: Dict[str, Any]) -> str:
        total = res.get("total_matches", 0)
        hotspots = (res.get("hotspots") or {}).get("files_with_most_hits") or []
        top = [f"{h.get('path')} ({h.get('hits')})" for h in hotspots[:3]]
        return f"Search done. Matches: {total}. Top files: {', '.join(top) or '(none)'}"

    def _summarize_plan(self, res: Dict[str, Any]) -> str:
        diff_path = res.get("diff_path") if isinstance(res, dict) else None
        selected = res.get("selected_files") if isinstance(res, dict) else None
        count = len(selected) if isinstance(selected, list) else 0
        return f"Plan ready. Diff: {diff_path or '(none)'}; files: {count}"

    def _summarize_apply(self, res: Dict[str, Any]) -> str:
        totals = (res.get("totals") or {}) if isinstance(res, dict) else {}
        return f"Apply done. Success: {totals.get('success_count', 0)}, Failed: {totals.get('failed_count', 0)}"

    def _summarize_verify(self, res: Dict[str, Any]) -> str:
        totals = (res.get("totals") or {}) if isinstance(res, dict) else {}
        failed = totals.get("failed_count", 0)
        return "Verify passed." if failed == 0 else f"Verify failed: {failed} checks"

    def _verify_passed(self, res: Dict[str, Any]) -> bool:
        totals = (res.get("totals") or {}) if isinstance(res, dict) else {}
        return totals.get("failed_count", 0) == 0

    def _extract_reports(self, actions: List[Dict[str, Any]]) -> List[str]:
        paths: List[str] = []
        for a in actions:
            res = a.get("result") or {}
            if isinstance(res, dict):
                rp = res.get("report_paths")
                if isinstance(rp, list):
                    paths.extend([str(p) for p in rp])
        return paths

    def _extract_artifacts(self, actions: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        artifacts = {"reports": [], "patches": [], "outputs": []}
        for a in actions:
            res = a.get("result") or {}
            if isinstance(res, dict):
                if res.get("report_paths"):
                    artifacts["reports"].extend([str(p) for p in res.get("report_paths")])
                if res.get("diff_path"):
                    artifacts["patches"].append(str(res.get("diff_path")))
                if res.get("out_dxf"):
                    artifacts["outputs"].append(str(res.get("out_dxf")))
        return artifacts

    def _recommendations_from_response(self, response_lines: List[str]) -> List[str]:
        recs = []
        for line in response_lines:
            if line.lower().startswith("next:"):
                recs.append(line)
        return recs

    def _load_doc_index(self, project_path: str) -> List[Dict[str, Any]]:
        try:
            # project_path is working/; index is at project root
            proj_root = os.path.dirname(project_path.rstrip(os.sep))
            index_path = os.path.join(proj_root, "index.json")
            return IndexStore(index_path).load()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return []

    def _format_suggestions(self, suggestions: List[Dict[str, Any]]) -> str:
        if not suggestions:
            return "Suggestions: (none)"
        lines = ["Suggestions:"]
        for idx, s in enumerate(suggestions, 1):
            title = s.get("title") or "Suggestion"
            reason = s.get("rationale") or s.get("reason") or ""
            evidence = s.get("evidence") or []
            ev_text = f" evidence: {len(evidence)} item(s)" if evidence else ""
            if reason:
                lines.append(f"{idx}) {title} - {reason}{ev_text}")
            else:
                lines.append(f"{idx}) {title}{ev_text}")
        return "\n".join(lines)

    def _summarize_risks(self, risks: List[Dict[str, Any]]) -> str:
        if not risks:
            return "Risks: (none)"
        top = risks[:5]
        lines = ["Key risks:"]
        for r in top:
            lines.append(f"- {r.get('file')} (score {r.get('score')}): {', '.join(r.get('reasons') or [])}")
        return "\n".join(lines)

    def _summarize_entrypoints(self, entrypoints: List[Dict[str, str]]) -> str:
        if not entrypoints:
            return "Entrypoints: (none)"
        top = entrypoints[:5]
        items = ", ".join([e.get("path") for e in top if e.get("path")])
        return f"Entrypoints: {items}"

    def _summarize_subsystems(self, deps: Dict[str, List[str]]) -> str:
        if not deps:
            return "Subsystems: (none)"
        subsystems: Dict[str, int] = {}
        for path in deps.keys():
            top = path.split(os.sep)[0] if path else "root"
            subsystems[top] = subsystems.get(top, 0) + 1
        top = sorted(subsystems.items(), key=lambda x: x[1], reverse=True)[:5]
        return "Subsystems: " + ", ".join([f"{k}({v})" for k, v in top])

    def _summarize_quick_wins(self, suggestions: List[Dict[str, Any]]) -> str:
        if not suggestions:
            return "Quick wins: (none)"
        wins = []
        for s in suggestions:
            risk = str(s.get("risk") or "").lower()
            effort = str(s.get("effort") or "").lower()
            if risk in ("low", "") and effort in ("low", "medium", ""):
                wins.append(s)
            if len(wins) >= 5:
                break
        if not wins:
            wins = suggestions[:5]
        return "Quick wins: " + ", ".join([w.get("title") or "Suggestion" for w in wins])

    def _explain_suggestion(self, message: str, state: ChatState) -> Optional[str]:
        import re
        m = re.search(r"(?:Ø§Ù‚ØªØ±Ø§Ø­|suggestion)\\s*#?\\s*(\\d+)", message, re.IGNORECASE)
        if not m:
            return None
        try:
            idx = int(m.group(1))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return None
        if idx < 1 or idx > len(state.suggestions or []):
            return "Suggestion not found."
        s = state.suggestions[idx - 1]
        lines = [
            f"Suggestion #{idx}: {s.get('title')}",
            f"Rationale: {s.get('rationale') or s.get('reason') or ''}",
        ]
        evidence = s.get("evidence") or []
        if evidence:
            lines.append("Evidence:")
            for ev in evidence[:5]:
                line = f"- {ev.get('path')}"
                if ev.get("line"):
                    line += f":{ev.get('line')}"
                if ev.get("excerpt"):
                    line += f" â€” {ev.get('excerpt')}"
                lines.append(line)
        return "\n".join(lines)

    def _load_prefs_from_path(self, project_path: str) -> Dict[str, Any]:
        try:
            project_id = self._project_id_from_path(project_path)
            if not project_id:
                return {}
            prefs = load_prefs(project_id, os.environ.get("NH_WORKSPACE"))
            return prefs.to_dict()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return {}

    def _project_id_from_path(self, project_path: str) -> Optional[str]:
        if not project_path:
            return None
        parts = project_path.replace("\\", "/").split("/")
        if "projects" in parts:
            idx = parts.index("projects")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return None

    def _init_suggestion_status(self, suggestions: List[Dict[str, Any]], existing: Dict[str, Any]) -> Dict[str, Any]:
        status = init_status(suggestions, existing)
        # preserve last_run_at if provided
        for key, entry in status.items():
            if isinstance(existing, dict) and isinstance(existing.get(key), dict):
                entry["last_run_at"] = existing.get(key).get("last_run_at") or ""
        return status

    def _update_suggestion_status(self, state: ChatState, number: int, status: str, diff_path: str = "", error: Optional[str] = None) -> None:
        if state.suggestion_status is None:
            state.suggestion_status = {}
        state.suggestion_status = update_status(state.suggestion_status, number, status, diff_path=diff_path, error=error)
        state.suggestion_status[str(number)]["last_run_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OrchestratorFactory:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self._orchestrators: Dict[str, ChatOrchestrator] = {}

    def get(self, runner: Runner, registry: PluginRegistry) -> ChatOrchestrator:
        key = f"{id(runner)}:{id(registry)}"
        if key not in self._orchestrators:
            self._orchestrators[key] = ChatOrchestrator(self.project_root, runner, registry)
        return self._orchestrators[key]


def build_default_runner(project_root: str) -> Tuple[Runner, PluginRegistry]:
    profile = os.environ.get("NH_PROFILE", "engineering")
    tool_policy = ToolPolicy(os.path.join(project_root, "configs", "tool_policy.yaml"), active_profile=profile)
    approvals = ApprovalFlow(tool_policy, os.path.join(project_root, "configs", "approvals.yaml"))
    runner = Runner(approval_flow=approvals, approval_callback=_approval_callback)

    reg = PluginRegistry()
    PluginLoader(project_root).load_enabled(os.path.join(project_root, "configs", "plugins_enabled.yaml"), reg)
    return runner, reg


def _approval_callback(req, res):
    print("\n=== APPROVAL REQUIRED ===")
    print("ToolGroup:", req.tool_group)
    print("Op:", req.op)
    print("Target:", req.target)
    print("Reason:", res.reason)
    print("Risk:", res.risk_score)
    ans = input("Approve? (y/n): ").strip().lower()
    return ans == "y"


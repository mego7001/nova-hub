from __future__ import annotations
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.jobs.models import Job, JobArtifacts
from core.jobs.storage import JobStorage
from core.projects.manager import ProjectManager
from core.system_state_machine import SystemStateMachine, TransitionEvidence, PolicyFailure
from core.records.record_store import RecordStore, DecisionRecord, RunRecord
from core.conversation import jarvis_core
from core.audit_spine import ProjectAuditSpine
from core.tooling.invoker import InvokeContext, invoke_tool


class JobController:
    def __init__(self, runner, registry, approval_flow, workspace_root: Optional[str] = None):
        self.runner = runner
        self.registry = registry
        self.approval_flow = approval_flow
        self.storage = JobStorage(workspace_root)
        self.project_manager = ProjectManager(workspace_root)
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def enqueue_job(self, project_id: str, title: str, recipe: str, options: Optional[Dict[str, Any]] = None) -> Job:
        job_id = uuid.uuid4().hex
        now = _now()
        steps = self._build_steps(recipe, options or {})
        job = Job(
            job_id=job_id,
            project_id=project_id,
            title=title,
            created_at=now,
            updated_at=now,
            status="queued",
            steps_total=len(steps),
            steps_done=0,
            current_step_label="",
            last_safe_point_label="",
            last_safe_point_at="",
            pause_requested=False,
            preview_requested=False,
            last_error=None,
            artifacts=JobArtifacts(),
            log_tail=[],
            recipe=recipe,
            recipe_options=options or {},
            next_step_index=0,
            cancel_requested=False,
        )
        self._log(job, f"Enqueued job: {title}")
        self.storage.save_job(job)
        self._emit_timeline(project_id, "job.created", {"job_id": job_id, "title": title, "recipe": recipe})
        return job

    def start_job(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        if job.status in ("running", "waiting_for_user", "waiting_for_approval"):
            return
        t = threading.Thread(target=self._run_job, args=(job.project_id, job.job_id), daemon=True)
        self._threads[job.job_id] = t
        t.start()
        self._emit_timeline(project_id, "job.started", {"job_id": job_id, "title": job.title})

    def pause_job(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        job.pause_requested = True
        job.updated_at = _now()
        self._log(job, "Pause requested")
        self.storage.save_job(job)
        self._emit_timeline(project_id, "job.pause_requested", {"job_id": job_id})

    def resume_job(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        if job.status == "paused":
            job.pause_requested = False
            job.status = "running"
            job.updated_at = _now()
            self._log(job, "Resuming job")
            self.storage.save_job(job)
            self._emit_timeline(project_id, "job.resumed", {"job_id": job_id})
            self.start_job(project_id, job_id)

    def cancel_job(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        job.cancel_requested = True
        job.updated_at = _now()
        self._log(job, "Cancel requested")
        self.storage.save_job(job)
        self._emit_timeline(project_id, "job.cancel_requested", {"job_id": job_id})


    def confirm_apply(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        if job.status != "waiting_for_user" or job.waiting_reason != "confirm_apply" or not job.pending_diff_path:
            return
        self._emit_timeline(project_id, "job.confirm_apply", {"job_id": job_id, "diff_path": job.pending_diff_path})
        job.status = "waiting_for_approval"
        job.updated_at = _now()
        self._log(job, "User confirmed apply")
        self.storage.save_job(job)

        try:
            sm = SystemStateMachine("idle")
            sm.transition("intake")
            sm.transition("analysis")
            paths = self.project_manager.get_project_paths(job.project_id)
            store = RecordStore(paths.reports)
            decision_ref = f"decision:job:{job.job_id}:{_now()}"
            store.add_decision(DecisionRecord(
                decision_id=decision_ref,
                mission_id=job.project_id,
                intent_id=f"intent:job:{job.job_id}",
                operator_id="operator",
                decision_type="execute",
                decision_outcome="approved",
                recorded_at=_now(),
            ))
            sm.transition("executing", TransitionEvidence(decision_ref=decision_ref))
            run_id = f"run:job:{job.job_id}:{_now()}"
            store.add_run(RunRecord(
                run_id=run_id,
                mission_id=job.project_id,
                intent_id=f"intent:job:{job.job_id}",
                decision_id=decision_ref,
                run_phase="execution",
                run_state="executing",
                started_at=_now(),
            ))
            if not store.has_run(run_id):
                raise PolicyFailure("Policy failure: missing run record", "executing", "executing", "missing_run_record")

            res_apply = self._apply_diff(job, job.pending_diff_path)
            if isinstance(res_apply, dict):
                self._update_artifacts(job, res_apply)
            self._emit_timeline(job.project_id, "patch.apply.result", {"status": "ok", "diff_path": job.pending_diff_path})
            artifact_ref = ""
            if isinstance(res_apply, dict):
                artifact_ref = str(res_apply.get("artifact_ref") or res_apply.get("diff_path") or "")
                if not artifact_ref and res_apply.get("report_paths"):
                    rp = res_apply.get("report_paths")
                    if isinstance(rp, list) and rp:
                        artifact_ref = str(rp[0])
            if artifact_ref:
                store.add_artifact(run_id, artifact_ref)
            if not store.has_artifact(run_id, artifact_ref):
                raise PolicyFailure("Policy failure: missing artifact record", "executing", "verifying", "missing_artifact_record")
            sm.transition("verifying", TransitionEvidence(artifact_ref=artifact_ref))

            res_verify = self._run_verify(job)
            if isinstance(res_verify, dict):
                self._update_artifacts(job, res_verify)
            verdict = "pass" if self._verify_passed(res_verify) else "fail"
            self._emit_timeline(job.project_id, "verify.result", {"verdict": verdict})
            if verdict == "pass":
                sm.transition("completed", TransitionEvidence(verification_verdict=verdict))
            else:
                sm.transition("failed", TransitionEvidence(verification_verdict=verdict))

            if not self._verify_passed(res_verify):
                job.status = "failed"
                job.last_error = "verify failed"
                self._emit_recovery(job, "verify_failed")
                if job.pending_suggestion_n:
                    self._update_project_suggestion(job.project_id, job.pending_suggestion_n, "failed", diff_path=job.pending_diff_path or "")
            else:
                job.status = "running"
                if job.pending_suggestion_n:
                    self._update_project_suggestion(job.project_id, job.pending_suggestion_n, "applied", diff_path=job.pending_diff_path or "")
            job.waiting_reason = None
            job.pending_diff_path = None
            job.pending_suggestion_n = None
            job.updated_at = _now()
            self.storage.save_job(job)
        except PolicyFailure as e:
            job.status = "failed"
            job.last_error = str(e)
            job.updated_at = _now()
            self._log(job, f"Apply blocked: {e}")
            self._emit_timeline(project_id, "patch.apply.result", {"status": "error", "error": str(e)})
            self.storage.save_job(job)
            return
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            job.status = "failed"
            job.last_error = str(e)
            job.updated_at = _now()
            self._log(job, f"Apply failed: {e}")
            self._emit_timeline(project_id, "patch.apply.result", {"status": "error", "error": str(e)})
            self._emit_recovery(job, "patch_apply_failed")
            self.storage.save_job(job)
            return

        if job.cancel_requested:
            job.status = "cancelled"
            self._log(job, "Cancelled after apply")
            self.storage.save_job(job)
            return

        # continue job
        if job.status == "running":
            self.start_job(project_id, job_id)

    def skip_pending(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        if job.status != "waiting_for_user" or job.waiting_reason != "confirm_apply":
            return
        pending_suggestion_n = job.pending_suggestion_n
        self._emit_timeline(project_id, "job.skip_apply", {"job_id": job_id})
        job.waiting_reason = None
        job.pending_diff_path = None
        job.pending_suggestion_n = None
        job.status = "running"
        job.updated_at = _now()
        if pending_suggestion_n:
            self._update_project_suggestion(job.project_id, pending_suggestion_n, "ready", diff_path="")
        self._log(job, "Skipped pending apply")
        self.storage.save_job(job)
        self.start_job(project_id, job_id)

    def stop_job(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        if job.status in ("waiting_for_user", "paused"):
            job.status = "cancelled"
            job.updated_at = _now()
            self._log(job, "Job cancelled")
            self.storage.save_job(job)
            self._emit_timeline(project_id, "job.stopped", {"job_id": job_id})
            return
        job.cancel_requested = True
        job.updated_at = _now()
        self._log(job, "Cancel requested")
        self.storage.save_job(job)
        self._emit_timeline(project_id, "job.stop_requested", {"job_id": job_id})

    def request_preview(self, project_id: str, job_id: str) -> None:
        job = self.storage.load_job(project_id, job_id)
        job.preview_requested = True
        job.updated_at = _now()
        self._log(job, "Preview requested")
        self.storage.save_job(job)
        self._emit_timeline(project_id, "job.preview_requested", {"job_id": job_id})

    def list_jobs(self, project_id: str) -> List[Dict[str, Any]]:
        return self.storage.list_jobs(project_id)

    def get_job(self, project_id: str, job_id: str) -> Job:
        return self.storage.load_job(project_id, job_id)

    def _run_job(self, project_id: str, job_id: str) -> None:
        with self._lock:
            job = self.storage.load_job(project_id, job_id)
            if job.status == "cancelled":
                return
            job.status = "running"
            job.updated_at = _now()
            self._log(job, "Job started")
            self.storage.save_job(job)

        steps = self._build_steps(job.recipe, job.recipe_options)

        while job.next_step_index < len(steps):
            step = steps[job.next_step_index]

            if job.cancel_requested:
                job.status = "cancelled"
                self._log(job, "Job cancelled")
                self._emit_timeline(project_id, "job.cancelled", {"job_id": job_id})
                break

            if job.pause_requested:
                job.status = "paused"
                self._log(job, "Paused at safe point")
                self._emit_timeline(project_id, "job.paused", {"job_id": job_id})
                break

            if job.preview_requested:
                job.preview_requested = False
                job.status = "paused"
                job.current_step_label = "Preview requested"
                job.last_safe_point_label = job.current_step_label
                job.last_safe_point_at = _now()
                self._log(job, "Preview requested; paused at safe point")
                self._emit_timeline(project_id, "job.preview_pause", {"job_id": job_id})
                break

            job.current_step_label = step["label"]
            job.updated_at = _now()
            self.storage.save_job(job)

            try:
                if step.get("requires_approval"):
                    job.status = "waiting_for_approval"
                    self._log(job, f"Waiting for approval: {step['label']}")
                    self.storage.save_job(job)
                result = step["action"](job)
                if isinstance(result, dict):
                    self._update_artifacts(job, result)

                job.steps_done += 1
                job.next_step_index += 1
                job.last_safe_point_label = step["label"]
                job.last_safe_point_at = _now()
                job.status = "running"
                self._log(job, f"Completed: {step['label']}")

                if step.get("wait_for_user"):
                    job.status = "waiting_for_user"
                    job.waiting_reason = "confirm_apply"
                    job.pending_diff_path = self._extract_pending_diff(result)
                    job.pending_suggestion_n = self._extract_pending_suggestion(result)
                    self._log(job, "Waiting for user confirmation")
                    self.storage.save_job(job)
                    self._emit_timeline(project_id, "job.wait_confirm", {"job_id": job_id, "diff_path": job.pending_diff_path})
                    break

            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                job.status = "failed"
                job.last_error = str(e)
                self._log(job, f"Failed: {e}")
                self._emit_timeline(project_id, "job.failed", {"job_id": job_id, "error": str(e)})
                break

            self.storage.save_job(job)

        if job.status == "running" and job.next_step_index >= len(steps):
            job.status = "completed"
            self._log(job, "Job completed")
            self._emit_timeline(project_id, "job.completed", {"job_id": job_id})

        job.updated_at = _now()
        self.storage.save_job(job)

    def _build_steps(self, recipe: str, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        if recipe == "quick_fix":
            steps.append({"label": "Analyze", "action": lambda job: self._chat(job, "analyze"), "requires_approval": True})
        elif recipe == "auto_improve":
            max_suggestions = int(options.get("max_suggestions") or 3)
            steps.append({"label": "Analyze", "action": lambda job: self._chat(job, "analyze"), "requires_approval": True})
            for i in range(1, max_suggestions + 1):
                steps.append({
                    "label": f"Plan suggestion {i}",
                    "action": lambda job, n=i: self._chat(job, f"نفّذ {n}"),
                    "wait_for_user": True,
                })
        elif recipe == "pipeline":
            goal = str(options.get("goal") or "Pipeline run")
            steps.append({"label": "Pipeline", "action": lambda job: self._chat(job, f"pipeline goal: {goal}"), "requires_approval": True})
        else:
            steps.append({"label": "Analyze", "action": lambda job: self._chat(job, "analyze")})
        return steps

    def _chat(self, job: Job, message: str) -> Dict[str, Any]:
        tool = self.registry.tools.get("conversation.chat")
        if not tool:
            raise RuntimeError("conversation.chat tool missing")
        return invoke_tool(
            "conversation.chat",
            {
                "user_message": message,
                "project_path": self._project_working(job.project_id),
                "session_id": job.project_id,
                "write_reports": True,
            },
            InvokeContext(
                runner=self.runner,
                registry=self.registry,
                session_id=job.project_id,
                project_id=job.project_id,
                mode="",
            ),
        )

    def _project_working(self, project_id: str) -> str:
        # Construct from workspace root; caller already uses workspace-only
        return os.path.join(self.storage.workspace_root, "projects", project_id, "working")

    def _update_artifacts(self, job: Job, result: Dict[str, Any]) -> None:
        state = result.get("state") if isinstance(result, dict) else None
        if isinstance(state, dict):
            job.artifacts.last_diff_path = str(state.get("last_diff_path") or job.artifacts.last_diff_path)
        actions = result.get("actions") if isinstance(result, dict) else None
        if isinstance(actions, list):
            for a in actions:
                res = a.get("result") or {}
                if res.get("diff_path"):
                    job.artifacts.last_diff_path = str(res.get("diff_path"))
                if res.get("report_paths"):
                    for rp in res.get("report_paths"):
                        if "patch_plan" in str(rp):
                            job.artifacts.last_plan_report = str(rp)
                        if "patch_apply" in str(rp):
                            job.artifacts.last_apply_report = str(rp)
                        if "verify_smoke" in str(rp):
                            job.artifacts.last_verify_report = str(rp)


    def _extract_pending_diff(self, result: Dict[str, Any]) -> str:
        if isinstance(result, dict):
            state = result.get("state")
            if isinstance(state, dict):
                return str(state.get("pending_apply_diff_path") or state.get("last_diff_path") or "")
            res_actions = result.get("actions")
            if isinstance(res_actions, list):
                for a in res_actions:
                    r = a.get("result") or {}
                    if r.get("diff_path"):
                        return str(r.get("diff_path"))
        return ""

    def _extract_pending_suggestion(self, result: Dict[str, Any]) -> Optional[int]:
        if isinstance(result, dict):
            state = result.get("state")
            if isinstance(state, dict):
                try:
                    return int(state.get("pending_apply_suggestion") or 0) or None
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    return None
        return None

    def _apply_diff(self, job: Job, diff_path: str) -> Dict[str, Any]:
        tool = self.registry.tools.get("patch.apply")
        if not tool:
            raise RuntimeError("patch.apply tool missing")
        return invoke_tool(
            "patch.apply",
            {
                "diff_path": diff_path,
                "target_root": self._project_working(job.project_id),
                "write_reports": True,
            },
            InvokeContext(
                runner=self.runner,
                registry=self.registry,
                session_id=job.project_id,
                project_id=job.project_id,
                mode="",
            ),
        )

    def _run_verify(self, job: Job) -> Dict[str, Any]:
        tool = self.registry.tools.get("verify.smoke")
        if not tool:
            raise RuntimeError("verify.smoke tool missing")
        return invoke_tool(
            "verify.smoke",
            {
                "target_root": self._project_working(job.project_id),
                "write_reports": True,
            },
            InvokeContext(
                runner=self.runner,
                registry=self.registry,
                session_id=job.project_id,
                project_id=job.project_id,
                mode="",
            ),
        )

    def _update_project_suggestion(self, project_id: str, number: int, status: str, diff_path: str = "") -> None:
        try:
            state = self.project_manager.load_state(project_id)
            if not hasattr(state, "suggestion_status"):
                return
            if not isinstance(state.suggestion_status, dict):
                state.suggestion_status = {}
            entry = state.suggestion_status.get(str(number)) or {}
            entry["status"] = status
            if diff_path:
                entry["last_diff_path"] = diff_path
            state.suggestion_status[str(number)] = entry
            self.project_manager.save_state(project_id, state)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _verify_passed(self, res: Dict[str, Any]) -> bool:
        totals = (res.get("totals") or {}) if isinstance(res, dict) else {}
        return totals.get("failed_count", 0) == 0

    def _emit_recovery(self, job: Job, failure_type: str) -> None:
        ctx = {"jarvis": {}}
        state = None
        try:
            state = self.project_manager.load_state(job.project_id)
            ctx["jarvis"] = dict(getattr(state, "jarvis", {}) or {})
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            state = None
        jarvis_core.update_last_outcome(ctx, failure_type, resolved=False)
        plan, _ = jarvis_core.recovery_mode(ctx, {"type": failure_type})
        if plan:
            self._log(job, f"Recovery: {plan}")
        if state is not None:
            state.jarvis = dict((ctx or {}).get("jarvis") or {})
            try:
                self.project_manager.save_state(job.project_id, state)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                pass

    def _emit_timeline(self, project_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        try:
            spine = ProjectAuditSpine(project_id, workspace_root=self.storage.workspace_root)
            spine.emit(event_type, payload)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def _log(self, job: Job, line: str) -> None:
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        entry = f"{ts} {line}"
        job.log_tail.append(entry)
        if len(job.log_tail) > 200:
            job.log_tail = job.log_tail[-200:]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")




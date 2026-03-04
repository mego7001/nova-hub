from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from core.llm.ollama_config import load_ollama_settings, pick_ollama_model
from core.llm.online_policy import OnlineDecision, decide_online
from core.llm.selection_policy import fallback_order, load_llm_routing_config
from core.llm.selector import WeightedProviderSelector
from core.security.secrets import SecretsManager
from core.telemetry.queries import llm_token_usage
from core.telemetry.recorders import TelemetryRecorder, classify_error_kind
from core.tooling.invoker import InvokeContext, invoke_tool


class LLMRouter:
    def __init__(
        self,
        runner=None,
        registry=None,
        config: Optional[Dict[str, Any]] = None,
        *,
        selector: Optional[WeightedProviderSelector] = None,
        telemetry_recorder: Optional[TelemetryRecorder] = None,
        profile: str = "",
    ):
        self.runner = runner
        self.registry = registry
        self.config = config or {}
        self.routing_config = load_llm_routing_config()
        self.selector = selector
        self.telemetry_recorder = telemetry_recorder
        self.profile = str(profile or self.config.get("profile") or os.environ.get("NH_PROFILE") or "").strip()
        self.ollama_settings = load_ollama_settings()

        self.task_map = {
            "conversation": self._default_provider(),
            "summarize_docs": "gemini",
            "deep_reasoning": "deepseek",
            "patch_planning": "auto",
            "vision": "ollama",
        }
        configured_task_map = self._router_cfg().get("task_map")
        if isinstance(configured_task_map, dict):
            for key, value in configured_task_map.items():
                k = str(key or "").strip().lower()
                v = str(value or "").strip().lower()
                if k and v:
                    self.task_map[k] = v

        runtime_task_map = self.config.get("task_map")
        runtime_task_map_keys: set[str] = set()
        if isinstance(runtime_task_map, dict):
            for key, value in runtime_task_map.items():
                k = str(key or "").strip().lower()
                v = str(value or "").strip().lower()
                if k and v:
                    self.task_map[k] = v
                    runtime_task_map_keys.add(k)

        if ("conversation" not in runtime_task_map_keys) and (
            str(self.config.get("default_provider") or "").strip() or str(os.environ.get("NH_DEFAULT_LLM") or "").strip()
        ):
            self.task_map["conversation"] = self._default_provider()

        configured_fallbacks = self._router_cfg().get("fallbacks")
        if isinstance(configured_fallbacks, list):
            self.fallbacks = [str(item or "").strip().lower() for item in configured_fallbacks if str(item or "").strip()]
        else:
            self.fallbacks = fallback_order("general")
        if not self.fallbacks:
            self.fallbacks = ["deepseek", "gemini", "openai", "ollama"]

        router_cfg = self._router_cfg()
        self.local_first = _coerce_bool(
            self.config.get("local_first"),
            _coerce_bool(router_cfg.get("local_first"), True),
        )
        self.external_backup_only = _coerce_bool(
            self.config.get("external_backup_only"),
            _coerce_bool(router_cfg.get("external_backup_only"), True),
        )

        self.task_model_map: Dict[str, str] = {}
        configured_task_model_map = router_cfg.get("task_model_map")
        if isinstance(configured_task_model_map, dict):
            for key, value in configured_task_model_map.items():
                k = str(key or "").strip().lower()
                v = str(value or "").strip()
                if k and v:
                    self.task_model_map[k] = v
        runtime_task_model_map = self.config.get("task_model_map")
        if isinstance(runtime_task_model_map, dict):
            for key, value in runtime_task_model_map.items():
                k = str(key or "").strip().lower()
                v = str(value or "").strip()
                if k and v:
                    self.task_model_map[k] = v

    def route(
        self,
        task_type: str,
        prompt: str,
        system: Optional[str] = None,
        online_enabled: bool = False,
        project_id: str = "",
        offline_confidence: str = "high",
        extracted_text_len: int = 0,
        parser_ok: bool = True,
        plan_ok: bool = True,
        goal_complex: Optional[bool] = None,
        mode: str = "general",
        request_kind: str = "",
        session_id: str = "",
        images: Optional[List[str]] = None,
        model_override: str = "",
    ) -> Dict[str, Any]:
        task = str(task_type or "").strip().lower() or "conversation"
        req_kind = str(request_kind or task or "chat").strip().lower() or "chat"
        selected_mode = str(mode or "general").strip().lower() or "general"

        provider = self._pick_provider(task)
        order = self._build_provider_order(provider)
        if self.local_first:
            order = self._with_ollama_first(order)

        selected_provider = None
        ollama_model = self._provider_model(
            "ollama",
            task_type=task,
            mode=selected_mode,
            request_kind=req_kind,
            is_vision=bool(images),
            model_override=model_override,
        )

        routing_meta: Dict[str, Any] = {
            "task_type": task,
            "mode": selected_mode,
            "request_kind": req_kind,
            "provider_preference": provider,
            "initial_order": list(order),
            "selector": {},
            "decision": {},
            "final_order": [],
            "attempts": [],
            "token_budget": {},
            "local_policy": {
                "local_first": bool(self.local_first),
                "external_backup_only": bool(self.external_backup_only),
            },
            "local_models": {
                "ollama_selected_model": ollama_model,
            },
        }

        decision: OnlineDecision = decide_online(
            task_type=task,
            user_msg=prompt,
            offline_confidence=offline_confidence,
            extracted_text_len=extracted_text_len,
            parser_ok=parser_ok,
            plan_ok=plan_ok,
            goal_complex=goal_complex,
        )
        routing_meta["decision"] = {
            "need_online": bool(decision.need_online),
            "reason": str(decision.reason or ""),
        }

        redacted_prompt = SecretsManager.redact_text(prompt)
        redacted_system = SecretsManager.redact_text(system or "")
        chars = len(redacted_prompt)
        tokens_est = max(1, chars // 4)

        if not decision.need_online:
            if self._ollama_enabled() and self.runner and self.registry and "ollama" in self._with_ollama_first(self._build_provider_order("ollama")):
                started = time.perf_counter()
                try:
                    out = self._call_provider(
                        "ollama",
                        redacted_prompt,
                        redacted_system,
                        purpose=task,
                        project_id=project_id,
                        chars=chars,
                        tokens_est=tokens_est,
                        online_reason=decision.reason,
                        images=images,
                        model_override=ollama_model,
                        timeout_sec=90,
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    text_out = str(out.get("text") or "")
                    output_tokens = max(0, len(text_out) // 4)
                    out["latency_ms"] = latency_ms
                    if self.telemetry_recorder is not None:
                        self.telemetry_recorder.record_llm_call(
                            session_id=session_id,
                            project_id=project_id,
                            mode=selected_mode,
                            provider="ollama",
                            model=str(out.get("model") or ollama_model),
                            profile=self.profile,
                            request_kind=req_kind,
                            input_tokens=tokens_est,
                            output_tokens=output_tokens,
                            cost_usd=0.0,
                            latency_ms=latency_ms,
                            status="ok",
                        )
                    routing_meta["attempts"].append(
                        {
                            "provider": "ollama",
                            "model": str(out.get("model") or ollama_model),
                            "status": "ok",
                            "latency_ms": latency_ms,
                            "error": "",
                        }
                    )
                    out["_routing"] = routing_meta
                    return out
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    routing_meta["attempts"].append(
                        {
                            "provider": "ollama",
                            "model": ollama_model,
                            "status": "error",
                            "latency_ms": latency_ms,
                            "error": str(exc),
                        }
                    )
                    if self.telemetry_recorder is not None:
                        self.telemetry_recorder.record_llm_call(
                            session_id=session_id,
                            project_id=project_id,
                            mode=selected_mode,
                            provider="ollama",
                            model=ollama_model,
                            profile=self.profile,
                            request_kind=req_kind,
                            input_tokens=tokens_est,
                            output_tokens=0,
                            cost_usd=None,
                            latency_ms=latency_ms,
                            status="error",
                            error_kind=classify_error_kind(exc),
                            error_msg=str(exc),
                        )

            offline_out = {
                "mode": "offline",
                "provider": "local",
                "text": "",
                "raw": None,
                "used_fallback": True,
                "error": None,
                "need_online": False,
                "reason": decision.reason,
            }
            offline_out["_routing"] = routing_meta
            return offline_out

        if not online_enabled or not self.runner or not self.registry:
            if self._ollama_enabled() and self.runner and self.registry and "ollama" in self._with_ollama_first(order):
                started = time.perf_counter()
                try:
                    out = self._call_provider(
                        "ollama",
                        redacted_prompt,
                        redacted_system,
                        purpose=task,
                        project_id=project_id,
                        chars=chars,
                        tokens_est=tokens_est,
                        online_reason=decision.reason,
                        images=images,
                        model_override=ollama_model,
                        timeout_sec=90,
                    )
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    text_out = str(out.get("text") or "")
                    output_tokens = max(0, len(text_out) // 4)
                    out["latency_ms"] = latency_ms
                    if self.telemetry_recorder is not None:
                        self.telemetry_recorder.record_llm_call(
                            session_id=session_id,
                            project_id=project_id,
                            mode=selected_mode,
                            provider="ollama",
                            model=str(out.get("model") or ollama_model),
                            profile=self.profile,
                            request_kind=req_kind,
                            input_tokens=tokens_est,
                            output_tokens=output_tokens,
                            cost_usd=0.0,
                            latency_ms=latency_ms,
                            status="ok",
                        )
                    routing_meta["attempts"].append(
                        {
                            "provider": "ollama",
                            "model": str(out.get("model") or ollama_model),
                            "status": "ok",
                            "latency_ms": latency_ms,
                            "error": "",
                        }
                    )
                    out["_routing"] = routing_meta
                    return out
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    routing_meta["attempts"].append(
                        {
                            "provider": "ollama",
                            "model": ollama_model,
                            "status": "error",
                            "latency_ms": latency_ms,
                            "error": str(exc),
                        }
                    )
                    if self.telemetry_recorder is not None:
                        self.telemetry_recorder.record_llm_call(
                            session_id=session_id,
                            project_id=project_id,
                            mode=selected_mode,
                            provider="ollama",
                            model=ollama_model,
                            profile=self.profile,
                            request_kind=req_kind,
                            input_tokens=tokens_est,
                            output_tokens=0,
                            cost_usd=None,
                            latency_ms=latency_ms,
                            status="error",
                            error_kind=classify_error_kind(exc),
                            error_msg=str(exc),
                        )
            offline_out = {
                "mode": "offline",
                "provider": "local",
                "text": f"Online AI is required for this request ({decision.reason}). Enable Online AI to proceed.",
                "raw": None,
                "used_fallback": True,
                "error": None,
                "need_online": True,
                "reason": decision.reason,
            }
            offline_out["_routing"] = routing_meta
            return offline_out

        if self.selector and order:
            try:
                if self.local_first and self.external_backup_only and "ollama" in order:
                    backup_candidates = [p for p in order if p != "ollama"]
                    if backup_candidates:
                        picked = self.selector.pick_provider(
                            mode=selected_mode,
                            request_kind=req_kind,
                            candidates=list(backup_candidates),
                            profile=self.profile,
                        )
                        routing_meta["selector"] = {"backup": picked}
                        selected_provider = str(picked.get("provider") or "").strip().lower()
                        if selected_provider in backup_candidates:
                            order = ["ollama", selected_provider] + [p for p in backup_candidates if p != selected_provider]
                        else:
                            order = ["ollama"] + backup_candidates
                else:
                    picked = self.selector.pick_provider(
                        mode=selected_mode,
                        request_kind=req_kind,
                        candidates=list(order),
                        profile=self.profile,
                    )
                    routing_meta["selector"] = picked
                    selected_provider = str(picked.get("provider") or "").strip().lower()
                    if selected_provider:
                        order = [selected_provider] + [p for p in order if p != selected_provider]
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                selected_provider = None
        routing_meta["final_order"] = list(order)

        budget = self._budget_status(session_id=session_id, planned_input_tokens=tokens_est)
        routing_meta["token_budget"] = budget
        if bool(budget.get("blocked")):
            offline_out = {
                "mode": "offline",
                "provider": "local",
                "text": str(budget.get("message") or "Token budget exceeded."),
                "raw": None,
                "used_fallback": True,
                "error": None,
                "need_online": True,
                "reason": "token budget exceeded",
            }
            offline_out["_routing"] = routing_meta
            return offline_out

        last_error = None
        for p in order:
            started = time.perf_counter()
            provider_model = self._provider_model(
                p,
                task_type=task,
                mode=selected_mode,
                request_kind=req_kind,
                is_vision=bool(images),
                model_override=model_override if p == "ollama" else "",
            )
            attempt: Dict[str, Any] = {"provider": p, "model": provider_model, "status": "error", "latency_ms": 0, "error": ""}
            try:
                out = self._call_provider(
                    p,
                    redacted_prompt,
                    redacted_system,
                    purpose=task,
                    project_id=project_id,
                    chars=chars,
                    tokens_est=tokens_est,
                    online_reason=decision.reason,
                    images=images,
                    model_override=provider_model if p == "ollama" else None,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                attempt["status"] = "ok"
                attempt["latency_ms"] = latency_ms
                routing_meta["attempts"].append(attempt)
                text_out = str(out.get("text") or "")
                output_tokens = max(0, len(text_out) // 4)
                model = str(out.get("model") or provider_model)
                out["latency_ms"] = latency_ms
                out["model"] = model
                if self.telemetry_recorder is not None:
                    self.telemetry_recorder.record_llm_call(
                        session_id=session_id,
                        project_id=project_id,
                        mode=selected_mode,
                        provider=p,
                        model=model,
                        profile=self.profile,
                        request_kind=req_kind,
                        input_tokens=tokens_est,
                        output_tokens=output_tokens,
                        cost_usd=out.get("cost_usd"),
                        latency_ms=latency_ms,
                        status="ok",
                    )
                out["_routing"] = routing_meta
                return out
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                last_error = str(exc)
                latency_ms = int((time.perf_counter() - started) * 1000)
                attempt["status"] = "error"
                attempt["latency_ms"] = latency_ms
                attempt["error"] = str(exc)
                routing_meta["attempts"].append(attempt)
                if self.telemetry_recorder is not None:
                    self.telemetry_recorder.record_llm_call(
                        session_id=session_id,
                        project_id=project_id,
                        mode=selected_mode,
                        provider=p,
                        model=provider_model,
                        profile=self.profile,
                        request_kind=req_kind,
                        input_tokens=tokens_est,
                        output_tokens=0,
                        cost_usd=None,
                        latency_ms=latency_ms,
                        status="error",
                        error_kind=classify_error_kind(exc),
                        error_msg=str(exc),
                    )
                continue

        offline_out = {
            "mode": "offline",
            "provider": selected_provider or provider,
            "text": "",
            "raw": None,
            "used_fallback": True,
            "error": last_error,
            "need_online": True,
            "reason": decision.reason,
        }
        offline_out["_routing"] = routing_meta
        return offline_out

    def _router_cfg(self) -> Dict[str, Any]:
        data = self.routing_config.get("router")
        return data if isinstance(data, dict) else {}

    def _default_provider(self) -> str:
        configured = str(self._router_cfg().get("default_provider") or "").strip()
        return str(self.config.get("default_provider") or os.environ.get("NH_DEFAULT_LLM") or configured or "auto")

    def _pick_provider(self, task_type: str) -> str:
        return str(self.task_map.get(task_type, "auto"))

    def _build_provider_order(self, provider: str) -> List[str]:
        if not self._ollama_enabled() and provider == "ollama":
            provider = "auto"
        if provider == "auto":
            candidates = list(self.fallbacks)
        elif provider in self.fallbacks:
            candidates = [provider] + [p for p in self.fallbacks if p != provider]
        else:
            candidates = list(self.fallbacks)
        if not self._ollama_enabled():
            candidates = [p for p in candidates if p != "ollama"]
        return candidates

    def _with_ollama_first(self, order: List[str]) -> List[str]:
        cleaned = [str(p or "").strip().lower() for p in order if str(p or "").strip()]
        if not self._ollama_enabled():
            return [p for p in cleaned if p != "ollama"]
        if "ollama" in cleaned:
            return ["ollama"] + [p for p in cleaned if p != "ollama"]
        if "ollama" in self.fallbacks:
            return ["ollama"] + cleaned
        return cleaned

    def _ollama_enabled(self) -> bool:
        if not bool(getattr(self.ollama_settings, "enabled", True)):
            return False
        return bool(self.registry and "ollama.chat" in self.registry.tools)

    def _budget_limit(self, env_name: str) -> int:
        raw = str(os.environ.get(env_name) or "").strip()
        if not raw:
            return 0
        try:
            value = int(raw)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return 0
        return max(0, value)

    def _budget_status(self, *, session_id: str, planned_input_tokens: int) -> Dict[str, Any]:
        session_limit = self._budget_limit("NH_SESSION_TOKEN_BUDGET")
        daily_limit = self._budget_limit("NH_DAILY_TOKEN_BUDGET")
        if session_limit <= 0 and daily_limit <= 0:
            return {"enabled": False, "blocked": False}

        db = getattr(self.telemetry_recorder, "db", None)
        if db is None:
            return {
                "enabled": True,
                "blocked": False,
                "session_limit": session_limit,
                "daily_limit": daily_limit,
                "message": "Token budget is configured but telemetry db is unavailable.",
            }

        usage = llm_token_usage(db, session_id=str(session_id or ""), daily_window_hours=24)
        session_used = int(usage.get("session_tokens") or 0)
        daily_used = int(usage.get("daily_tokens") or 0)
        session_remaining = session_limit - session_used if session_limit > 0 else 0
        daily_remaining = daily_limit - daily_used if daily_limit > 0 else 0
        session_blocked = bool(session_limit > 0 and session_id and (session_used + planned_input_tokens) > session_limit)
        daily_blocked = bool(daily_limit > 0 and (daily_used + planned_input_tokens) > daily_limit)
        blocked = session_blocked or daily_blocked
        if blocked:
            if daily_blocked and session_blocked:
                message = "Online call blocked: session and daily token budgets exceeded."
            elif daily_blocked:
                message = "Online call blocked: daily token budget exceeded."
            else:
                message = "Online call blocked: session token budget exceeded."
        else:
            message = ""
        return {
            "enabled": True,
            "blocked": blocked,
            "session_limit": session_limit,
            "session_used": session_used,
            "session_remaining": session_remaining,
            "daily_limit": daily_limit,
            "daily_used": daily_used,
            "daily_remaining": daily_remaining,
            "planned_input_tokens": int(max(0, planned_input_tokens)),
            "message": message,
        }

    def _call_provider(
        self,
        provider: str,
        prompt: str,
        system: Optional[str],
        purpose: str,
        project_id: str,
        chars: int,
        tokens_est: int,
        online_reason: str = "",
        images: Optional[List[str]] = None,
        model_override: Optional[str] = None,
        timeout_sec: Optional[int] = None,
    ) -> Dict[str, Any]:
        reason = online_reason.replace("\n", " ").strip()
        reason_part = f" reason={reason}" if reason else ""
        target = f"llm:{provider} purpose={purpose} project={project_id or 'unknown'} chars={chars} tokens={tokens_est}{reason_part}"
        invoke_ctx = InvokeContext(
            runner=self.runner,
            registry=self.registry,
            project_id=str(project_id or ""),
            mode="",
        )

        if provider == "deepseek":
            tool = self.registry.tools.get("deepseek.chat")
            if not tool:
                raise RuntimeError("deepseek.chat tool not available")
            original = tool.default_target
            tool.default_target = target
            try:
                res = invoke_tool("deepseek.chat", {"prompt": prompt, "system": system}, invoke_ctx)
            finally:
                tool.default_target = original
            return {
                "mode": "online",
                "provider": provider,
                "text": _extract_deepseek_text(res),
                "raw": res,
                "used_fallback": False,
                "error": None,
                "model": self._provider_model(provider),
                "cost_usd": _extract_cost_usd(res),
            }

        if provider == "gemini":
            tool = self.registry.tools.get("gemini.prompt")
            if not tool:
                raise RuntimeError("gemini.prompt tool not available")
            original = tool.default_target
            tool.default_target = target
            try:
                res = invoke_tool("gemini.prompt", {"text": prompt, "system": system}, invoke_ctx)
            finally:
                tool.default_target = original
            return {
                "mode": "online",
                "provider": provider,
                "text": _extract_gemini_text(res),
                "raw": res,
                "used_fallback": False,
                "error": None,
                "model": self._provider_model(provider),
                "cost_usd": _extract_cost_usd(res),
            }

        if provider == "openai":
            tool = self.registry.tools.get("openai.chat")
            if not tool:
                raise RuntimeError("openai.chat tool not available")
            original = tool.default_target
            tool.default_target = target
            try:
                res = invoke_tool("openai.chat", {"prompt": prompt, "system": system}, invoke_ctx)
            finally:
                tool.default_target = original
            return {
                "mode": "online",
                "provider": provider,
                "text": _extract_openai_text(res),
                "raw": res,
                "used_fallback": False,
                "error": None,
                "model": self._provider_model(provider),
                "cost_usd": _extract_cost_usd(res),
            }

        if provider == "ollama":
            tool = self.registry.tools.get("ollama.chat")
            if not tool:
                raise RuntimeError("ollama.chat tool not available")
            selected_model = str(model_override or self._provider_model(provider, is_vision=bool(images)) or "").strip()
            if not selected_model:
                raise RuntimeError("No Ollama model resolved for this task")
            res = invoke_tool(
                "ollama.chat",
                {
                    "prompt": prompt,
                    "system": system,
                    "images": images,
                    "model": selected_model,
                    "timeout_sec": timeout_sec,
                },
                invoke_ctx,
            )
            if isinstance(res, dict):
                status = str(res.get("status") or "").strip().lower()
                if status and status != "ok":
                    detail = str(res.get("details") or res.get("error") or "Ollama request failed").strip()
                    raise RuntimeError(detail)
            text = _extract_ollama_text(res)
            if not text:
                raise RuntimeError("Ollama returned empty response")
            return {
                "mode": "offline",
                "provider": provider,
                "text": text,
                "raw": res,
                "used_fallback": False,
                "error": None,
                "model": selected_model,
                "cost_usd": 0.0,
            }

        raise RuntimeError("Unknown provider")

    def _provider_model(
        self,
        provider: str,
        *,
        task_type: str = "",
        mode: str = "",
        request_kind: str = "",
        is_vision: bool = False,
        model_override: str = "",
    ) -> str:
        p = str(provider or "").strip().lower()
        if p == "deepseek":
            return str(self.config.get("deepseek_model") or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat")
        if p == "gemini":
            return str(self.config.get("gemini_model") or os.environ.get("GEMINI_MODEL") or "gemini-1.5-pro")
        if p == "openai":
            return str(self.config.get("openai_model") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini")
        if p == "ollama":
            return self._resolve_ollama_model(
                task_type=task_type,
                mode=mode,
                request_kind=request_kind,
                is_vision=is_vision,
                model_override=model_override,
            )
        return ""

    def _resolve_ollama_model(
        self,
        *,
        task_type: str = "",
        mode: str = "",
        request_kind: str = "",
        is_vision: bool = False,
        model_override: str = "",
    ) -> str:
        return pick_ollama_model(
            mode=mode,
            request_kind=request_kind,
            task_type=task_type,
            task_model_map=self.task_model_map,
            settings=self.ollama_settings,
            is_vision=is_vision,
            model_override=model_override,
        )

    def _is_coder_local_task(self, *, task: str, mode: str, request_kind: str) -> bool:
        if task in {"patch_planning", "plan"}:
            return True
        if mode == "build_software":
            return True
        rk = str(request_kind or "")
        if any(token in rk for token in ("patch", "code", "build", "refactor")):
            return True
        return False


def _extract_deepseek_text(res: Dict[str, Any]) -> str:
    try:
        choices = res.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            return str(msg.get("content") or "").strip()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return ""


def _extract_gemini_text(res: Dict[str, Any]) -> str:
    try:
        candidates = res.get("candidates") or []
        if candidates:
            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []
            if parts:
                return str(parts[0].get("text") or "").strip()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return ""


def _extract_openai_text(res: Dict[str, Any]) -> str:
    try:
        choices = res.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            return str(msg.get("content") or "").strip()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return ""


def _extract_ollama_text(res: Dict[str, Any]) -> str:
    try:
        direct = str(res.get("text") or "").strip()
        if direct:
            return direct
        msg = res.get("message") or {}
        if isinstance(msg, dict):
            content = str(msg.get("content") or "").strip()
            if content:
                return content
        return str(res.get("response") or "").strip()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        pass
    return ""


def _extract_cost_usd(res: Dict[str, Any]) -> float | None:
    # Provider responses do not consistently return cost. Keep nullable in v1.
    _ = res
    return None


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)

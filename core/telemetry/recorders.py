from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .db import TelemetryDB
from .sanitize import sanitize_error_message, truncate_text


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class TelemetryRecorder:
    def __init__(self, db: TelemetryDB) -> None:
        self.db = db

    def record_llm_call(
        self,
        *,
        session_id: str = "",
        project_id: str = "",
        mode: str = "",
        provider: str = "",
        model: str = "",
        profile: str = "",
        request_kind: str = "",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
        latency_ms: int | None = None,
        status: str = "ok",
        error_kind: str | None = None,
        error_msg: str | None = None,
        call_id: str | None = None,
        ts: str | None = None,
    ) -> str:
        rid = str(call_id or uuid.uuid4().hex)
        self.db.execute(
            """
            INSERT INTO llm_calls(
                id, ts, session_id, project_id, mode, provider, model, profile, request_kind,
                input_tokens, output_tokens, cost_usd, latency_ms, status, error_kind, error_msg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                str(ts or _utc_now()),
                str(session_id or ""),
                str(project_id or ""),
                str(mode or ""),
                str(provider or ""),
                str(model or ""),
                str(profile or ""),
                str(request_kind or ""),
                int(input_tokens or 0),
                int(output_tokens or 0),
                float(cost_usd) if cost_usd is not None else None,
                int(latency_ms or 0),
                str(status or "ok"),
                str(error_kind or "") if error_kind else None,
                sanitize_error_message(error_msg or "") if error_msg else None,
            ),
        )
        return rid

    def record_tool_call(
        self,
        *,
        session_id: str = "",
        project_id: str = "",
        mode: str = "",
        tool_name: str = "",
        latency_ms: int | None = None,
        status: str = "ok",
        error_kind: str | None = None,
        error_msg: str | None = None,
        call_id: str | None = None,
        ts: str | None = None,
    ) -> str:
        rid = str(call_id or uuid.uuid4().hex)
        self.db.execute(
            """
            INSERT INTO tool_calls(
                id, ts, session_id, project_id, mode, tool_name, latency_ms, status, error_kind, error_msg
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                str(ts or _utc_now()),
                str(session_id or ""),
                str(project_id or ""),
                str(mode or ""),
                str(tool_name or ""),
                int(latency_ms or 0),
                str(status or "ok"),
                str(error_kind or "") if error_kind else None,
                sanitize_error_message(error_msg or "") if error_msg else None,
            ),
        )
        return rid

    def start_task_run(
        self,
        *,
        session_id: str = "",
        project_id: str = "",
        mode: str = "",
        objective: str = "",
        run_id: str | None = None,
    ) -> str:
        rid = str(run_id or uuid.uuid4().hex)
        self.db.execute(
            """
            INSERT INTO task_runs(
                id, ts_start, ts_end, session_id, project_id, mode, objective, status,
                qa_passed, tests_passed, tests_failed, notes
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
            """,
            (
                rid,
                _utc_now(),
                str(session_id or ""),
                str(project_id or ""),
                str(mode or ""),
                truncate_text(objective, max_len=300),
                "running",
            ),
        )
        return rid

    def finish_task_run(
        self,
        run_id: str,
        *,
        status: str = "ok",
        qa_passed: bool | None = None,
        tests_passed: int | None = None,
        tests_failed: int | None = None,
        notes: str = "",
    ) -> None:
        self.db.execute(
            """
            UPDATE task_runs
               SET ts_end = ?, status = ?, qa_passed = ?, tests_passed = ?, tests_failed = ?, notes = ?
             WHERE id = ?
            """,
            (
                _utc_now(),
                str(status or "ok"),
                None if qa_passed is None else int(bool(qa_passed)),
                None if tests_passed is None else int(tests_passed),
                None if tests_failed is None else int(tests_failed),
                truncate_text(notes, max_len=300),
                str(run_id or ""),
            ),
        )

    def record_task_run(
        self,
        *,
        session_id: str = "",
        project_id: str = "",
        mode: str = "",
        objective: str = "",
        status: str = "ok",
        qa_passed: bool | None = None,
        tests_passed: int | None = None,
        tests_failed: int | None = None,
        notes: str = "",
    ) -> str:
        rid = self.start_task_run(
            session_id=session_id,
            project_id=project_id,
            mode=mode,
            objective=objective,
        )
        self.finish_task_run(
            rid,
            status=status,
            qa_passed=qa_passed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            notes=notes,
        )
        return rid


def classify_error_kind(exc: Exception | str | None) -> str:
    text = str(exc or "").strip().lower()
    if not text:
        return "other"
    if "rate limit" in text or "too many requests" in text or "429" in text:
        return "rate_limit"
    if "auth" in text or "api key" in text or "unauthorized" in text or "forbidden" in text or "401" in text or "403" in text:
        return "auth"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    return "other"

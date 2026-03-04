from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, Mapping

from core.ux.task_modes import normalize_task_mode


_ROUTE_HEADER_RE = re.compile(r"^\[\[NOVA_MODE (?P<meta>[^\]]+)\]\]\s*$")


@dataclass(frozen=True)
class ModeRouteEnvelope:
    mode: str
    text: str
    context: Dict[str, str] = field(default_factory=dict)
    wrapped: bool = False


def _sanitize_context_value(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    # Keep wrapper single-line and human-readable in logs.
    return raw.replace("\n", " ").replace(";", ",").replace("=", ":")


def _normalize_context(context: Mapping[str, object] | None) -> Dict[str, str]:
    if context is None:
        return {}
    out: Dict[str, str] = {}
    for key, value in context.items():
        k = str(key or "").strip().lower()
        if not k:
            continue
        sanitized = _sanitize_context_value(value)
        if not sanitized:
            continue
        out[k] = sanitized
    return out


def route_message_for_mode(
    mode: str,
    text: str,
    context: Mapping[str, object] | None = None,
) -> str:
    payload = str(text or "").strip()
    normalized_mode = normalize_task_mode(mode)
    if not payload:
        return ""
    normalized_context = _normalize_context(context)
    meta = [f"mode={normalized_mode}"]
    for key in sorted(normalized_context.keys()):
        meta.append(f"{key}={normalized_context[key]}")
    header = f"[[NOVA_MODE {'; '.join(meta)}]]"
    return f"{header}\n{payload}"


def parse_mode_wrapped_message(message: str) -> ModeRouteEnvelope:
    raw = str(message or "")
    if not raw.strip():
        return ModeRouteEnvelope(mode=normalize_task_mode(""), text="", context={}, wrapped=False)

    lines = raw.splitlines()
    if not lines:
        return ModeRouteEnvelope(mode=normalize_task_mode(""), text="", context={}, wrapped=False)
    first = lines[0].strip()
    match = _ROUTE_HEADER_RE.match(first)
    if not match:
        return ModeRouteEnvelope(mode=normalize_task_mode(""), text=raw.strip(), context={}, wrapped=False)

    meta_raw = str(match.group("meta") or "").strip()
    context: Dict[str, str] = {}
    mode = normalize_task_mode("")
    for token in [x.strip() for x in meta_raw.split(";") if x.strip()]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        k = str(key or "").strip().lower()
        v = str(value or "").strip()
        if not k:
            continue
        if k == "mode":
            mode = normalize_task_mode(v)
            continue
        context[k] = v
    text = "\n".join(lines[1:]).strip()
    return ModeRouteEnvelope(mode=mode, text=text, context=context, wrapped=True)


def unwrap_mode_wrapped_text(message: str) -> str:
    return parse_mode_wrapped_message(message).text

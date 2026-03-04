from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from core.ux.task_modes import normalize_task_mode


MODE_GENERAL = "general"
MODE_BUILD_SOFTWARE = "build_software"
MODE_GEN_3D_STEP = "gen_3d_step"
MODE_GEN_2D_DXF = "gen_2d_dxf"


@dataclass(frozen=True)
class ToolUxMeta:
    tool_id: str
    mode_tags: tuple[str, ...]
    curated_modes: tuple[str, ...] = ()
    required_modules: tuple[str, ...] = ()
    required_env_vars: tuple[str, ...] = ()
    requires_project_context: bool = False


def _modes(*modes: str) -> tuple[str, ...]:
    out: List[str] = []
    seen = set()
    for mode in modes:
        normalized = normalize_task_mode(mode)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return tuple(out)


V1_TOOL_UX_META: Dict[str, ToolUxMeta] = {
    "conversation.chat": ToolUxMeta(
        tool_id="conversation.chat",
        mode_tags=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE, MODE_GEN_3D_STEP, MODE_GEN_2D_DXF),
        curated_modes=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE, MODE_GEN_3D_STEP, MODE_GEN_2D_DXF),
    ),
    "deepseek.chat": ToolUxMeta(
        tool_id="deepseek.chat",
        mode_tags=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE),
        required_env_vars=("DEEPSEEK_API_KEY",),
    ),
    "gemini.prompt": ToolUxMeta(
        tool_id="gemini.prompt",
        mode_tags=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE),
        required_env_vars=("GEMINI_API_KEY",),
    ),
    "openai.chat": ToolUxMeta(
        tool_id="openai.chat",
        mode_tags=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE),
        required_env_vars=("OPENAI_API_KEY",),
    ),
    "telegram.send": ToolUxMeta(
        tool_id="telegram.send",
        mode_tags=_modes(MODE_GENERAL),
        required_env_vars=("TELEGRAM_BOT_TOKEN",),
    ),
    "project.scan_repo": ToolUxMeta(
        tool_id="project.scan_repo",
        mode_tags=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE),
        curated_modes=_modes(MODE_BUILD_SOFTWARE),
    ),
    "repo.search": ToolUxMeta(
        tool_id="repo.search",
        mode_tags=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE),
        curated_modes=_modes(MODE_GENERAL, MODE_BUILD_SOFTWARE),
    ),
    "patch.plan": ToolUxMeta(
        tool_id="patch.plan",
        mode_tags=_modes(MODE_BUILD_SOFTWARE),
        curated_modes=_modes(MODE_BUILD_SOFTWARE),
        requires_project_context=True,
    ),
    "patch.apply": ToolUxMeta(
        tool_id="patch.apply",
        mode_tags=_modes(MODE_BUILD_SOFTWARE),
        curated_modes=_modes(MODE_BUILD_SOFTWARE),
        requires_project_context=True,
    ),
    "verify.smoke": ToolUxMeta(
        tool_id="verify.smoke",
        mode_tags=_modes(MODE_BUILD_SOFTWARE, MODE_GENERAL),
        curated_modes=_modes(MODE_BUILD_SOFTWARE, MODE_GENERAL),
    ),
    "pipeline.run": ToolUxMeta(
        tool_id="pipeline.run",
        mode_tags=_modes(MODE_BUILD_SOFTWARE),
        curated_modes=_modes(MODE_BUILD_SOFTWARE),
    ),
    "sketch.parse": ToolUxMeta(
        tool_id="sketch.parse",
        mode_tags=_modes(MODE_GEN_2D_DXF),
        curated_modes=_modes(MODE_GEN_2D_DXF),
    ),
    "sketch.apply": ToolUxMeta(
        tool_id="sketch.apply",
        mode_tags=_modes(MODE_GEN_2D_DXF),
        curated_modes=_modes(MODE_GEN_2D_DXF),
    ),
    "sketch.export_dxf": ToolUxMeta(
        tool_id="sketch.export_dxf",
        mode_tags=_modes(MODE_GEN_2D_DXF),
        curated_modes=_modes(MODE_GEN_2D_DXF),
    ),
    "cad.dxf.generate": ToolUxMeta(
        tool_id="cad.dxf.generate",
        mode_tags=_modes(MODE_GEN_2D_DXF),
        curated_modes=_modes(MODE_GEN_2D_DXF),
        required_modules=("ezdxf",),
    ),
    "cad.step.generate": ToolUxMeta(
        tool_id="cad.step.generate",
        mode_tags=_modes(MODE_GEN_3D_STEP),
        curated_modes=_modes(MODE_GEN_3D_STEP),
        required_modules=("cadquery",),
    ),
    "nesting.solve_rectangles": ToolUxMeta(
        tool_id="nesting.solve_rectangles",
        mode_tags=_modes(MODE_GEN_2D_DXF),
    ),
    "conical.generate_helix": ToolUxMeta(
        tool_id="conical.generate_helix",
        mode_tags=_modes(MODE_GEN_2D_DXF),
    ),
    "halftone.generate_pattern": ToolUxMeta(
        tool_id="halftone.generate_pattern",
        mode_tags=_modes(MODE_GEN_2D_DXF),
    ),
    "run.preview": ToolUxMeta(
        tool_id="run.preview",
        mode_tags=_modes(MODE_BUILD_SOFTWARE, MODE_GEN_3D_STEP),
        curated_modes=_modes(MODE_GEN_3D_STEP),
    ),
    "run.stop": ToolUxMeta(
        tool_id="run.stop",
        mode_tags=_modes(MODE_BUILD_SOFTWARE, MODE_GEN_3D_STEP),
    ),
    "security.audit": ToolUxMeta(
        tool_id="security.audit",
        mode_tags=_modes(MODE_BUILD_SOFTWARE, MODE_GENERAL),
        curated_modes=_modes(MODE_BUILD_SOFTWARE),
        requires_project_context=True,
    ),
    "voice.stt_record": ToolUxMeta(
        tool_id="voice.stt_record",
        mode_tags=_modes(MODE_GENERAL),
        curated_modes=_modes(MODE_GENERAL),
        required_modules=("faster_whisper", "sounddevice"),
    ),
    "voice.tts_speak": ToolUxMeta(
        tool_id="voice.tts_speak",
        mode_tags=_modes(MODE_GENERAL),
        required_modules=("pyttsx3",),
    ),
}


_CURATED_FALLBACK_ORDER: Dict[str, tuple[str, ...]] = {
    MODE_GENERAL: (
        "conversation.chat",
        "repo.search",
        "verify.smoke",
        "voice.stt_record",
    ),
    MODE_BUILD_SOFTWARE: (
        "conversation.chat",
        "project.scan_repo",
        "repo.search",
        "patch.plan",
        "patch.apply",
        "verify.smoke",
        "pipeline.run",
        "security.audit",
    ),
    MODE_GEN_2D_DXF: (
        "conversation.chat",
        "sketch.parse",
        "sketch.apply",
        "sketch.export_dxf",
        "cad.dxf.generate",
        "nesting.solve_rectangles",
        "conical.generate_helix",
        "halftone.generate_pattern",
    ),
    MODE_GEN_3D_STEP: (
        "conversation.chat",
        "cad.step.generate",
        "run.preview",
    ),
}


def metadata_for_tool(tool_id: str) -> ToolUxMeta:
    tid = str(tool_id or "").strip()
    meta = V1_TOOL_UX_META.get(tid)
    if meta is not None:
        return meta
    return ToolUxMeta(tool_id=tid, mode_tags=_modes(MODE_GENERAL), curated_modes=())


def mode_tags_for_tool(tool_id: str) -> List[str]:
    return list(metadata_for_tool(tool_id).mode_tags)


def curated_tool_ids_for_mode(mode: str, *, project_context: bool = False) -> List[str]:
    normalized_mode = normalize_task_mode(mode)
    order = list(_CURATED_FALLBACK_ORDER.get(normalized_mode) or ())
    dynamic = []
    for tool_id, meta in V1_TOOL_UX_META.items():
        if normalized_mode in meta.curated_modes and tool_id not in order:
            dynamic.append(tool_id)
    order.extend(sorted(dynamic))

    if project_context and normalized_mode == MODE_GENERAL:
        for extra in ("project.scan_repo", "patch.plan"):
            if extra not in order:
                order.append(extra)
    return order


def tools_index_rows(tool_ids: List[str]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for tool_id in sorted({str(x or "").strip() for x in tool_ids if str(x or "").strip()}):
        meta = metadata_for_tool(tool_id)
        rows.append(
            {
                "id": tool_id,
                "mode_tags": list(meta.mode_tags),
                "curated_modes": list(meta.curated_modes),
            }
        )
    return rows

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration


def _params_or_empty(params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return dict(params or {})


def _missing_dep_error(feature: str, exc: Exception) -> RuntimeError:
    return RuntimeError(
        f"{feature} is unavailable because optional CAD dependencies are missing. "
        f"Install requirements-cad.txt / requirements-3d.txt. ({exc})"
    )


def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    def cad_dxf_generate(
        spec_text: str = "",
        params: Optional[Mapping[str, Any]] = None,
        output_path: str = "outputs/generated_shape.dxf",
        units: str = "mm",
        layer: str = "OUTLINE",
    ) -> Dict[str, Any]:
        try:
            from core.cad_pipeline.dxf_generator import generate_dxf
        except (ImportError, ModuleNotFoundError) as exc:
            raise _missing_dep_error("cad.dxf.generate", exc) from exc
        return generate_dxf(
            spec_text=spec_text,
            params=_params_or_empty(params),
            output_path=output_path,
            units=units,
            layer=layer,
        )

    def cad_step_generate(
        spec_text: str = "",
        params: Optional[Mapping[str, Any]] = None,
        output_path: str = "outputs/generated_part.step",
    ) -> Dict[str, Any]:
        try:
            from core.cad_pipeline.step_generator import generate_step
        except (ImportError, ModuleNotFoundError) as exc:
            raise _missing_dep_error("cad.step.generate", exc) from exc
        return generate_step(
            spec_text=spec_text,
            params=_params_or_empty(params),
            output_path=output_path,
        )

    registry.register_tool(
        ToolRegistration(
            tool_id="cad.dxf.generate",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="cad_dxf_generate",
            handler=cad_dxf_generate,
            description="Generate a 2D DXF artifact from text spec or params.",
            default_target="outputs/generated_shape.dxf",
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="cad.step.generate",
            plugin_id=manifest.id,
            tool_group="fs_write",
            op="cad_step_generate",
            handler=cad_step_generate,
            description="Generate a 3D STEP artifact from text spec or params (optional cadquery).",
            default_target="outputs/generated_part.step",
        )
    )

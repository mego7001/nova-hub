from pathlib import Path

from core.cad_pipeline.dxf_generator import generate_dxf
from core.cad_pipeline.step_generator import generate_step
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistration, PluginRegistry
from integrations.cad_pipeline.plugin import init_plugin


def test_generate_dxf_writes_output(tmp_path: Path):
    out = tmp_path / "shape.dxf"
    result = generate_dxf(
        spec_text="rectangle 120x80",
        params={"shape": "rectangle", "width": 120, "height": 80},
        output_path=str(out),
    )
    assert result.get("ok") is True
    assert Path(str(result.get("out_dxf") or "")).exists()
    assert str(result.get("shape")) == "rectangle"


def test_generate_step_is_graceful_without_optional_dependency(tmp_path: Path):
    out = tmp_path / "part.step"
    result = generate_step(
        spec_text="box",
        params={"shape": "box", "width": 10, "depth": 10, "height": 10},
        output_path=str(out),
    )
    if result.get("ok") is True:
        assert Path(str(result.get("out_step") or "")).exists()
    else:
        assert "cadquery" in str(result.get("error") or "").lower()


def test_cad_pipeline_plugin_registers_tools():
    registry = PluginRegistry()
    registry.register_plugin(
        PluginRegistration(
            plugin_id="cad_pipeline",
            kind="integration",
            name="CAD Pipeline Tools",
            version="1.0.0",
            entrypoint="integrations.cad_pipeline.plugin",
            tool_groups=["fs_write"],
            config={},
        )
    )
    manifest = PluginManifest(
        id="cad_pipeline",
        name="CAD Pipeline Tools",
        version="1.0.0",
        kind="integration",
        entrypoint="integrations.cad_pipeline.plugin",
        tool_groups=["fs_write"],
        config_schema={"type": "object", "properties": {}, "required": []},
    )
    init_plugin({}, registry, manifest)
    assert "cad.dxf.generate" in registry.tools
    assert "cad.step.generate" in registry.tools

from core.ux.tools_registry import curated_tool_ids_for_mode, metadata_for_tool


def test_tools_registry_curated_build_mode_contains_patch_flow():
    curated = curated_tool_ids_for_mode("build_software", project_context=True)
    assert "patch.plan" in curated
    assert "patch.apply" in curated
    assert "pipeline.run" in curated


def test_tools_registry_curated_dxf_mode_focuses_geometry_tools():
    curated = curated_tool_ids_for_mode("gen_2d_dxf", project_context=True)
    assert "sketch.parse" in curated
    assert "sketch.export_dxf" in curated


def test_tools_registry_unknown_tool_falls_back_to_general():
    meta = metadata_for_tool("unknown.tool")
    assert meta.mode_tags == ("general",)
    assert meta.curated_modes == ()

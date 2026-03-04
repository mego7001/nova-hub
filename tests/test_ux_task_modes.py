from core.plugin_engine.registry import PluginRegistry
from core.ux.task_modes import available_task_modes, is_mode_supported, normalize_task_mode


def test_task_modes_hide_unavailable_by_default():
    reg = PluginRegistry()
    rows = available_task_modes(reg, include_unavailable=False)
    ids = {str(row.get("id")) for row in rows}
    assert "general" in ids
    assert "gen_3d_step" not in ids
    assert "build_software" not in ids
    assert "gen_2d_dxf" not in ids


def test_task_modes_include_available_tool_backed_modes():
    reg = PluginRegistry()
    reg.tools["conversation.chat"] = object()  # type: ignore[index]
    reg.tools["sketch.export_dxf"] = object()  # type: ignore[index]
    rows = available_task_modes(reg, include_unavailable=False)
    ids = {str(row.get("id")) for row in rows}
    assert "build_software" in ids
    assert "gen_2d_dxf" in ids
    assert is_mode_supported("build", reg) is True


def test_available_task_modes_return_v1_ids_only():
    reg = PluginRegistry()
    reg.tools["conversation.chat"] = object()  # type: ignore[index]
    reg.tools["cad.step.generate"] = object()  # type: ignore[index]
    reg.tools["sketch.export_dxf"] = object()  # type: ignore[index]
    ids = {str(row.get("id")) for row in available_task_modes(reg, include_unavailable=False)}
    assert ids <= {"general", "build_software", "gen_3d_step", "gen_2d_dxf"}


def test_normalize_task_mode_falls_back_to_general():
    assert normalize_task_mode("DEEP_RESEARCH") == "build_software"
    assert normalize_task_mode("sketch") == "gen_2d_dxf"
    assert normalize_task_mode("not-real-mode") == "general"

from __future__ import annotations

import importlib
import sys

import pytest

from core.cad_pipeline import dxf_generator, step_generator
from core.utils import optional_deps
from core.utils.optional_deps import FeatureUnavailable


def test_step_generator_graceful_when_cadquery_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        step_generator,
        "require",
        lambda *a, **k: (False, "Feature disabled: missing dependency 'cadquery'"),
    )
    out = tmp_path / "part.step"
    result = step_generator.generate_step(output_path=str(out))
    assert result.get("ok") is False
    assert "missing dependency" in str(result.get("error") or "").lower()


def test_dxf_generator_self_intersection_check_is_noop_without_shapely(monkeypatch) -> None:
    monkeypatch.setattr(
        dxf_generator,
        "require",
        lambda *a, **k: (False, "Feature disabled: missing dependency 'shapely'"),
    )
    warnings = []
    dxf_generator._line_self_intersection_best_effort([(0.0, 0.0), (1.0, 1.0)], warnings)
    assert warnings == []


def test_cad_package_import_survives_pattern_mapper_import_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        optional_deps,
        "require",
        lambda *a, **k: (False, "Feature disabled: missing dependency 'shapely'"),
    )
    sys.modules.pop("core.cad_pipeline", None)
    sys.modules.pop("core.cad_pipeline.pattern_mapper", None)

    mod = importlib.import_module("core.cad_pipeline")
    with pytest.raises(FeatureUnavailable):
        mod.PatternMapper()

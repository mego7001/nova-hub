from .dxf_handler import LineSegment, PatternDXFReader, PolylinePath
from .dxf_generator import generate_dxf
from .geometry_engine import ConicalHelixEngine, EngineConfig, PanelDefinition, PanelFlatPattern
from .panels_dxf import PanelDXFGenerator
from .step_generator import generate_step
from core.utils.optional_deps import FeatureUnavailable, require

_has_shapely, _shapely_msg = require(
    "shapely",
    "pip install -r requirements-cad.txt",
    "pattern mapping",
)

try:
    if not _has_shapely:
        raise ImportError(_shapely_msg)
    from .pattern_mapper import MappedLine, MappedPolyline, PatternMapper, PatternProjector
except (ImportError, ModuleNotFoundError) as _pattern_mapper_exc:
    _pattern_mapper_cause = _pattern_mapper_exc
    _pattern_mapper_error = RuntimeError(
        "Feature disabled: missing dependency 'shapely' for pattern mapping. "
        "Install with: pip install -r requirements-cad.txt"
    )

    class _PatternMapperUnavailable:
        def __init__(self, *args, **kwargs) -> None:
            raise FeatureUnavailable(str(_pattern_mapper_error)) from _pattern_mapper_cause

    class _MappedUnavailable:
        def __init__(self, *args, **kwargs) -> None:
            raise FeatureUnavailable(str(_pattern_mapper_error)) from _pattern_mapper_cause

    PatternMapper = _PatternMapperUnavailable
    PatternProjector = _PatternMapperUnavailable
    MappedLine = _MappedUnavailable
    MappedPolyline = _MappedUnavailable

__all__ = [
    "ConicalHelixEngine",
    "EngineConfig",
    "LineSegment",
    "MappedLine",
    "MappedPolyline",
    "PanelDXFGenerator",
    "PanelDefinition",
    "PanelFlatPattern",
    "PatternDXFReader",
    "PatternMapper",
    "PatternProjector",
    "PolylinePath",
    "generate_dxf",
    "generate_step",
]

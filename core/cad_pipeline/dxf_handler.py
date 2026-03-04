from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple
import math
import ezdxf
from ezdxf.math import bulge_to_arc
from .qa_report import QACollector, QAReportV1, resolve_workspace_root


_BULGE_EPSILON = 1e-9
_POINT_EPSILON = 1e-8
_DEFAULT_ARC_SEGMENTS = 96
_DEGENERATE_WARN_THRESHOLD = 50


@dataclass
class LineSegment:
    """
    ØªÙ…Ø«ÙŠÙ„ Ø®Ø· Ù…Ø³ØªÙ‚ÙŠÙ… ÙˆØ§Ø­Ø¯ Ù…Ù† DXF ÙƒØ¨Ø¯Ø§ÙŠØ© ÙˆÙ†Ù‡Ø§ÙŠØ©.
    """
    start: Tuple[float, float]
    end: Tuple[float, float]


@dataclass
class PolylinePath:
    """
    ØªÙ…Ø«ÙŠÙ„ Polyline ÙƒÙ…Ø³Ø§Ø± Ù…Ù† Ù†Ù‚Ø§Ø· Ù…ØªØªØ§Ø¨Ø¹Ø©.
    """
    points: List[Tuple[float, float]]
    closed: bool = False


class PatternDXFReader:
    """
    Ù‚Ø§Ø±Ø¦ DXF Ù…Ø­Ø³Ù‘Ù† Ù„Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ù…Ø³ØªØ·ÙŠÙ„:
    - Ù‚Ø±Ø§Ø¡Ø© Ø¢Ù…Ù†Ø© Ù…Ø¹ Ù…Ø¹Ø§Ù„Ø¬Ø© Ø£Ø®Ø·Ø§Ø¡ Ù…Ø­Ø³Ù‘Ù†Ø©
    - Ø§Ø³ØªØ®Ø±Ø§Ø¬ Lines Ùˆ Polylines Ø¨ÙƒÙØ§Ø¡Ø©
    - Ø­Ø³Ø§Ø¨ Bounds Ø¯Ù‚ÙŠÙ‚
    - Ø¯Ø¹Ù… Ø§Ù„Ø·Ø¨Ù‚Ø§Øª (Layers)
    - ØªÙ‚Ø§Ø±ÙŠØ± Ù…ÙØµÙ„Ø© Ø¹Ù† Ø§Ù„Ù…Ø­ØªÙˆÙ‰
    """

    def __init__(
        self,
        file_path: str,
        pattern_config: Optional[Mapping[str, Any]] = None,
        project_id: str = "unknown",
        pattern_id: str = "",
        workspace_root: Optional[str] = None,
        qa_report: Optional[QAReportV1] = None,
        qa_collector: Optional[QACollector] = None,
    ):
        self.file_path = file_path
        self.arc_segments = self._resolve_arc_segments(pattern_config)
        self.workspace_root = resolve_workspace_root(workspace_root or file_path)
        self.qa_report = qa_report or QAReportV1(
            project_id=str(project_id or "unknown"),
            dxf_path=file_path,
            pattern_id=pattern_id,
            units="mm",
        )
        self.qa_collector = qa_collector or QACollector(self.qa_report)
        if qa_collector is not None:
            self.qa_report = qa_collector.report
        self._qa_initialized = False
        self._qa_findings_finalized = False
        self.doc: Optional[ezdxf.document.Drawing] = None
        self.msp = None
        self._init_qa_defaults()
        self._load_file()

    def _resolve_arc_segments(self, pattern_config: Optional[Mapping[str, Any]]) -> int:
        """
        Resolve arc sampling density from `pattern.arc_segments`.
        """
        if pattern_config is None:
            return _DEFAULT_ARC_SEGMENTS

        arc_segments: Any = None
        if isinstance(pattern_config, Mapping):
            arc_segments = pattern_config.get("pattern.arc_segments")
            if arc_segments is None:
                pattern_section = pattern_config.get("pattern")
                if isinstance(pattern_section, Mapping):
                    arc_segments = pattern_section.get("arc_segments")
            if arc_segments is None:
                arc_segments = pattern_config.get("arc_segments")

        try:
            parsed = int(arc_segments)
        except (TypeError, ValueError):
            return _DEFAULT_ARC_SEGMENTS
        return parsed if parsed >= 2 else _DEFAULT_ARC_SEGMENTS

    def _init_qa_defaults(self) -> None:
        self.qa_report.ensure_schema_defaults()
        self.qa_report.dxf["arc_segments_default"] = int(self.arc_segments)
        self._reset_qa_runtime()

    def _reset_qa_runtime(self) -> None:
        self.qa_report.ensure_schema_defaults()
        dxf = self.qa_report.dxf
        dxf["entities_seen"] = 0
        dxf["polylines_seen"] = 0
        dxf["lwpolylines_seen"] = 0
        dxf["bulge_segments_seen"] = 0
        dxf["bulge_segments_expanded"] = 0
        dxf["bulge_segments_failed"] = 0
        dxf["closed_loops_seen"] = 0
        dxf["closed_loops_enforced"] = 0
        dxf["degenerate_segments_dropped"] = 0
        dxf["invalid_entities_skipped"] = 0
        dxf["entity_counts"] = {}
        self._qa_initialized = True
        self._qa_findings_finalized = False

    def _qa_inc(self, key: str, amount: int = 1) -> None:
        self.qa_report.ensure_schema_defaults()
        current = int(self.qa_report.dxf.get(key) or 0)
        self.qa_report.dxf[key] = current + int(amount)

    def _qa_inc_entity_type(self, entity_type: str, amount: int = 1) -> None:
        self.qa_report.ensure_schema_defaults()
        counts = self.qa_report.dxf.get("entity_counts")
        if not isinstance(counts, dict):
            counts = {}
            self.qa_report.dxf["entity_counts"] = counts
        key = str(entity_type or "").upper()
        counts[key] = int(counts.get(key) or 0) + int(amount)

    def _bind_collector(self, qa_collector: Optional[QACollector]) -> None:
        if qa_collector is None:
            return
        if qa_collector.report is self.qa_report:
            self.qa_collector = qa_collector
            return
        self.qa_collector = qa_collector
        self.qa_report = qa_collector.report
        self.qa_report.ensure_schema_defaults()

    def _scan_entity_type_counts(self, layer: Optional[str] = None) -> None:
        if self.msp is None:
            return
        counts: Dict[str, int] = {}
        for entity in self.msp:
            try:
                if layer:
                    ent_layer = str(getattr(entity.dxf, "layer", "") or "")
                    if ent_layer != layer:
                        continue
                ent_type = str(entity.dxftype() or "").upper()
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                ent_type = "UNKNOWN"
            counts[ent_type] = int(counts.get(ent_type) or 0) + 1
        ordered = {k: counts[k] for k in sorted(counts.keys())}
        self.qa_report.dxf["entity_counts"] = ordered

    def _finalize_qa_findings(self) -> None:
        if self._qa_findings_finalized:
            return
        self._qa_findings_finalized = True

        dxf = self.qa_report.dxf
        bulge_seen = int(dxf.get("bulge_segments_seen") or 0)
        bulge_expanded = int(dxf.get("bulge_segments_expanded") or 0)
        bulge_failed = int(dxf.get("bulge_segments_failed") or 0)
        degenerate = int(dxf.get("degenerate_segments_dropped") or 0)
        invalid = int(dxf.get("invalid_entities_skipped") or 0)
        closures = int(dxf.get("closed_loops_enforced") or 0)
        entity_counts = dxf.get("entity_counts") if isinstance(dxf.get("entity_counts"), dict) else {}

        if bulge_seen > 0:
            self.qa_report.add_unique(
                "info",
                "DXF_BULGE_SAMPLED",
                "Expanded bulge segments using arc sampling.",
                {"count": bulge_seen, "segments": int(self.arc_segments), "expanded": bulge_expanded},
            )
        if degenerate > _DEGENERATE_WARN_THRESHOLD:
            self.qa_report.add_unique(
                "warn",
                "DXF_DEGENERATE_DROPS_HIGH",
                "Many degenerate segments were dropped.",
                {"count": degenerate, "threshold": _DEGENERATE_WARN_THRESHOLD},
            )
        if invalid > 0:
            self.qa_report.add_unique(
                "warn",
                "DXF_INVALID_ENTITIES_SKIPPED",
                "One or more invalid DXF entities were skipped.",
                {"count": invalid},
            )
        if bulge_failed > 0:
            self.qa_report.add_unique(
                "warn",
                "DXF_BULGE_FALLBACK",
                "One or more bulge arcs could not be converted and were kept as straight segments.",
                {"count": bulge_failed},
            )
        if closures > 0:
            self.qa_report.add_unique(
                "info",
                "DXF_CLOSED_LOOP_ENFORCED",
                "Closed loops were explicitly repaired to keep first==last.",
                {"count": closures},
            )
        supported = {"LINE", "LWPOLYLINE", "POLYLINE"}
        unsupported = sum(
            int(v or 0) for k, v in entity_counts.items() if str(k or "").upper() not in supported
        )
        if unsupported > 0:
            self.qa_report.add_unique(
                "info",
                "DXF_UNSUPPORTED_TYPES_PRESENT",
                "DXF contains entity types that are currently not projected by this reader.",
                {"count": unsupported, "types": sorted(entity_counts.keys())},
            )

    def _distance_sq(
        self,
        point_a: Tuple[float, float],
        point_b: Tuple[float, float],
    ) -> float:
        dx = point_a[0] - point_b[0]
        dy = point_a[1] - point_b[1]
        return dx * dx + dy * dy

    def _points_close(
        self,
        point_a: Tuple[float, float],
        point_b: Tuple[float, float],
        epsilon: float = _POINT_EPSILON,
    ) -> bool:
        return self._distance_sq(point_a, point_b) <= epsilon * epsilon

    def _expand_segment_with_bulge(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        bulge: float,
    ) -> List[Tuple[float, float]]:
        """
        Expand one bulge segment into sampled arc points.
        """
        if self._points_close(start, end):
            self._qa_inc("degenerate_segments_dropped")
            return [start]
        if abs(bulge) < _BULGE_EPSILON:
            return [start, end]

        self._qa_inc("bulge_segments_seen")
        try:
            center, start_angle, end_angle, radius = bulge_to_arc(start, end, bulge)
            self._qa_inc("bulge_segments_expanded")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            self._qa_inc("bulge_segments_failed")
            return [start, end]

        sweep = end_angle - start_angle
        while sweep <= 0.0:
            sweep += 2.0 * math.pi

        steps = max(2, int(math.ceil(self.arc_segments * (sweep / (2.0 * math.pi)))))
        cx = float(center[0])
        cy = float(center[1])
        arc_points: List[Tuple[float, float]] = []

        for index in range(steps + 1):
            t = index / steps
            angle = start_angle + sweep * t
            arc_points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

        # bulge_to_arc is always CCW; reverse for clockwise bulge segments.
        if self._distance_sq(arc_points[0], start) > self._distance_sq(arc_points[0], end):
            arc_points.reverse()

        arc_points[0] = start
        arc_points[-1] = end
        return arc_points

    def _expand_polyline_vertices(
        self,
        vertices: List[Tuple[float, float, float]],
        closed: bool,
    ) -> List[Tuple[float, float]]:
        """
        Expand a bulged polyline into explicit point geometry.
        """
        if len(vertices) < 2:
            return []

        points: List[Tuple[float, float]] = []
        segment_count = len(vertices) if closed else len(vertices) - 1

        for index in range(segment_count):
            start_x, start_y, bulge = vertices[index]
            next_index = (index + 1) % len(vertices)
            end_x, end_y, _ = vertices[next_index]
            segment_points = self._expand_segment_with_bulge(
                start=(start_x, start_y),
                end=(end_x, end_y),
                bulge=bulge,
            )
            if not segment_points:
                continue
            if not points:
                points.extend(segment_points)
            else:
                points.extend(segment_points[1:])

        if closed and points and not self._points_close(points[0], points[-1]):
            points.append(points[0])
        return points

    # =========================
    # ØªØ­Ù…ÙŠÙ„ Ù…Ù„Ù DXF
    # =========================

    def _load_file(self) -> None:
        """
        ØªØ­Ù…ÙŠÙ„ Ù…Ù„Ù DXF Ù…Ø¹ Ù…Ø¹Ø§Ù„Ø¬Ø© Ø£Ø®Ø·Ø§Ø¡ Ù…Ø­Ø³Ù‘Ù†Ø©
        """
        try:
            self.doc = ezdxf.readfile(self.file_path)
            self.msp = self.doc.modelspace()
            print(f"âœ… ØªÙ… ØªØ­Ù…ÙŠÙ„ Ù…Ù„Ù DXF: {self.file_path}")
            
        except IOError as e:
            raise RuntimeError(
                f"âŒ ØªØ¹Ø°Ù‘Ø± Ù‚Ø±Ø§Ø¡Ø© Ù…Ù„Ù DXF ÙÙŠ Ø§Ù„Ù…Ø³Ø§Ø±:\n"
                f"   {self.file_path}\n"
                f"   Ø§Ù„Ø³Ø¨Ø¨: {str(e)}\n"
                f"   ÙŠØ±Ø¬Ù‰ Ø§Ù„ØªØ£ÙƒØ¯ Ù…Ù† ÙˆØ¬ÙˆØ¯ Ø§Ù„Ù…Ù„Ù ÙˆØµÙ„Ø§Ø­ÙŠØ§Øª Ø§Ù„Ù‚Ø±Ø§Ø¡Ø©."
            )
        except ezdxf.DXFStructureError as e:
            raise RuntimeError(
                f"âŒ Ù…Ù„Ù DXF ØªØ§Ù„Ù Ø£Ùˆ ØºÙŠØ± ØµØ§Ù„Ø­:\n"
                f"   {self.file_path}\n"
                f"   Ø§Ù„Ø³Ø¨Ø¨: {str(e)}\n"
                f"   ÙŠØ±Ø¬Ù‰ ÙØªØ­ Ø§Ù„Ù…Ù„Ù ÙÙŠ Ø¨Ø±Ù†Ø§Ù…Ø¬ CAD Ù„Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø³Ù„Ø§Ù…ØªÙ‡."
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            raise RuntimeError(
                f"âŒ Ø®Ø·Ø£ ØºÙŠØ± Ù…ØªÙˆÙ‚Ø¹ Ø£Ø«Ù†Ø§Ø¡ ØªØ­Ù…ÙŠÙ„ DXF:\n"
                f"   {str(e)}"
            )

    # =========================
    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ø®Ø·ÙˆØ· (LINE)
    # =========================

    def get_lines(
        self,
        layer: Optional[str] = None,
        qa_collector: Optional[QACollector] = None,
    ) -> List[LineSegment]:
        """
        Ø§Ø³ØªØ®Ø±Ø§Ø¬ ÙƒÙ„ Ø§Ù„ÙƒÙŠØ§Ù†Ø§Øª Ù…Ù† Ù†ÙˆØ¹ LINE ÙƒÙ‚Ø§Ø¦Ù…Ø© LineSegment.
        
        Args:
            layer: Ø§Ø³Ù… Ø§Ù„Ø·Ø¨Ù‚Ø© (Ø§Ø®ØªÙŠØ§Ø±ÙŠ). Ø¥Ø°Ø§ ØªÙ… ØªØ­Ø¯ÙŠØ¯Ù‡ØŒ ÙŠØªÙ… Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ø®Ø·ÙˆØ· Ù…Ù† ØªÙ„Ùƒ Ø§Ù„Ø·Ø¨Ù‚Ø© ÙÙ‚Ø·.
        
        Returns:
            Ù‚Ø§Ø¦Ù…Ø© Ù…Ù† LineSegment
        """
        if self.msp is None:
            raise RuntimeError("Ù„Ù… ÙŠØªÙ… ØªØ­Ù…ÙŠÙ„ Ù…Ù„Ù DXF Ø¨Ø´ÙƒÙ„ ØµØ­ÙŠØ­.")
        self._bind_collector(qa_collector)

        # Ø¨Ù†Ø§Ø¡ Ø§Ø³ØªØ¹Ù„Ø§Ù… DXF
        if layer:
            query_str = f"LINE[layer=='{layer}']"
        else:
            query_str = "LINE"

        segments: List[LineSegment] = []
        
        try:
            for entity in self.msp.query(query_str):
                self._qa_inc("entities_seen")
                self._qa_inc_entity_type("LINE")
                # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ù†Ù‚Ø§Ø· Ø§Ù„Ø¨Ø¯Ø§ÙŠØ© ÙˆØ§Ù„Ù†Ù‡Ø§ÙŠØ© Ø¨Ø´ÙƒÙ„ Ø¢Ù…Ù†
                try:
                    start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                    end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
                    
                    # ØªØ¬Ø§Ù‡Ù„ Ø§Ù„Ø®Ø·ÙˆØ· Ø§Ù„ØªÙŠ Ù„Ù‡Ø§ Ø·ÙˆÙ„ ØµÙØ±
                    if abs(start[0] - end[0]) < 1e-6 and abs(start[1] - end[1]) < 1e-6:
                        self._qa_inc("degenerate_segments_dropped")
                        continue
                    
                    segments.append(LineSegment(start=start, end=end))
                    
                except (AttributeError, ValueError) as e:
                    self._qa_inc("invalid_entities_skipped")
                    print(f"âš ï¸  ØªØ­Ø°ÙŠØ±: ØªÙ… ØªØ¬Ø§Ù‡Ù„ Ø®Ø· ØªØ§Ù„Ù - {e}")
                    continue
                    
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            raise RuntimeError(f"Ø®Ø·Ø£ Ø£Ø«Ù†Ø§Ø¡ Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ø®Ø·ÙˆØ·: {e}")

        return segments

    # =========================
    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Polylines
    # =========================

    def get_polylines(
        self,
        layer: Optional[str] = None,
        qa_collector: Optional[QACollector] = None,
    ) -> List[PolylinePath]:
        """
        Ø§Ø³ØªØ®Ø±Ø§Ø¬ LWPOLYLINE Ùˆ POLYLINE ÙƒÙ…Ø³Ø§Ø±Ø§Øª Ù†Ù‚Ø§Ø·.
        
        Args:
            layer: Ø§Ø³Ù… Ø§Ù„Ø·Ø¨Ù‚Ø© (Ø§Ø®ØªÙŠØ§Ø±ÙŠ)
        
        Returns:
            Ù‚Ø§Ø¦Ù…Ø© Ù…Ù† PolylinePath
        """
        if self.msp is None:
            raise RuntimeError("Ù„Ù… ÙŠØªÙ… ØªØ­Ù…ÙŠÙ„ Ù…Ù„Ù DXF Ø¨Ø´ÙƒÙ„ ØµØ­ÙŠØ­.")
        self._bind_collector(qa_collector)

        paths: List[PolylinePath] = []

        # Ø§Ø³ØªØ¹Ù„Ø§Ù…Ø§Øª DXF
        if layer:
            query_lw = f"LWPOLYLINE[layer=='{layer}']"
            query_pl = f"POLYLINE[layer=='{layer}']"
        else:
            query_lw = "LWPOLYLINE"
            query_pl = "POLYLINE"

        # ========== LWPOLYLINE ==========
        try:
            for entity in self.msp.query(query_lw):
                self._qa_inc("entities_seen")
                self._qa_inc_entity_type("LWPOLYLINE")
                self._qa_inc("polylines_seen")
                self._qa_inc("lwpolylines_seen")
                try:
                    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ù†Ù‚Ø§Ø· (x, y) ÙÙ‚Ø·
                    raw_vertices = [
                        (float(v[0]), float(v[1]), float(v[2] or 0.0))
                        for v in entity.get_points("xyb")
                    ]
                    is_closed = bool(entity.closed)
                    if is_closed:
                        self._qa_inc("closed_loops_seen")
                    pts = self._expand_polyline_vertices(raw_vertices, closed=is_closed)
                    
                    # ØªØ¬Ø§Ù‡Ù„ Ø§Ù„Ù€ polylines Ø§Ù„ÙØ§Ø±ØºØ© Ø£Ùˆ Ø°Ø§Øª Ø§Ù„Ù†Ù‚Ø·Ø© Ø§Ù„ÙˆØ§Ø­Ø¯Ø©
                    if len(pts) < 2:
                        self._qa_inc("degenerate_segments_dropped")
                        continue

                    if is_closed and not self._points_close(pts[0], pts[-1]):
                        self._qa_inc("closed_loops_enforced")
                        pts.append(pts[0])
                    paths.append(PolylinePath(points=pts, closed=is_closed))
                    
                except (AttributeError, ValueError, IndexError) as e:
                    self._qa_inc("invalid_entities_skipped")
                    print(f"âš ï¸  ØªØ­Ø°ÙŠØ±: ØªÙ… ØªØ¬Ø§Ù‡Ù„ LWPOLYLINE ØªØ§Ù„Ù - {e}")
                    continue
                    
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            print(f"âš ï¸  Ø®Ø·Ø£ ÙÙŠ Ù…Ø¹Ø§Ù„Ø¬Ø© LWPOLYLINE: {e}")

        # ========== POLYLINE 2D ==========
        try:
            for entity in self.msp.query(query_pl):
                self._qa_inc("entities_seen")
                self._qa_inc_entity_type("POLYLINE")
                self._qa_inc("polylines_seen")
                try:
                    raw_vertices: List[Tuple[float, float, float]] = []
                    for vertex in entity.vertices:
                        x = float(vertex.dxf.location.x)
                        y = float(vertex.dxf.location.y)
                        bulge = float(getattr(vertex.dxf, "bulge", 0.0) or 0.0)
                        raw_vertices.append((x, y, bulge))

                    closed = bool(entity.is_closed)
                    if closed:
                        self._qa_inc("closed_loops_seen")
                    pts = self._expand_polyline_vertices(raw_vertices, closed=closed)
                    
                    if len(pts) < 2:
                        self._qa_inc("degenerate_segments_dropped")
                        continue
                    
                    if closed and not self._points_close(pts[0], pts[-1]):
                        self._qa_inc("closed_loops_enforced")
                        pts.append(pts[0])
                    paths.append(PolylinePath(points=pts, closed=closed))
                    
                except (AttributeError, ValueError) as e:
                    self._qa_inc("invalid_entities_skipped")
                    print(f"âš ï¸  ØªØ­Ø°ÙŠØ±: ØªÙ… ØªØ¬Ø§Ù‡Ù„ POLYLINE ØªØ§Ù„Ù - {e}")
                    continue
                    
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            print(f"âš ï¸  Ø®Ø·Ø£ ÙÙŠ Ù…Ø¹Ø§Ù„Ø¬Ø© POLYLINE: {e}")

        return paths

    # =========================
    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø¬Ù…ÙŠØ¹ Ø§Ù„Ù‡Ù†Ø¯Ø³Ø©
    # =========================

    def get_all_geometry(
        self,
        layer: Optional[str] = None,
        qa_collector: Optional[QACollector] = None,
    ) -> Tuple[List[LineSegment], List[PolylinePath]]:
        """
        Ø¥Ø±Ø¬Ø§Ø¹ ÙƒÙ„ Ø§Ù„Ø®Ø·ÙˆØ· + Ø§Ù„Ù€ polylines ÙÙŠ Ø§Ø³ØªØ¯Ø¹Ø§Ø¡ ÙˆØ§Ø­Ø¯.
        
        Args:
            layer: Ø§Ø³Ù… Ø§Ù„Ø·Ø¨Ù‚Ø© (Ø§Ø®ØªÙŠØ§Ø±ÙŠ)
        
        Returns:
            (lines, polylines)
        """
        self._bind_collector(qa_collector)
        self._reset_qa_runtime()
        self._scan_entity_type_counts(layer=layer)
        lines = self.get_lines(layer=layer)
        polys = self.get_polylines(layer=layer)
        self._finalize_qa_findings()
        return lines, polys

    def write_qa_report(self, workspace_root: Optional[str] = None) -> str:
        """
        Persist deterministic DXF QA payload into workspace reports.
        """
        self._finalize_qa_findings()
        return self.qa_report.write_latest(workspace_root or self.workspace_root)

    # =========================
    # Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø¨Ø³ÙŠØ·Ø© Ø¹Ù† Ø§Ù„Ù…Ù„Ù
    # =========================

    def get_basic_info(self) -> dict:
        """
        Ù…Ù„Ø®Øµ Ø¹Ù† Ù…Ø­ØªÙˆÙ‰ Ù…Ù„Ù DXF
        
        Returns:
            Ù‚Ø§Ù…ÙˆØ³ ÙŠØ­ØªÙˆÙŠ Ø¹Ù„Ù‰:
            - file: Ù…Ø³Ø§Ø± Ø§Ù„Ù…Ù„Ù
            - num_lines: Ø¹Ø¯Ø¯ Ø§Ù„Ø®Ø·ÙˆØ·
            - num_polylines: Ø¹Ø¯Ø¯ Ø§Ù„Ù€ polylines
            - total_entities: Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ÙƒÙŠØ§Ù†Ø§Øª
        """
        lines, polys = self.get_all_geometry()
        
        info = {
            "file": self.file_path,
            "num_lines": len(lines),
            "num_polylines": len(polys),
            "total_entities": len(lines) + len(polys),
        }
        
        # Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø¥Ø¶Ø§ÙÙŠØ© Ø¹Ù† Ø§Ù„Ø·Ø¨Ù‚Ø§Øª
        if self.doc:
            info["num_layers"] = len(list(self.doc.layers))
        
        return info

    # =========================
    # Ø­Ø³Ø§Ø¨ Ø­Ø¯ÙˆØ¯ Ø§Ù„Ø¨Ø§ØªØ±Ù† (Bounding Box)
    # =========================

    def get_bounds(self, layer: Optional[str] = None) -> dict:
        """
        Ø­Ø³Ø§Ø¨ Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ø¨Ø§ØªØ±Ù† ÙÙŠ Ù…Ø³Ø§Ø­Ø© DXF:
        - min_x, max_x, min_y, max_y
        - width, height
        
        Args:
            layer: Ø§Ø³Ù… Ø§Ù„Ø·Ø¨Ù‚Ø© (Ø§Ø®ØªÙŠØ§Ø±ÙŠ)
        
        Returns:
            Ù‚Ø§Ù…ÙˆØ³ ÙŠØ­ØªÙˆÙŠ Ø¹Ù„Ù‰ Ø­Ø¯ÙˆØ¯ Ø§Ù„Ø¨Ø§ØªØ±Ù†
        
        Raises:
            RuntimeError: Ø¥Ø°Ø§ Ù„Ù… ÙŠØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ Ø£ÙŠ Ù‡Ù†Ø¯Ø³Ø©
        """
        lines, polys = self.get_all_geometry(layer=layer)

        all_points: List[Tuple[float, float]] = []

        # Ø¬Ù…Ø¹ Ù†Ù‚Ø§Ø· Ø§Ù„Ø®Ø·ÙˆØ·
        for ln in lines:
            all_points.append(ln.start)
            all_points.append(ln.end)

        # Ø¬Ù…Ø¹ Ù†Ù‚Ø§Ø· Ø§Ù„Ù€ polylines
        for pl in polys:
            all_points.extend(pl.points)

        if not all_points:
            raise RuntimeError(
                f"âŒ Ù„Ù… ÙŠØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ Ø£ÙŠ Ù‡Ù†Ø¯Ø³Ø© ÙÙŠ Ù…Ù„Ù DXF:\n"
                f"   {self.file_path}\n"
                f"   ÙŠØ±Ø¬Ù‰ Ø§Ù„ØªØ£ÙƒØ¯ Ù…Ù† Ø£Ù† Ø§Ù„Ù…Ù„Ù ÙŠØ­ØªÙˆÙŠ Ø¹Ù„Ù‰ LINE Ø£Ùˆ POLYLINE."
            )

        # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ù„Ø¥Ø­Ø¯Ø§Ø«ÙŠØ§Øª
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        width = max_x - min_x
        height = max_y - min_y

        # Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ù…Ù†Ø·Ù‚ÙŠØ©
        if width <= 0 or height <= 0:
            raise RuntimeError(
                f"âŒ Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ø¨Ø§ØªØ±Ù† ØºÙŠØ± Ù…Ù†Ø·Ù‚ÙŠØ©:\n"
                f"   Ø§Ù„Ø¹Ø±Ø¶: {width:.2f}\n"
                f"   Ø§Ù„Ø§Ø±ØªÙØ§Ø¹: {height:.2f}\n"
                f"   ÙŠØ¬Ø¨ Ø£Ù† ØªÙƒÙˆÙ† Ø§Ù„Ù‚ÙŠÙ… > 0"
            )

        bounds = {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
            "width": width,
            "height": height,
        }
        
        print(f"\n{'='*60}")
        print(f"ðŸ“ Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ø¨Ø§ØªØ±Ù†:")
        print(f"   - Ø§Ù„Ø¹Ø±Ø¶ (Width):    {width:.2f} Ù…Ù…")
        print(f"   - Ø§Ù„Ø§Ø±ØªÙØ§Ø¹ (Height): {height:.2f} Ù…Ù…")
        print(f"   - X: [{min_x:.2f}, {max_x:.2f}]")
        print(f"   - Y: [{min_y:.2f}, {max_y:.2f}]")
        print(f"{'='*60}\n")
        
        return bounds

    # =========================
    # Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ø·Ø¨Ù‚Ø§Øª Ø§Ù„Ù…ØªØ§Ø­Ø©
    # =========================

    def get_available_layers(self) -> List[str]:
        """
        Ø§Ù„Ø­ØµÙˆÙ„ Ø¹Ù„Ù‰ Ù‚Ø§Ø¦Ù…Ø© Ø¨Ø£Ø³Ù…Ø§Ø¡ Ø¬Ù…ÙŠØ¹ Ø§Ù„Ø·Ø¨Ù‚Ø§Øª ÙÙŠ Ø§Ù„Ù…Ù„Ù
        
        Returns:
            Ù‚Ø§Ø¦Ù…Ø© Ø¨Ø£Ø³Ù…Ø§Ø¡ Ø§Ù„Ø·Ø¨Ù‚Ø§Øª
        """
        if self.doc is None:
            return []
        
        layers = [layer.dxf.name for layer in self.doc.layers]
        return layers

    # =========================
    # ØªÙ‚Ø±ÙŠØ± Ù…ÙØµÙ„
    # =========================

    def print_detailed_report(self):
        """
        Ø·Ø¨Ø§Ø¹Ø© ØªÙ‚Ø±ÙŠØ± Ù…ÙØµÙ„ Ø¹Ù† Ù…Ø­ØªÙˆÙ‰ Ù…Ù„Ù DXF
        """
        print(f"\n{'='*60}")
        print(f"ðŸ“„ ØªÙ‚Ø±ÙŠØ± Ù…Ù„Ù DXF:")
        print(f"{'='*60}")
        print(f"Ø§Ù„Ù…Ù„Ù: {self.file_path}")
        
        # Ø§Ù„Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø§Ù„Ø£Ø³Ø§Ø³ÙŠØ©
        info = self.get_basic_info()
        print(f"\nðŸ“Š Ø§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª:")
        print(f"   - Ø¹Ø¯Ø¯ Ø§Ù„Ø®Ø·ÙˆØ· (LINE): {info['num_lines']}")
        print(f"   - Ø¹Ø¯Ø¯ Ø§Ù„Ù€ Polylines: {info['num_polylines']}")
        print(f"   - Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ÙƒÙŠØ§Ù†Ø§Øª: {info['total_entities']}")
        
        # Ø§Ù„Ø·Ø¨Ù‚Ø§Øª
        layers = self.get_available_layers()
        if layers:
            print(f"\nðŸ“‘ Ø§Ù„Ø·Ø¨Ù‚Ø§Øª Ø§Ù„Ù…ØªØ§Ø­Ø© ({len(layers)}):")
            for layer in layers[:10]:  # Ø£ÙˆÙ„ 10 Ø·Ø¨Ù‚Ø§Øª ÙÙ‚Ø·
                print(f"   - {layer}")
            if len(layers) > 10:
                print(f"   ... Ùˆ {len(layers) - 10} Ø·Ø¨Ù‚Ø§Øª Ø£Ø®Ø±Ù‰")
        
        # Ø§Ù„Ø­Ø¯ÙˆØ¯
        try:
            bounds = self.get_bounds()
            # ØªÙ… Ø·Ø¨Ø§Ø¹ØªÙ‡Ø§ Ø¨Ø§Ù„ÙØ¹Ù„ ÙÙŠ get_bounds()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            print(f"\nâš ï¸  Ù„Ù… ÙŠØªÙ… Ø­Ø³Ø§Ø¨ Ø§Ù„Ø­Ø¯ÙˆØ¯: {e}")
        
        print(f"{'='*60}\n")

    # =========================
    # Ø¯ÙˆØ§Ù„ Ù…Ø³Ø§Ø¹Ø¯Ø© Ù„Ù„ØªØµØ¯ÙŠØ±
    # =========================

    def export_summary_to_file(self, output_path: str):
        """
        ØªØµØ¯ÙŠØ± Ù…Ù„Ø®Øµ Ø¹Ù† Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø¥Ù„Ù‰ Ù…Ù„Ù Ù†ØµÙŠ
        
        Args:
            output_path: Ù…Ø³Ø§Ø± Ù…Ù„Ù Ø§Ù„Ø¥Ø®Ø±Ø§Ø¬ (.txt)
        """
        info = self.get_basic_info()
        bounds = self.get_bounds()
        layers = self.get_available_layers()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("ØªÙ‚Ø±ÙŠØ± Ù…Ù„Ù DXF Ù„Ù„Ø¨Ø§ØªØ±Ù†\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Ø§Ù„Ù…Ù„Ù: {self.file_path}\n\n")
            
            f.write("Ø§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª:\n")
            f.write(f"  - Ø¹Ø¯Ø¯ Ø§Ù„Ø®Ø·ÙˆØ·: {info['num_lines']}\n")
            f.write(f"  - Ø¹Ø¯Ø¯ Ø§Ù„Ù€ Polylines: {info['num_polylines']}\n")
            f.write(f"  - Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ÙƒÙŠØ§Ù†Ø§Øª: {info['total_entities']}\n\n")
            
            f.write("Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯:\n")
            f.write(f"  - Ø§Ù„Ø¹Ø±Ø¶: {bounds['width']:.2f} Ù…Ù…\n")
            f.write(f"  - Ø§Ù„Ø§Ø±ØªÙØ§Ø¹: {bounds['height']:.2f} Ù…Ù…\n")
            f.write(f"  - X: [{bounds['min_x']:.2f}, {bounds['max_x']:.2f}]\n")
            f.write(f"  - Y: [{bounds['min_y']:.2f}, {bounds['max_y']:.2f}]\n\n")
            
            if layers:
                f.write(f"Ø§Ù„Ø·Ø¨Ù‚Ø§Øª ({len(layers)}):\n")
                for layer in layers:
                    f.write(f"  - {layer}\n")
            
            f.write("\n" + "=" * 60 + "\n")
        
        print(f"âœ… ØªÙ… Ø­ÙØ¸ Ø§Ù„ØªÙ‚Ø±ÙŠØ±: {output_path}")


# =========================
# Ø¯ÙˆØ§Ù„ Ù…Ø³Ø§Ø¹Ø¯Ø© (Utility Functions)
# =========================

def validate_pattern_file(file_path: str) -> bool:
    """
    Ø§Ù„ØªØ­Ù‚Ù‚ Ø§Ù„Ø³Ø±ÙŠØ¹ Ù…Ù† ØµÙ„Ø§Ø­ÙŠØ© Ù…Ù„Ù DXF Ù„Ù„Ø¨Ø§ØªØ±Ù†
    
    Args:
        file_path: Ù…Ø³Ø§Ø± Ù…Ù„Ù DXF
    
    Returns:
        True Ø¥Ø°Ø§ ÙƒØ§Ù† Ø§Ù„Ù…Ù„Ù ØµØ§Ù„Ø­Ø§Ù‹ØŒ False Ø®Ù„Ø§Ù Ø°Ù„Ùƒ
    """
    try:
        reader = PatternDXFReader(file_path)
        info = reader.get_basic_info()
        
        if info['total_entities'] == 0:
            print(f"âš ï¸  Ø§Ù„Ù…Ù„Ù Ù„Ø§ ÙŠØ­ØªÙˆÙŠ Ø¹Ù„Ù‰ Ø£ÙŠ ÙƒÙŠØ§Ù†Ø§Øª!")
            return False
        
        bounds = reader.get_bounds()
        
        if bounds['width'] < 10 or bounds['height'] < 10:
            print(f"âš ï¸  Ø§Ù„Ø¨Ø§ØªØ±Ù† ØµØºÙŠØ± Ø¬Ø¯Ø§Ù‹: {bounds['width']}x{bounds['height']}")
            return False
        
        print(f"âœ… Ø§Ù„Ù…Ù„Ù ØµØ§Ù„Ø­: {info['total_entities']} ÙƒÙŠØ§Ù†")
        return True
        
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
        print(f"âŒ ÙØ´Ù„ Ø§Ù„ØªØ­Ù‚Ù‚: {e}")
        return False


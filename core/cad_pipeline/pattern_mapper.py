from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Polygon,
)

from .geometry_engine import PanelFlatPattern
from .dxf_handler import LineSegment, PolylinePath
from .qa_report import QAReportV1


@dataclass
class MappedLine:
    """
    Ø®Ø· Ø¨Ø¹Ø¯ ØªØ­ÙˆÙŠÙ„Ù‡ Ù…Ù† Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ù…Ø³ØªØ·ÙŠÙ„ Ø¥Ù„Ù‰ Ø§Ù„Ù‚ÙˆØ³ Ø§Ù„Ù…ÙØ±ÙˆØ¯.
    """
    start: Tuple[float, float]
    end: Tuple[float, float]


@dataclass
class MappedPolyline:
    """
    Polyline Ø¨Ø¹Ø¯ ØªØ­ÙˆÙŠÙ„ Ù†Ù‚Ø§Ø·Ù‡ Ø¥Ù„Ù‰ Ø§Ù„Ù‚ÙˆØ³ Ø§Ù„Ù…ÙØ±ÙˆØ¯.
    """
    points: List[Tuple[float, float]]
    closed: bool = False


_POINT_EPSILON = 1e-8
_SAFE_ZONE_SAMPLING_SEGMENTS = 2048


class PatternMapper:
    """
    Ù…Ø­ÙˆÙ„ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ù…ÙØ­Ø³Ù‘Ù†:
    - ÙŠØ­ÙˆÙ„ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ù…Ø³ØªØ·ÙŠÙ„ Ø¥Ù„Ù‰ Ù‚ÙˆØ³ Ù…ÙØ±ÙˆØ¯
    - Ø®ÙˆØ§Ø±Ø²Ù…ÙŠØ© Ø¯Ù‚ÙŠÙ‚Ø© Ù„Ù„Ù€ mapping
    - Ø¯Ø¹Ù… Ù„Ù„ØªØ¯ÙˆÙŠØ± ÙˆØ§Ù„Ù…Ø­Ø§Ø°Ø§Ø©
    - Ù…Ø¹Ø§Ù„Ø¬Ø© Ø§Ù„ØªØ´ÙˆÙ‡Ø§Øª Ø¹Ù†Ø¯ Ø§Ù„Ø­ÙˆØ§Ù
    - Ø¥Ù…ÙƒØ§Ù†ÙŠØ© Ø§Ù„ØªØ­ÙƒÙ… ÙÙŠ ÙƒØ«Ø§ÙØ© Ø§Ù„Ù†Ù‚Ø§Ø·
    """

    def __init__(
        self,
        panel_flat: PanelFlatPattern,
        pattern_width: float,
        pattern_height: float,
        min_x: float = 0.0,
        min_y: float = 0.0,
        preserve_aspect_ratio: bool = True,
        interpolation_density: int = 1,
    ):
        """
        Args:
            panel_flat: Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø¥ÙØ±Ø§Ø¯ Ù„Ù„ÙˆØ­ Ø§Ù„Ù‡Ø¯Ù
            pattern_width: Ø¹Ø±Ø¶ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ø£ØµÙ„ÙŠ (Ù…Ù…)
            pattern_height: Ø§Ø±ØªÙØ§Ø¹ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ø£ØµÙ„ÙŠ (Ù…Ù…)
            min_x: Ø£Ù‚Ù„ Ù‚ÙŠÙ…Ø© X ÙÙŠ Ø§Ù„Ø¨Ø§ØªØ±Ù†
            min_y: Ø£Ù‚Ù„ Ù‚ÙŠÙ…Ø© Y ÙÙŠ Ø§Ù„Ø¨Ø§ØªØ±Ù†
            preserve_aspect_ratio: Ø§Ù„Ø­ÙØ§Ø¸ Ø¹Ù„Ù‰ Ù†Ø³Ø¨Ø© Ø§Ù„Ø¹Ø±Ø¶ Ù„Ù„Ø§Ø±ØªÙØ§Ø¹
            interpolation_density: ÙƒØ«Ø§ÙØ© Ù†Ù‚Ø§Ø· Ø§Ù„Ø¥Ø¶Ø§ÙÙŠØ© (1=Ø¹Ø§Ø¯ÙŠ, 2+=Ø²ÙŠØ§Ø¯Ø©)
        """
        if pattern_width <= 0 or pattern_height <= 0:
            raise ValueError(
                f"Ø£Ø¨Ø¹Ø§Ø¯ Ø§Ù„Ø¨Ø§ØªØ±Ù† ÙŠØ¬Ø¨ Ø£Ù† ØªÙƒÙˆÙ† > 0:\n"
                f"  Ø§Ù„Ø¹Ø±Ø¶: {pattern_width}\n"
                f"  Ø§Ù„Ø§Ø±ØªÙØ§Ø¹: {pattern_height}"
            )

        self.panel_flat = panel_flat
        self.pattern_width = pattern_width
        self.pattern_height = pattern_height
        self.min_x = min_x
        self.min_y = min_y
        self.preserve_aspect_ratio = preserve_aspect_ratio
        self.interpolation_density = max(1, interpolation_density)
        
        # Ø­Ø³Ø§Ø¨ Ù…Ø¹Ø§Ù…Ù„Ø§Øª Ø§Ù„ØªØ­ÙˆÙŠÙ„
        self._compute_transform_params()
        self._safe_zone_polygon = self._build_safe_zone_polygon()
        
        # Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª
        self.stats = {
            "lines_mapped": 0,
            "polylines_mapped": 0,
            "points_mapped": 0,
        }
        minx, miny, maxx, maxy = self._safe_zone_polygon.bounds
        self._clip_metrics: Dict[str, Any] = {
            "safe_zone": {
                "minx": float(minx),
                "miny": float(miny),
                "maxx": float(maxx),
                "maxy": float(maxy),
            },
            "closed_inputs": 0,
            "open_inputs": 0,
            "closed_outputs": 0,
            "open_outputs": 0,
            "fragmentation_events": 0,
            "geometry_collections": 0,
            "multi_geometries": 0,
            "ring_closure_repairs": 0,
            "num_inputs": 0,
            "num_clipped": 0,
            "geom_types_seen": {},
        }

    # =========================
    # Ø­Ø³Ø§Ø¨ Ù…Ø¹Ø§Ù…Ù„Ø§Øª Ø§Ù„ØªØ­ÙˆÙŠÙ„
    # =========================

    def _compute_transform_params(self):
        """
        Ø­Ø³Ø§Ø¨ Ø§Ù„Ù…Ø¹Ø§Ù…Ù„Ø§Øª Ø§Ù„Ù…Ø·Ù„ÙˆØ¨Ø© Ù„Ù„ØªØ­ÙˆÙŠÙ„
        """
        # Ø§Ù„Ø²Ø§ÙˆÙŠØ© Ø§Ù„ÙƒÙ„ÙŠØ© Ø¨Ø§Ù„Ø±Ø§Ø¯ÙŠØ§Ù†
        self.theta_total_rad = math.radians(self.panel_flat.arc_angle)
        
        # Ù†Ø·Ø§Ù‚ Ù†ØµÙ Ø§Ù„Ù‚Ø·Ø± Ø§Ù„ÙØ¹Ø§Ù„ (Ø¨Ø¹Ø¯ Ø®ØµÙ… safe zone)
        self.r_inner_eff = self.panel_flat.r_inner + self.panel_flat.safe_zone
        self.r_outer_eff = self.panel_flat.r_outer - self.panel_flat.safe_zone
        
        # Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† Ù…Ù†Ø·Ù‚ÙŠØ© Ø§Ù„Ù†Ø·Ø§Ù‚
        if self.r_outer_eff <= self.r_inner_eff:
            # ØªØ¹Ø¯ÙŠÙ„ ØªÙ„Ù‚Ø§Ø¦ÙŠ
            avg = (self.panel_flat.r_inner + self.panel_flat.r_outer) / 2.0
            margin = min(10.0, self.panel_flat.safe_zone / 2.0)
            self.r_inner_eff = avg - margin
            self.r_outer_eff = avg + margin
            
            print(f"âš ï¸  ØªØ­Ø°ÙŠØ±: safe_zone ÙƒØ¨ÙŠØ±Ø© Ø¬Ø¯Ø§Ù‹. ØªÙ… Ø§Ù„ØªØ¹Ø¯ÙŠÙ„ Ø§Ù„ØªÙ„Ù‚Ø§Ø¦ÙŠ:")
            print(f"   r_inner_eff: {self.r_inner_eff:.2f}")
            print(f"   r_outer_eff: {self.r_outer_eff:.2f}")
        
        # Ù†Ø·Ø§Ù‚ Ù†ØµÙ Ø§Ù„Ù‚Ø·Ø±
        self.r_range = self.r_outer_eff - self.r_inner_eff
        
        # Ù†Ø³Ø¨Ø© Ø§Ù„Ø¹Ø±Ø¶ Ù„Ù„Ø§Ø±ØªÙØ§Ø¹
        self.aspect_ratio = self.pattern_width / self.pattern_height if self.pattern_height > 0 else 1.0

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

    def _point_sort_key(self, point: Tuple[float, float]) -> Tuple[float, float]:
        return (round(point[0], 9), round(point[1], 9))

    def _dedupe_consecutive(
        self,
        points: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        deduped: List[Tuple[float, float]] = []
        for point in points:
            candidate = (float(point[0]), float(point[1]))
            if not deduped or not self._points_close(deduped[-1], candidate):
                deduped.append(candidate)
        return deduped

    def _signed_area(self, points: List[Tuple[float, float]]) -> float:
        if len(points) < 3:
            return 0.0
        area = 0.0
        for index in range(len(points)):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % len(points)]
            area += (x1 * y2) - (x2 * y1)
        return 0.5 * area

    def _normalize_open_points(
        self,
        points: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        normalized = self._dedupe_consecutive(points)
        if len(normalized) < 2:
            return []
        if self._point_sort_key(normalized[-1]) < self._point_sort_key(normalized[0]):
            normalized.reverse()
        return normalized

    def _normalize_closed_ring(
        self,
        points: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        normalized = self._dedupe_consecutive(points)
        if len(normalized) < 3:
            return []

        if self._points_close(normalized[0], normalized[-1]):
            normalized = normalized[:-1]
        if len(normalized) < 3:
            return []

        min_index = min(range(len(normalized)), key=lambda idx: self._point_sort_key(normalized[idx]))
        normalized = normalized[min_index:] + normalized[:min_index]

        if self._signed_area(normalized) < 0.0:
            normalized = list(reversed(normalized))
            min_index = min(range(len(normalized)), key=lambda idx: self._point_sort_key(normalized[idx]))
            normalized = normalized[min_index:] + normalized[:min_index]

        normalized.append(normalized[0])
        return normalized if len(normalized) >= 4 else []

    def _build_safe_zone_polygon(self) -> Polygon:
        """
        Build a polygonal approximation of the panel safe zone.
        """
        arc_ratio = abs(self.theta_total_rad) / (2.0 * math.pi) if self.theta_total_rad else 1.0
        num_segments = max(32, int(math.ceil(_SAFE_ZONE_SAMPLING_SEGMENTS * arc_ratio)))

        outer_points: List[Tuple[float, float]] = []
        inner_points: List[Tuple[float, float]] = []
        for index in range(num_segments + 1):
            theta = self.theta_total_rad * (index / num_segments)
            cos_theta = math.cos(theta)
            sin_theta = math.sin(theta)
            outer_points.append((self.r_outer_eff * cos_theta, self.r_outer_eff * sin_theta))
            inner_points.append((self.r_inner_eff * cos_theta, self.r_inner_eff * sin_theta))

        ring = outer_points + list(reversed(inner_points))
        polygon = Polygon(ring)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        return polygon

    def _extract_polygon_geometries(self, geometry) -> List[Polygon]:
        if geometry.is_empty:
            return []
        if isinstance(geometry, Polygon):
            return [geometry]
        if isinstance(geometry, MultiPolygon):
            polygons: List[Polygon] = []
            for polygon in geometry.geoms:
                polygons.extend(self._extract_polygon_geometries(polygon))
            return polygons
        if isinstance(geometry, GeometryCollection):
            polygons: List[Polygon] = []
            for sub_geometry in geometry.geoms:
                polygons.extend(self._extract_polygon_geometries(sub_geometry))
            return polygons
        return []

    def _extract_line_geometries(self, geometry) -> List[LineString]:
        if geometry.is_empty:
            return []
        if isinstance(geometry, LineString):
            return [geometry]
        if isinstance(geometry, MultiLineString):
            lines: List[LineString] = []
            for line in geometry.geoms:
                lines.extend(self._extract_line_geometries(line))
            return lines
        if isinstance(geometry, GeometryCollection):
            lines: List[LineString] = []
            for sub_geometry in geometry.geoms:
                lines.extend(self._extract_line_geometries(sub_geometry))
            return lines
        return []

    def _clip_inc(self, key: str, amount: int = 1) -> None:
        current = int(self._clip_metrics.get(key) or 0)
        self._clip_metrics[key] = current + int(amount)

    def _track_geometry_shape(self, geometry: Any) -> None:
        if geometry is None or geometry.is_empty:
            return
        geom_types = self._clip_metrics.get("geom_types_seen")
        if not isinstance(geom_types, dict):
            geom_types = {}
            self._clip_metrics["geom_types_seen"] = geom_types
        geom_name = str(getattr(geometry, "geom_type", "Unknown") or "Unknown")
        geom_types[geom_name] = int(geom_types.get(geom_name) or 0) + 1
        if isinstance(geometry, GeometryCollection):
            self._clip_inc("geometry_collections")
            for sub_geometry in geometry.geoms:
                self._track_geometry_shape(sub_geometry)
            return
        if isinstance(geometry, (MultiPolygon, MultiLineString)):
            self._clip_inc("multi_geometries")
            for sub_geometry in geometry.geoms:
                self._track_geometry_shape(sub_geometry)

    def get_clip_metrics(self) -> Dict[str, Any]:
        num_inputs = int(self._clip_metrics.get("closed_inputs") or 0) + int(
            self._clip_metrics.get("open_inputs") or 0
        )
        num_clipped = int(self._clip_metrics.get("closed_outputs") or 0) + int(
            self._clip_metrics.get("open_outputs") or 0
        )
        return {
            "safe_zone": dict(self._clip_metrics.get("safe_zone") or {}),
            "closed_inputs": int(self._clip_metrics.get("closed_inputs") or 0),
            "open_inputs": int(self._clip_metrics.get("open_inputs") or 0),
            "closed_outputs": int(self._clip_metrics.get("closed_outputs") or 0),
            "open_outputs": int(self._clip_metrics.get("open_outputs") or 0),
            "fragmentation_events": int(self._clip_metrics.get("fragmentation_events") or 0),
            "geometry_collections": int(self._clip_metrics.get("geometry_collections") or 0),
            "multi_geometries": int(self._clip_metrics.get("multi_geometries") or 0),
            "ring_closure_repairs": int(self._clip_metrics.get("ring_closure_repairs") or 0),
            "num_inputs": num_inputs,
            "num_clipped": num_clipped,
            "geom_types_seen": dict(self._clip_metrics.get("geom_types_seen") or {}),
        }

    def _clip_open_points(
        self,
        points: List[Tuple[float, float]],
    ) -> List[List[Tuple[float, float]]]:
        self._clip_inc("open_inputs")
        if len(points) < 2:
            return []

        clipped = LineString(points).intersection(self._safe_zone_polygon)
        self._track_geometry_shape(clipped)
        lines = self._extract_line_geometries(clipped)
        output: List[List[Tuple[float, float]]] = []
        for line in lines:
            normalized = self._normalize_open_points(list(line.coords))
            if len(normalized) >= 2:
                output.append(normalized)

        self._clip_inc("open_outputs", len(output))
        if len(output) > 1:
            self._clip_inc("fragmentation_events", len(output) - 1)

        output.sort(
            key=lambda item: (
                self._point_sort_key(item[0]),
                self._point_sort_key(item[-1]),
                len(item),
            )
        )
        return output

    def _clip_closed_points(
        self,
        points: List[Tuple[float, float]],
    ) -> List[MappedPolyline]:
        self._clip_inc("closed_inputs")
        if len(points) < 3:
            return []

        ring = self._dedupe_consecutive(points)
        if len(ring) < 3:
            return []
        if not self._points_close(ring[0], ring[-1]):
            self._clip_inc("ring_closure_repairs")
            ring.append(ring[0])

        source_polygon = Polygon(ring)
        if source_polygon.is_empty:
            return []
        if not source_polygon.is_valid:
            source_polygon = source_polygon.buffer(0)

        clipped = source_polygon.intersection(self._safe_zone_polygon)
        self._track_geometry_shape(clipped)
        polygon_parts = self._extract_polygon_geometries(clipped)

        mapped: List[MappedPolyline] = []
        for polygon in polygon_parts:
            exterior_coords = list(polygon.exterior.coords)
            if exterior_coords and not self._points_close(exterior_coords[0], exterior_coords[-1]):
                self._clip_inc("ring_closure_repairs")
            exterior = self._normalize_closed_ring(exterior_coords)
            if exterior:
                mapped.append(MappedPolyline(points=exterior, closed=True))
            for hole in polygon.interiors:
                interior_coords = list(hole.coords)
                if interior_coords and not self._points_close(interior_coords[0], interior_coords[-1]):
                    self._clip_inc("ring_closure_repairs")
                interior = self._normalize_closed_ring(interior_coords)
                if interior:
                    mapped.append(MappedPolyline(points=interior, closed=True))

        self._clip_inc("closed_outputs", len(mapped))
        if len(mapped) > 1:
            self._clip_inc("fragmentation_events", len(mapped) - 1)

        mapped.sort(
            key=lambda poly: (
                self._point_sort_key(poly.points[0]) if poly.points else (0.0, 0.0),
                len(poly.points),
            )
        )
        return mapped

    def _map_polyline_segments(self, poly: PolylinePath) -> List[MappedPolyline]:
        if self.interpolation_density > 1:
            source_points = self._interpolate_polyline(poly.points)
        else:
            source_points = list(poly.points)

        mapped_points = [self._map_point(point, clamp=False) for point in source_points]
        is_closed = bool(poly.closed) or (
            len(mapped_points) > 2 and self._points_close(mapped_points[0], mapped_points[-1])
        )

        self.stats["polylines_mapped"] += 1

        if is_closed:
            clipped = self._clip_closed_points(mapped_points)
            self.stats["points_mapped"] += sum(len(item.points) for item in clipped)
            return clipped

        clipped_segments = self._clip_open_points(mapped_points)
        output = [MappedPolyline(points=segment, closed=False) for segment in clipped_segments]
        self.stats["points_mapped"] += sum(len(item.points) for item in output)
        return output

    # =========================
    # ÙˆØ§Ø¬Ù‡Ø© Ø¹Ø§Ù…Ø© Ù„Ù„ØªØ­ÙˆÙŠÙ„
    # =========================

    def map_line(self, line: LineSegment) -> MappedLine:
        """
        ØªØ­ÙˆÙŠÙ„ Ø®Ø· ÙˆØ§Ø­Ø¯ Ù…Ù† Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ù…Ø³ØªØ·ÙŠÙ„ Ø¥Ù„Ù‰ Ø§Ù„Ù‚ÙˆØ³
        
        Args:
            line: Ø§Ù„Ø®Ø· Ø§Ù„Ù…Ø±Ø§Ø¯ ØªØ­ÙˆÙŠÙ„Ù‡
        
        Returns:
            Ø§Ù„Ø®Ø· Ø§Ù„Ù…Ø­ÙˆÙ„
        """
        mapped_lines = self.map_lines([line])
        if mapped_lines:
            return mapped_lines[0]

        start_mapped = self._map_point(line.start, clamp=True)
        end_mapped = self._map_point(line.end, clamp=True)
        return MappedLine(start=start_mapped, end=end_mapped)

    def map_polyline(self, poly: PolylinePath) -> MappedPolyline:
        """
        Map a polyline and preserve closure semantics after safe-zone clipping.
        """
        mapped_polylines = self._map_polyline_segments(poly)
        if mapped_polylines:
            return mapped_polylines[0]
        return MappedPolyline(points=[], closed=bool(poly.closed))

    def map_lines(self, lines: List[LineSegment]) -> List[MappedLine]:
        """
        Map and clip open entities against the safe-zone boundary.
        """
        output: List[MappedLine] = []
        for line in lines:
            mapped_start = self._map_point(line.start, clamp=False)
            mapped_end = self._map_point(line.end, clamp=False)
            clipped_segments = self._clip_open_points([mapped_start, mapped_end])

            self.stats["lines_mapped"] += 1

            if not clipped_segments:
                continue

            for segment in clipped_segments:
                if len(segment) < 2:
                    continue
                output.append(MappedLine(start=segment[0], end=segment[-1]))
                self.stats["points_mapped"] += len(segment)

        return output

    def map_polylines(self, polys: List[PolylinePath]) -> List[MappedPolyline]:
        """
        Map polylines and preserve closed-ring semantics through clipping.
        """
        output: List[MappedPolyline] = []
        for polyline in polys:
            output.extend(self._map_polyline_segments(polyline))
        return output

    # =========================
    # Ù‚Ù„Ø¨ Ø®ÙˆØ§Ø±Ø²Ù…ÙŠØ© Ø§Ù„ØªØ­ÙˆÙŠÙ„
    # =========================

    def _map_point(self, pt: Tuple[float, float], clamp: bool = False) -> Tuple[float, float]:
        """
        ØªØ­ÙˆÙŠÙ„ Ù†Ù‚Ø·Ø© (x, y) Ù…Ù† Ù…Ø³Ø§Ø­Ø© Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ù…Ø³ØªØ·ÙŠÙ„ Ø¥Ù„Ù‰ Ø§Ù„Ù‚ÙˆØ³ Ø§Ù„Ù…ÙØ±ÙˆØ¯
        
        Ø§Ù„Ø®ÙˆØ§Ø±Ø²Ù…ÙŠØ©:
        1. ØªØ·Ø¨ÙŠØ¹ Ø§Ù„Ù†Ù‚Ø·Ø© Ø¥Ù„Ù‰ Ù†Ø·Ø§Ù‚ [0, 1]
        2. ØªØ­ÙˆÙŠÙ„ u Ø¥Ù„Ù‰ Ø²Ø§ÙˆÙŠØ© Î¸
        3. ØªØ­ÙˆÙŠÙ„ v Ø¥Ù„Ù‰ Ù†ØµÙ Ù‚Ø·Ø± r
        4. ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ù‚Ø·Ø¨ÙŠ (r, Î¸) Ø¥Ù„Ù‰ Ø¯ÙŠÙƒØ§Ø±ØªÙŠ (X, Y)
        
        Args:
            pt: Ø§Ù„Ù†Ù‚Ø·Ø© Ø§Ù„Ø£ØµÙ„ÙŠØ© (x, y)
        
        Returns:
            Ø§Ù„Ù†Ù‚Ø·Ø© Ø§Ù„Ù…Ø­ÙˆÙ„Ø© (X, Y)
        """
        x, y = pt

        # 1. Ø§Ù„ØªØ·Ø¨ÙŠØ¹ Ø¥Ù„Ù‰ Ù†Ø·Ø§Ù‚ [0, 1]
        u = (x - self.min_x) / self.pattern_width   # Ø§ØªØ¬Ø§Ù‡ Ø§Ù„Ø²Ø§ÙˆÙŠØ©
        v = (y - self.min_y) / self.pattern_height  # Ø§ØªØ¬Ø§Ù‡ Ù†ØµÙ Ø§Ù„Ù‚Ø·Ø±

        if clamp:
            # Legacy fallback path for callers that need bounded mapping.
            u = max(0.0, min(1.0, u))
            v = max(0.0, min(1.0, v))

        # 2. Ø­Ø³Ø§Ø¨ Ø§Ù„Ø²Ø§ÙˆÙŠØ© (Î¸)
        theta = u * self.theta_total_rad

        # 3. Ø­Ø³Ø§Ø¨ Ù†ØµÙ Ø§Ù„Ù‚Ø·Ø± (r)
        # Ø§Ù„ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ø®Ø·ÙŠ Ù…Ù† v Ø¥Ù„Ù‰ Ù†Ø·Ø§Ù‚ Ù†ØµÙ Ø§Ù„Ù‚Ø·Ø±
        r = self.r_inner_eff + v * self.r_range

        # 4. Ø§Ù„ØªØ­ÙˆÙŠÙ„ Ù…Ù† Ø§Ù„Ù‚Ø·Ø¨ÙŠ Ø¥Ù„Ù‰ Ø§Ù„Ø¯ÙŠÙƒØ§Ø±ØªÙŠ
        X = r * math.cos(theta)
        Y = r * math.sin(theta)

        return (X, Y)

    # =========================
    # Ø¥Ø¶Ø§ÙØ© Ù†Ù‚Ø§Ø· Ø¥Ø¶Ø§ÙÙŠØ© (Interpolation)
    # =========================

    def _interpolate_polyline(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Ø¥Ø¶Ø§ÙØ© Ù†Ù‚Ø§Ø· Ø¥Ø¶Ø§ÙÙŠØ© Ø¨ÙŠÙ† ÙƒÙ„ Ù†Ù‚Ø·ØªÙŠÙ† ÙÙŠ Ø§Ù„Ù€ polyline
        Ù„ØªØ­Ø³ÙŠÙ† Ø¬ÙˆØ¯Ø© Ø§Ù„Ø§Ù†Ø­Ù†Ø§Ø¡ Ø¨Ø¹Ø¯ Ø§Ù„ØªØ­ÙˆÙŠÙ„
        
        Args:
            points: Ø§Ù„Ù†Ù‚Ø§Ø· Ø§Ù„Ø£ØµÙ„ÙŠØ©
        
        Returns:
            Ù†Ù‚Ø§Ø· Ù…Ø¹ Ø¥Ø¶Ø§ÙØ© Ù†Ù‚Ø§Ø· ÙˆØ³Ø·ÙŠØ©
        """
        if len(points) < 2:
            return points
        
        interpolated = []
        
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            
            # Ø¥Ø¶Ø§ÙØ© Ø§Ù„Ù†Ù‚Ø·Ø© Ø§Ù„Ø£ÙˆÙ„Ù‰
            interpolated.append(p1)
            
            # Ø¥Ø¶Ø§ÙØ© Ù†Ù‚Ø§Ø· ÙˆØ³Ø·ÙŠØ©
            for j in range(1, self.interpolation_density):
                t = j / self.interpolation_density
                x_mid = p1[0] + t * (p2[0] - p1[0])
                y_mid = p1[1] + t * (p2[1] - p1[1])
                interpolated.append((x_mid, y_mid))
        
        # Ø¥Ø¶Ø§ÙØ© Ø§Ù„Ù†Ù‚Ø·Ø© Ø§Ù„Ø£Ø®ÙŠØ±Ø©
        interpolated.append(points[-1])
        
        return interpolated

    # =========================
    # Ø¯ÙˆØ§Ù„ Ù…Ø³Ø§Ø¹Ø¯Ø©
    # =========================

    def get_mapping_stats(self) -> dict:
        """
        Ø§Ù„Ø­ØµÙˆÙ„ Ø¹Ù„Ù‰ Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª Ø§Ù„ØªØ­ÙˆÙŠÙ„
        
        Returns:
            Ù‚Ø§Ù…ÙˆØ³ Ø¨Ø§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª
        """
        return {
            **self.stats,
            "panel_id": self.panel_flat.panel_id,
            "panel_type": self.panel_flat.panel_type,
            "arc_angle": self.panel_flat.arc_angle,
            "r_inner_eff": self.r_inner_eff,
            "r_outer_eff": self.r_outer_eff,
        }

    def print_mapping_info(self):
        """
        Ø·Ø¨Ø§Ø¹Ø© Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø¹Ù† Ø¹Ù…Ù„ÙŠØ© Ø§Ù„ØªØ­ÙˆÙŠÙ„
        """
        print(f"\n{'='*60}")
        print(f"ðŸ”„ Ù…Ø¹Ù„ÙˆÙ…Ø§Øª ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ø¨Ø§ØªØ±Ù† - Ù„ÙˆØ­ {self.panel_flat.panel_id}")
        print(f"{'='*60}")
        print(f"Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø§Ù„Ø£ØµÙ„ÙŠ:")
        print(f"  - Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯: {self.pattern_width:.0f} Ã— {self.pattern_height:.0f} Ù…Ù…")
        print(f"  - Ù†Ø³Ø¨Ø© Ø§Ù„Ø£Ø¨Ø¹Ø§Ø¯: {self.aspect_ratio:.2f}")
        print(f"\nØ§Ù„Ù„ÙˆØ­ Ø§Ù„Ù‡Ø¯Ù:")
        print(f"  - Ø§Ù„Ù†ÙˆØ¹: {self.panel_flat.panel_type}")
        print(f"  - Ø²Ø§ÙˆÙŠØ© Ø§Ù„Ù‚ÙˆØ³: {self.panel_flat.arc_angle:.2f}Â°")
        print(f"  - Ù†Ø·Ø§Ù‚ Ù†ØµÙ Ø§Ù„Ù‚Ø·Ø±: [{self.r_inner_eff:.0f}, {self.r_outer_eff:.0f}]")
        print(f"\nØ§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª:")
        print(f"  - Ø®Ø·ÙˆØ· Ù…Ø­ÙˆÙ„Ø©: {self.stats['lines_mapped']}")
        print(f"  - polylines Ù…Ø­ÙˆÙ„Ø©: {self.stats['polylines_mapped']}")
        print(f"  - Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ù†Ù‚Ø§Ø·: {self.stats['points_mapped']}")
        print(f"{'='*60}\n")

    def reset_stats(self):
        """
        Ø¥Ø¹Ø§Ø¯Ø© ØªØ¹ÙŠÙŠÙ† Ø§Ù„Ø¥Ø­ØµØ§Ø¦ÙŠØ§Øª
        """
        self.stats = {
            "lines_mapped": 0,
            "polylines_mapped": 0,
            "points_mapped": 0,
        }


# Alias used by downstream callers that refer to the clipping stage as projector.
PatternProjector = PatternMapper


# =========================
# Ø¯ÙˆØ§Ù„ Ù…Ø³Ø§Ø¹Ø¯Ø© Ø¹Ø§Ù…Ø©
# =========================

def create_mapper_for_panel(
    panel_flat: PanelFlatPattern,
    pattern_bounds: dict,
    interpolation_density: int = 2
) -> PatternMapper:
    """
    Ø¥Ù†Ø´Ø§Ø¡ mapper Ø¬Ø§Ù‡Ø² Ù„Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù… Ù…Ù† Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ù„ÙˆØ­ ÙˆØ­Ø¯ÙˆØ¯ Ø§Ù„Ø¨Ø§ØªØ±Ù†
    
    Args:
        panel_flat: Ø¨ÙŠØ§Ù†Ø§Øª Ø¥ÙØ±Ø§Ø¯ Ø§Ù„Ù„ÙˆØ­
        pattern_bounds: Ø­Ø¯ÙˆØ¯ Ø§Ù„Ø¨Ø§ØªØ±Ù† (Ù…Ù† PatternDXFReader.get_bounds())
        interpolation_density: ÙƒØ«Ø§ÙØ© Ø§Ù„Ø¥Ø¶Ø§ÙØ© (1-5 Ù…ÙˆØµÙ‰ Ø¨Ù‡)
    
    Returns:
        PatternMapper Ø¬Ø§Ù‡Ø² Ù„Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù…
    """
    mapper = PatternMapper(
        panel_flat=panel_flat,
        pattern_width=pattern_bounds["width"],
        pattern_height=pattern_bounds["height"],
        min_x=pattern_bounds["min_x"],
        min_y=pattern_bounds["min_y"],
        interpolation_density=interpolation_density
    )
    
    return mapper


def batch_map_pattern_to_panels(
    panels_flat: List[PanelFlatPattern],
    pattern_lines: List[LineSegment],
    pattern_polys: List[PolylinePath],
    pattern_bounds: dict,
    interpolation_density: int = 2,
    verbose: bool = True,
    qa_report: Optional[QAReportV1] = None,
    workspace_root: Optional[str] = None,
    write_qa_report: bool = False,
) -> dict[int, dict]:
    """
    ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø¹Ù„Ù‰ Ø¹Ø¯Ø© Ø£Ù„ÙˆØ§Ø­ Ø¯ÙØ¹Ø© ÙˆØ§Ø­Ø¯Ø©
    
    Args:
        panels_flat: Ù‚Ø§Ø¦Ù…Ø© Ø£Ù„ÙˆØ§Ø­ Ø§Ù„Ø¥ÙØ±Ø§Ø¯
        pattern_lines: Ø®Ø·ÙˆØ· Ø§Ù„Ø¨Ø§ØªØ±Ù†
        pattern_polys: polylines Ø§Ù„Ø¨Ø§ØªØ±Ù†
        pattern_bounds: Ø­Ø¯ÙˆØ¯ Ø§Ù„Ø¨Ø§ØªØ±Ù†
        interpolation_density: ÙƒØ«Ø§ÙØ© Ø§Ù„Ø¥Ø¶Ø§ÙØ©
        verbose: Ø·Ø¨Ø§Ø¹Ø© Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø§Ù„ØªÙ‚Ø¯Ù…
    
    Returns:
        Ù‚Ø§Ù…ÙˆØ³: {panel_id: {"lines": [...], "polylines": [...]}}
    """
    results = {}
    clip_totals: Dict[str, Any] = {
        "safe_zone": {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0},
        "closed_inputs": 0,
        "open_inputs": 0,
        "closed_outputs": 0,
        "open_outputs": 0,
        "fragmentation_events": 0,
        "geometry_collections": 0,
        "multi_geometries": 0,
        "ring_closure_repairs": 0,
        "num_inputs": 0,
        "num_clipped": 0,
        "geom_types_seen": {},
    }
    safe_zone_set = False
    
    total = len(panels_flat)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"ðŸ”„ Ø¨Ø¯Ø¡ ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø¹Ù„Ù‰ {total} Ù„ÙˆØ­...")
        print(f"{'='*60}\n")
    
    for i, panel_flat in enumerate(panels_flat, 1):
        mapper = create_mapper_for_panel(
            panel_flat=panel_flat,
            pattern_bounds=pattern_bounds,
            interpolation_density=interpolation_density
        )
        
        # ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ø¨Ø§ØªØ±Ù†
        mapped_lines = mapper.map_lines(pattern_lines)
        mapped_polys = mapper.map_polylines(pattern_polys)
        
        results[panel_flat.panel_id] = {
            "lines": mapped_lines,
            "polylines": mapped_polys,
            "stats": mapper.get_mapping_stats()
        }
        clip_metrics = mapper.get_clip_metrics()
        if not safe_zone_set:
            clip_totals["safe_zone"] = dict(clip_metrics.get("safe_zone") or clip_totals["safe_zone"])
            safe_zone_set = True
        for key in (
            "closed_inputs",
            "open_inputs",
            "closed_outputs",
            "open_outputs",
            "fragmentation_events",
            "geometry_collections",
            "multi_geometries",
            "ring_closure_repairs",
            "num_inputs",
            "num_clipped",
        ):
            clip_totals[key] = int(clip_totals.get(key) or 0) + int(clip_metrics.get(key) or 0)
        geom_types = clip_metrics.get("geom_types_seen")
        if isinstance(geom_types, dict):
            totals_geom = clip_totals.get("geom_types_seen")
            if not isinstance(totals_geom, dict):
                totals_geom = {}
                clip_totals["geom_types_seen"] = totals_geom
            for g_key, g_value in geom_types.items():
                totals_geom[str(g_key)] = int(totals_geom.get(str(g_key)) or 0) + int(g_value or 0)
        
        if verbose and (i <= 3 or i % 10 == 0 or i == total):
            print(f"âœ… Ù„ÙˆØ­ {panel_flat.panel_id:02d}/{total:02d} - "
                  f"{len(mapped_lines)} Ø®Ø·ØŒ {len(mapped_polys)} polyline")
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"âœ… Ø§ÙƒØªÙ…Ù„ ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„Ø¨Ø§ØªØ±Ù† Ø¹Ù„Ù‰ Ø¬Ù…ÙŠØ¹ Ø§Ù„Ø£Ù„ÙˆØ§Ø­")
        print(f"{'='*60}\n")

    if qa_report is not None:
        qa_report.ensure_schema_defaults()
        qa_report.clip.update(clip_totals)

        fragmentation_events = int(clip_totals.get("fragmentation_events") or 0)
        if fragmentation_events > 0:
            qa_report.add_unique(
                "warn",
                "CLIP_FRAGMENTATION",
                "Clipping produced fragmented outputs.",
                {"count": fragmentation_events},
            )

        geometry_collections = int(clip_totals.get("geometry_collections") or 0)
        if geometry_collections > 0:
            qa_report.add_unique(
                "info",
                "CLIP_GEOMETRY_COLLECTION",
                "GeometryCollection encountered during clipping.",
                {"count": geometry_collections},
            )

        closed_in = int(clip_totals.get("closed_inputs") or 0)
        closed_out = int(clip_totals.get("closed_outputs") or 0)
        if closed_in > 0 and closed_out == 0:
            qa_report.add_unique(
                "fail",
                "CLIP_CLOSED_VANISHED",
                "All closed shapes vanished after clipping.",
                {"in": closed_in, "out": closed_out},
            )

        open_in = int(clip_totals.get("open_inputs") or 0)
        open_out = int(clip_totals.get("open_outputs") or 0)
        if open_out < open_in:
            qa_report.add_unique(
                "warn",
                "CLIP_OPEN_REDUCED",
                "Some open paths were reduced or removed by safe-zone clipping.",
                {"in": open_in, "out": open_out},
            )

        geom_types_seen = clip_totals.get("geom_types_seen")
        if isinstance(geom_types_seen, dict):
            allowed = {"Polygon", "MultiPolygon", "LineString", "MultiLineString", "GeometryCollection"}
            unexpected = sorted([k for k in geom_types_seen.keys() if k not in allowed])
            if unexpected:
                qa_report.add_unique(
                    "warn",
                    "CLIP_UNEXPECTED_GEOMETRY_TYPES",
                    "Unexpected geometry types encountered during clipping.",
                    {"types": unexpected},
                )

        if write_qa_report:
            qa_report.write_latest(workspace_root or "")
    
    return results




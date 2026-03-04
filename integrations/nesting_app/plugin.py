from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
import os
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.utils.dxf_min import polyline, write_dxf

Rect = Tuple[float,float]  # (w,h)

def _shelf_pack(sheet_w: float, sheet_h: float, rects: List[Rect], gap: float) -> List[Dict[str, Any]]:
    x=gap; y=gap; row_h=0.0
    placed=[]
    for i,(w,h) in enumerate(rects):
        w2=w+gap; h2=h+gap
        if x + w2 > sheet_w:
            x=gap
            y += row_h + gap
            row_h=0.0
        if y + h2 > sheet_h:
            break
        placed.append({"id": i, "x": x, "y": y, "w": w, "h": h, "rot": 0})
        x += w2
        row_h = max(row_h, h)
    return placed

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    sheet_w=float(config.get("sheet_w", 3000.0))
    sheet_h=float(config.get("sheet_h", 1500.0))
    gap=float(config.get("gap", 5.0))

    def solve(rects: List[List[float]], out_dxf: str="outputs/nesting_result.dxf") -> Dict[str, Any]:
        rr=[(float(r[0]), float(r[1])) for r in rects]
        placements=_shelf_pack(sheet_w,sheet_h,rr,gap)
        ents=[]
        # sheet border
        ents.append(polyline([(0,0),(sheet_w,0),(sheet_w,sheet_h),(0,sheet_h)], layer="SHEET", closed=True))
        for p in placements:
            x,y,w,h=p["x"],p["y"],p["w"],p["h"]
            ents.append(polyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)], layer="PART", closed=True))
        write_dxf(out_dxf, ents)
        return {"sheet": [sheet_w,sheet_h], "gap": gap, "placed": placements, "out_dxf": os.path.abspath(out_dxf)}

    registry.register_tool(ToolRegistration(
        tool_id="nesting.solve_rectangles",
        plugin_id=manifest.id,
        tool_group="fs_write",
        op="nesting_solve_rectangles",
        handler=solve,
        description="Greedy shelf pack rectangles and export DXF to outputs/",
        default_target="outputs/nesting_result.dxf",
    ))

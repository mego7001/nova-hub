from __future__ import annotations
from typing import Any, Dict
import os, math
from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration
from core.utils.dxf_min import circle, write_dxf

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    grid_w=int(config.get("grid_w", 60))
    grid_h=int(config.get("grid_h", 40))
    max_r=float(config.get("max_r", 6.0))

    def halftone_gradient(out_dxf: str="outputs/halftone_gradient.dxf") -> Dict[str, Any]:
        ents=[]
        # simple radial gradient: bigger circles near center
        cx=(grid_w-1)/2.0
        cy=(grid_h-1)/2.0
        maxd=math.hypot(cx,cy)
        pitch = max_r*2.2
        for j in range(grid_h):
            for i in range(grid_w):
                d=math.hypot(i-cx, j-cy)/maxd
                r=max_r*(1.0-d)
                if r <= 0.15: 
                    continue
                x=i*pitch
                y=j*pitch
                ents.append(circle((x,y), r, layer="DOTS"))
        write_dxf(out_dxf, ents)
        return {"grid":[grid_w,grid_h], "max_r": max_r, "out_dxf": os.path.abspath(out_dxf), "circles": len(ents)}

    # This tool writes a DXF => declare fs_write so approvals guard the output path.
    registry.register_tool(ToolRegistration(
        tool_id="halftone.generate_pattern",
        plugin_id=manifest.id,
        tool_group="fs_write",
        op="halftone_generate_pattern",
        handler=halftone_gradient,
        description="Generate radial halftone (circles) and export DXF to outputs/",
        default_target="outputs/halftone_gradient.dxf",
    ))

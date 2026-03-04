from __future__ import annotations
from typing import Iterable, Tuple, List, Optional
import math

Point = Tuple[float, float]

def _dxf_header() -> str:
    return "\n".join([
        "0","SECTION","2","HEADER",
        "9","$ACADVER","1","AC1009",
        "0","ENDSEC",
        "0","SECTION","2","TABLES",
        "0","ENDSEC",
        "0","SECTION","2","ENTITIES",
    ]) + "\n"

def _dxf_footer() -> str:
    return "\n".join(["0","ENDSEC","0","EOF"]) + "\n"

def polyline(points: Iterable[Point], layer: str="0", closed: bool=True) -> str:
    pts = list(points)
    if closed and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    out = ["0","POLYLINE","8",layer,"66","1","70","1" if closed else "0"]
    for x,y in pts:
        out += ["0","VERTEX","8",layer,"10",f"{x:.6f}","20",f"{y:.6f}","30","0.0"]
    out += ["0","SEQEND"]
    return "\n".join(out) + "\n"

def circle(center: Point, radius: float, layer: str="0") -> str:
    x,y = center
    out = ["0","CIRCLE","8",layer,"10",f"{x:.6f}","20",f"{y:.6f}","30","0.0","40",f"{radius:.6f}"]
    return "\n".join(out) + "\n"

def write_dxf(path: str, entities: List[str]) -> None:
    import os
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_dxf_header())
        for e in entities:
            f.write(e)
        f.write(_dxf_footer())

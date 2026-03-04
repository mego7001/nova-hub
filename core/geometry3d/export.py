from __future__ import annotations

import os
from typing import Dict, List, Tuple

from core.geometry3d import primitives
from core.security.secrets import SecretsManager


Point3 = Tuple[float, float, float]


import struct

def export_stl(model: Dict, path: str, name: str = "geometry3d", binary: bool = True) -> str:
    entities = model.get("entities") or []
    triangles: List[Tuple[Point3, Point3, Point3]] = []
    for e in entities:
        triangles.extend(primitives.entity_triangles(e))
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    if binary:
        _write_binary_stl(path, triangles)
    else:
        stl = _build_ascii_stl(name, triangles)
        with open(path, "w", encoding="utf-8") as f:
            f.write(SecretsManager.redact_text(stl))
    return path


def _write_binary_stl(path: str, tris: List[Tuple[Point3, Point3, Point3]]) -> None:
    # 80-byte header
    header = b"Nova Hub Binary STL" + (b"\x00" * 61)
    with open(path, "wb") as f:
        f.write(header[:80])
        # Number of triangles
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            # Normal (0,0,0)
            f.write(struct.pack("<fff", 0.0, 0.0, 0.0))
            # Vertices
            f.write(struct.pack("<fff", *a))
            f.write(struct.pack("<fff", *b))
            f.write(struct.pack("<fff", *c))
            # Attribute byte count
            f.write(struct.pack("<H", 0))


def _build_ascii_stl(name: str, tris: List[Tuple[Point3, Point3, Point3]]) -> str:
    lines = [f"solid {name}"]
    for a, b, c in tris:
        lines.append("  facet normal 0 0 0")
        lines.append("    outer loop")
        lines.append(f"      vertex {a[0]:.6f} {a[1]:.6f} {a[2]:.6f}")
        lines.append(f"      vertex {b[0]:.6f} {b[1]:.6f} {b[2]:.6f}")
        lines.append(f"      vertex {c[0]:.6f} {c[1]:.6f} {c[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {name}")
    return "\n".join(lines)

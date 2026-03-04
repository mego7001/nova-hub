from __future__ import annotations
import ast
import os
from typing import Dict, List


def build_dependency_graph(root_path: str) -> Dict[str, List[str]]:
    graph: Dict[str, List[str]] = {}
    for base, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__", "node_modules", "dist", "build")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root_path)
            imports: List[str] = []
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    src = f.read()
                tree = ast.parse(src)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                graph[rel] = imports
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(n.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for n in node.names:
                        imports.append(f"{mod}.{n.name}" if mod else n.name)
            graph[rel] = sorted(set(imports))
    return graph

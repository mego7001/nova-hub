from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass(frozen=True)
class SchemaError:
    path: str
    message: str

def validate_json_schema(data: Any, schema: Dict[str, Any], path: str = "$") -> List[SchemaError]:
    errs: List[SchemaError] = []
    st = schema.get("type")

    def ok(v: Any, t: str) -> bool:
        if t == "object": return isinstance(v, dict)
        if t == "string": return isinstance(v, str)
        if t == "integer": return isinstance(v, int) and not isinstance(v, bool)
        if t == "number": return isinstance(v, (int, float)) and not isinstance(v, bool)
        if t == "boolean": return isinstance(v, bool)
        if t == "array": return isinstance(v, list)
        return True

    if st and not ok(data, st):
        return [SchemaError(path, f"Expected {st}, got {type(data).__name__}")]

    if st == "object":
        props = schema.get("properties") or {}
        req = schema.get("required") or []
        for k in req:
            if k not in data:
                errs.append(SchemaError(f"{path}.{k}", "Missing required key"))
        for k, ps in props.items():
            if k in data and isinstance(ps, dict):
                errs += validate_json_schema(data[k], ps, f"{path}.{k}")
    return errs

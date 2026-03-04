from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from core.llm.router import LLMRouter
from core.engineering.extract import _parse_engineering_json
from core.engineering.model import build_state

def run_vision_geometry_pipeline(
    image_base64: str,
    prompt: str = "Extract all engineering dimensions, materials, and loads from this drawing.",
    project_id: str = "",
    router: Optional[LLMRouter] = None
) -> Dict[str, Any]:
    if not router:
        return {"error": "Router not provided"}

    system_prompt = (
        "You are an expert engineering assistant. Analyze the provided image (technical drawing, sketch, or photo). "
        "Extract engineering signals in JSON format. Focus on dimensions (diameter, length, height), "
        "materials mentioned, tolerances, and any visible loads or supports. "
        "Return JSON only. Format: {\"material\":\"...\",\"geometry\":{\"diameter\":...},\"loads\":[],\"tolerances\":[]}"
    )

    # Call router with vision task
    routed = router.route(
        "vision",
        prompt=prompt,
        system=system_prompt,
        online_enabled=True,
        request_kind="vision_geometry",
        images=[image_base64]
    )

    text = routed.get("text") or ""
    signals = _parse_engineering_json(text)
    
    # Enrich signals if needed
    signals["confidence"] = 0.8 if signals else 0.4
    
    # Build engineering state
    state = build_state(signals, message=prompt)
    
    return {
        "signals": signals,
        "state": state.to_dict(),
        "reply": text,
        "mode": routed.get("mode")
    }

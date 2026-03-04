from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, List, Optional

from core.engineering.vision_geometry import run_vision_geometry_pipeline
from core.llm.router import LLMRouter
from core.plugin_engine.registry import PluginRegistry
from core.task_engine.runner import Runner
from core.tooling.invoker import InvokeContext, invoke_tool


class ReasoningAgent:
    def __init__(self, router: LLMRouter, registry: PluginRegistry, runner: Runner):
        self.router = router
        self.registry = registry
        self.runner = runner

    def solve(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tools_desc = self._format_tools()
        system = self._build_system_prompt(tools_desc)

        images: List[str] = []
        task_type = "deep_reasoning"
        vision_results = None

        low_goal = goal.lower()
        if any(w in low_goal for w in ["image", "drawing", "picture", "screenshot", "صورة", "رسم"]):
            task_type = "vision"
            images = self._find_relevant_images(context)

            if images and any(w in low_goal for w in ["extract", "dimensions", "material", "load", "استخرج", "ابعاد"]):
                try:
                    vision_results = run_vision_geometry_pipeline(
                        images[0],
                        prompt=goal,
                        project_id=context.get("project_id", "") if context else "",
                        router=self.router,
                    )
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass

        out = self.router.route(
            task_type,
            prompt=goal,
            system=system,
            online_enabled=True,
            request_kind="agent",
            images=images,
        )

        plan_text = out.get("text") or ""
        plan = self._parse_plan(plan_text)

        results = []
        invoke_ctx = InvokeContext(
            runner=self.runner,
            registry=self.registry,
            session_id=str((context or {}).get("session_id") or ""),
            project_id=str((context or {}).get("project_id") or ""),
            mode="",
        )
        for step in plan:
            tool_id = step.get("tool_id")
            args = step.get("args") or {}

            tool = self.registry.tools.get(tool_id)
            if not tool:
                results.append({"tool_id": tool_id, "error": "Tool not found"})
                continue

            try:
                res = invoke_tool(str(tool_id or ""), dict(args), invoke_ctx)
                results.append({"tool_id": tool_id, "result": res})
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
                results.append({"tool_id": tool_id, "error": str(exc)})

        return {
            "plan": plan,
            "results": results,
            "vision_results": vision_results,
            "reply": out.get("text"),
            "mode": out.get("mode"),
        }

    def _find_relevant_images(self, context: Optional[Dict[str, Any]]) -> List[str]:
        if not context:
            return []

        attached = context.get("attached_images") or []
        if attached:
            return attached

        project_path = context.get("project_path")
        if not project_path:
            return []

        index_path = os.path.join(project_path, "index.json")
        if not os.path.exists(index_path):
            return []

        try:
            with open(index_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                docs = data.get("docs") if isinstance(data, dict) else data
                if not isinstance(docs, list):
                    return []

                image_records = [d for d in docs if d.get("type") == "image"]
                image_records.sort(key=lambda x: x.get("created_at", ""), reverse=True)

                if image_records:
                    path = image_records[0].get("stored_path")
                    if path and os.path.exists(path):
                        with open(path, "rb") as img_fp:
                            return [base64.b64encode(img_fp.read()).decode("utf-8")]
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

        return []

    def _format_tools(self) -> str:
        lines = []
        for tid, tool in self.registry.tools.items():
            lines.append(f"- {tid}: {tool.description}")
        return "\n".join(lines)

    def _build_system_prompt(self, tools_desc: str) -> str:
        return f"""You are Nova Hub's reasoning engine. Your goal is to solve the user's request by calling available tools.
Available Tools:
{tools_desc}

Advanced Rendering Instructions:
- If the user asks for "high quality", "8k", "detailed", or "premium" images, set "enable_hr": true in `stable_diffusion.generate`.
- Use `stable_diffusion.upscale` if the user wants to enlarge an existing image or improve its resolution.

Response Format:
Return a JSON array of tool calls at the beginning of your message if you want to execute tools.
Example:
[
  {{"tool_id": "stable_diffusion.generate", "args": {{"prompt": "3d blueprint of a turbine", "enable_hr": true}}}},
  {{"tool_id": "stable_diffusion.upscale", "args": {{"image_path": "path/to/img.png", "upscaling_resize": 4.0}}}}
]
Followed by your explanation in Arabic.
"""

    def _parse_plan(self, text: str) -> List[Dict[str, Any]]:
        import re

        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if not match:
            return []
        try:
            return json.loads(match.group(1))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return []

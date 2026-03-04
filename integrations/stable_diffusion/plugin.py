from __future__ import annotations
import base64
import json
import os
import requests
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.plugin_engine.manifest import PluginManifest
from core.plugin_engine.registry import PluginRegistry, ToolRegistration

def init_plugin(config: Dict[str, Any], registry: PluginRegistry, manifest: PluginManifest) -> None:
    api_url = str(config.get("api_url") or "http://127.0.0.1:7860").rstrip("/")
    default_output_dir = str(config.get("output_dir") or "outputs")

    def generate_image(
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg_scale: float = 7.0,
        enable_hr: bool = False,
        hr_scale: float = 2.0,
        hr_upscaler: str = "Latent",
        denoising_strength: float = 0.7,
        model_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an image using the local Stable Diffusion backend (Automatic1111/Forge).
        """
        if not prompt:
            raise ValueError("Prompt is required")

        # 1. Check/Switch Model if requested
        if model_name:
            try:
                opt_res = requests.get(f"{api_url}/sdapi/v1/options", timeout=5)
                opt_res.raise_for_status()
                opts = opt_res.json()
                current_model = opts.get("sd_model_checkpoint", "")
                
                # Simple loose matching logic
                if model_name.lower() not in current_model.lower():
                    # Attempt to find exact match or partial match from available models
                    models_res = requests.get(f"{api_url}/sdapi/v1/sd-models", timeout=5)
                    models = models_res.json()
                    target_model_title = None
                    for m in models:
                        title = m.get("title", "")
                        if model_name.lower() in title.lower():
                            target_model_title = title
                            break
                    
                    if target_model_title:
                        requests.post(f"{api_url}/sdapi/v1/options", json={"sd_model_checkpoint": target_model_title}, timeout=10)
                        # Giving it a moment to load
                        time.sleep(2)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
                # Non-fatal, just log/warn in response
                print(f"Warning: Failed to switch model: {e}")

        # 2. Prepare Payload
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "sampler_name": "Euler a",
            "batch_size": 1,
            "enable_hr": enable_hr,
            "hr_scale": hr_scale,
            "hr_upscaler": hr_upscaler,
            "denoising_strength": denoising_strength,
        }

        # 3. Call API
        try:
            response = requests.post(f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=120)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Could not connect to Stable Diffusion backend at {api_url}. Is it running with --api?")
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
             raise RuntimeError(f"Generation failed: {e}")

        r = response.json()
        images = r.get("images", [])
        if not images:
             raise RuntimeError("Backend returned no images.")

        # 4. Save Image
        # Determine actual output path
        # In Nova, we ideally want to write to the workspace project outputs.
        # This function might be running with a CWD of project root if invoked via task runner,
        # but let's be safe and use the provided output_dir or default.
        
        save_dir = output_dir or default_output_dir
        if not os.path.isabs(save_dir):
            save_dir = os.path.abspath(save_dir)
            
        os.makedirs(save_dir, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"sd_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)

        image_data = base64.b64decode(images[0])
        with open(filepath, "wb") as f:
            f.write(image_data)

        return {
            "status": "success",
            "prompt": prompt,
            "path": filepath,
            "info": r.get("info", {}),
            "model_used": model_name or "current"
        }

    def upscale_image(
        image_path: str,
        upscaling_resize: float = 2.0,
        upscaler_1: str = "R-ESRGAN 4x+",
        output_dir: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upscale an existing image using the Stable Diffusion extras API.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "image": base64_image,
            "upscaling_resize": upscaling_resize,
            "upscaler_1": upscaler_1,
        }

        try:
            response = requests.post(f"{api_url}/sdapi/v1/extra-single-image", json=payload, timeout=60)
            response.raise_for_status()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            raise RuntimeError(f"Upscaling failed: {e}")

        r = response.json()
        image_b64 = r.get("image")
        if not image_b64:
            raise RuntimeError("Backend returned no upscaled image.")

        save_dir = output_dir or default_output_dir
        if not os.path.isabs(save_dir):
            save_dir = os.path.abspath(save_dir)
        os.makedirs(save_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"upscaled_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(image_b64))

        return {
            "status": "success",
            "original_path": image_path,
            "path": filepath,
            "resize_factor": upscaling_resize
        }

    registry.register_tool(
        ToolRegistration(
            tool_id="stable_diffusion.generate",
            plugin_id=manifest.id,
            tool_group="media_gen",
            op="generate_image",
            handler=generate_image,
            description="Generate image using local Stable Diffusion with Hires.fix support",
            default_target="outputs",
        )
    )

    registry.register_tool(
        ToolRegistration(
            tool_id="stable_diffusion.upscale",
            plugin_id=manifest.id,
            tool_group="media_gen",
            op="upscale_image",
            handler=upscale_image,
            description="Upscale existing image using Stable Diffusion extras",
            default_target="outputs",
        )
    )


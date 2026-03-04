from __future__ import annotations
import os
from typing import Dict, List


def detect_run_profiles(working_dir: str) -> List[Dict[str, str]]:
    candidates = [
        "run_chat.py",
        "run_ui.py",
        "main.py",
        "app.py",
        "__main__.py",
    ]
    profiles: List[Dict[str, str]] = []
    for name in candidates:
        path = os.path.join(working_dir, name)
        if os.path.isfile(path):
            profile_id = name.replace(".py", "")
            profiles.append(
                {
                    "id": profile_id,
                    "label": f"python {name}",
                    "entry": name,
                }
            )
    return profiles

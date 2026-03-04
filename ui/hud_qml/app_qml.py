from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from core.portable.paths import default_workspace_dir, detect_base_dir, ensure_workspace_dirs

from .controller import HUDController

_UI_AUTO = "auto"
_UI_V1 = "v1"
_UI_V2 = "v2"
_VALID_UI_VERSIONS = {_UI_AUTO, _UI_V1, _UI_V2}
_UI_PROFILE_FULL = "full"
_DEFAULT_EFFECTS_PROFILE = "high_effects"
_DEFAULT_THEME_VARIANT = "jarvis_cyan"
_DEFAULT_MOTION_INTENSITY = "cinematic"


def _load_dotenv(path: str) -> None:
    p = Path(path)
    if not p.exists():
        return
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        key = k.strip()
        val = v.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _ui_v2_enabled() -> bool:
    raw = str(os.environ.get("NH_UI_V2") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _ui_shell_v3_enabled() -> bool:
    # V3 shell is default. Set NH_UI_SHELL_V3=0 to rollback to direct MainV2 loading.
    raw = str(os.environ.get("NH_UI_SHELL_V3") or "").strip().lower()
    if not raw:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return raw in {"1", "true", "yes", "on", "v3", "shell"}


def _resolve_effects_profile() -> str:
    raw = str(os.environ.get("NH_UI_EFFECTS_PROFILE") or "").strip().lower()
    if raw in {"high_effects", "balanced", "degraded"}:
        return raw
    return _DEFAULT_EFFECTS_PROFILE


def _effects_profile_forced() -> bool:
    raw = str(os.environ.get("NH_UI_EFFECTS_PROFILE") or "").strip().lower()
    return raw in {"high_effects", "balanced", "degraded"}


def _resolve_theme_variant() -> str:
    raw = str(os.environ.get("NH_UI_THEME_VARIANT") or "").strip().lower()
    if raw in {"jarvis_cyan", "amber_industrial"}:
        return raw
    return _DEFAULT_THEME_VARIANT


def _resolve_motion_intensity() -> str:
    raw = str(os.environ.get("NH_UI_MOTION_INTENSITY") or "").strip().lower()
    if raw in {"cinematic", "normal", "reduced"}:
        return raw
    return _DEFAULT_MOTION_INTENSITY


def _normalize_ui_version(raw_value: Optional[str]) -> Optional[str]:
    raw = str(raw_value or "").strip().lower()
    if not raw:
        return None
    if raw in _VALID_UI_VERSIONS:
        return raw
    if raw in {"1", "true", "yes", "on", "v2", "2"}:
        return _UI_V2
    if raw in {"0", "false", "no", "off", "v1", "legacy"}:
        return _UI_V1
    return None


def _resolve_ui_version(cli_ui_version: Optional[str] = None) -> str:
    cli_choice = _normalize_ui_version(cli_ui_version)
    if cli_choice is not None:
        return cli_choice
    env_choice = _normalize_ui_version(os.environ.get("NH_UI_VERSION"))
    if env_choice is not None:
        return env_choice
    if _ui_v2_enabled():
        return _UI_V2
    return _UI_AUTO


def _resolve_qml_candidates(ui_version: str) -> List[Path]:
    legacy = Path(__file__).resolve().parent / "qml" / "Main.qml"
    v2_shell = Path(__file__).resolve().parents[1] / "hud_qml_v2" / "shell" / "MainShellFull.qml"
    v2 = Path(__file__).resolve().parents[1] / "hud_qml_v2" / "MainV2.qml"
    v2_candidates = [v2_shell, v2] if _ui_shell_v3_enabled() else [v2]
    resolved = _normalize_ui_version(ui_version) or _UI_AUTO
    if resolved == _UI_V1:
        return [legacy]
    if resolved == _UI_V2:
        return v2_candidates
    return [*v2_candidates, legacy]


def _resolve_qml_main_path(ui_version: Optional[str] = None) -> Path:
    candidates = _resolve_qml_candidates(_resolve_ui_version(ui_version))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def build_engine(
    project_root: Optional[str] = None,
    workspace_root: Optional[str] = None,
    backend_enabled: bool = True,
    ui_version: Optional[str] = None,
) -> Tuple[QApplication, QQmlApplicationEngine, HUDController]:
    base_dir = os.path.abspath(project_root or detect_base_dir())
    ensure_workspace_dirs(base_dir)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    _load_dotenv(os.path.join(base_dir, ".env"))
    os.environ["NH_BASE_DIR"] = base_dir
    os.environ["NH_WORKSPACE"] = os.path.abspath(workspace_root or default_workspace_dir(base_dir))
    _load_dotenv(os.path.join(os.environ["NH_WORKSPACE"], "secrets", ".env"))
    os.chdir(base_dir)

    app = QApplication.instance() or QApplication(sys.argv)
    controller = HUDController(
        project_root=base_dir,
        workspace_root=os.environ["NH_WORKSPACE"],
        backend_enabled=backend_enabled,
    )
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("hudController", controller)
    engine.rootContext().setContextProperty("uiProfile", _UI_PROFILE_FULL)
    engine.rootContext().setContextProperty("visualEffectsProfile", _resolve_effects_profile())
    engine.rootContext().setContextProperty("visualEffectsProfileForced", _effects_profile_forced())
    engine.rootContext().setContextProperty("uiThemeVariant", _resolve_theme_variant())
    engine.rootContext().setContextProperty("uiMotionIntensity", _resolve_motion_intensity())

    requested_ui = _resolve_ui_version(ui_version)
    candidates = _resolve_qml_candidates(requested_ui)
    loaded_path: Optional[Path] = None
    attempted_paths: List[Path] = []
    for index, qml_path in enumerate(candidates):
        attempted_paths.append(qml_path)
        if not qml_path.exists():
            continue
        engine.load(QUrl.fromLocalFile(str(qml_path)))
        if engine.rootObjects():
            loaded_path = qml_path
            if requested_ui == _UI_AUTO and index > 0:
                print(
                    f"HUD auto fallback engaged: loaded {qml_path.name} after V2 load failure.",
                    file=sys.stderr,
                )
            break
        engine.clearComponentCache()
    if loaded_path is None:
        attempted = ", ".join(str(p) for p in attempted_paths)
        raise RuntimeError(f"Failed to load HUD QML (ui={requested_ui}). attempted={attempted}")
    os.environ["NH_UI_ACTIVE"] = _UI_V2 if "hud_qml_v2" in loaded_path.parts else _UI_V1
    return app, engine, controller


def main(*, ui_version: Optional[str] = None) -> int:
    app, _engine, _controller = build_engine(ui_version=ui_version)
    auto_close_ms = os.environ.get("NH_HUD_AUTOCLOSE_MS", "").strip()
    if auto_close_ms:
        try:
            ms = max(0, int(auto_close_ms))
            QTimer.singleShot(ms, app.quit)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
    return app.exec()

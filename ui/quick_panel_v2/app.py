from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from core.portable.paths import default_workspace_dir, detect_base_dir, ensure_workspace_dirs

from .controller import QuickPanelV2Controller

_UI_PROFILE_COMPACT = "compact"
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


def _resolve_qml_path() -> Path:
    if _ui_shell_v3_enabled():
        return Path(__file__).resolve().parents[1] / "hud_qml_v2" / "shell" / "MainShellCompact.qml"
    return Path(__file__).resolve().parent / "MainV2.qml"


def build_engine(
    project_root: Optional[str] = None,
    workspace_root: Optional[str] = None,
    backend_enabled: bool = True,
) -> Tuple[QApplication, QQmlApplicationEngine, QuickPanelV2Controller]:
    base_dir = os.path.abspath(project_root or detect_base_dir())
    ensure_workspace_dirs(base_dir)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    _load_dotenv(os.path.join(base_dir, ".env"))
    os.environ["NH_BASE_DIR"] = base_dir
    os.environ["NH_WORKSPACE"] = os.path.abspath(workspace_root or default_workspace_dir(base_dir))
    _load_dotenv(os.path.join(os.environ["NH_WORKSPACE"], "secrets", ".env"))
    os.chdir(base_dir)

    app = QApplication.instance() or QApplication(sys.argv)
    controller = QuickPanelV2Controller(
        project_root=base_dir,
        workspace_root=os.environ["NH_WORKSPACE"],
        backend_enabled=backend_enabled,
    )
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("quickPanelController", controller)
    engine.rootContext().setContextProperty("hudController", controller)
    engine.rootContext().setContextProperty("uiProfile", _UI_PROFILE_COMPACT)
    engine.rootContext().setContextProperty("visualEffectsProfile", _resolve_effects_profile())
    engine.rootContext().setContextProperty("visualEffectsProfileForced", _effects_profile_forced())
    engine.rootContext().setContextProperty("uiThemeVariant", _resolve_theme_variant())
    engine.rootContext().setContextProperty("uiMotionIntensity", _resolve_motion_intensity())

    qml_path = _resolve_qml_path()
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        raise RuntimeError(f"Failed to load Quick Panel V2 QML at {qml_path}")
    return app, engine, controller


def main() -> int:
    app, _engine, _controller = build_engine()
    auto_close_ms = str(os.environ.get("NH_QUICK_PANEL_V2_AUTOCLOSE_MS") or "").strip()
    if auto_close_ms:
        try:
            ms = max(0, int(auto_close_ms))
            QTimer.singleShot(ms, app.quit)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
    return int(app.exec())

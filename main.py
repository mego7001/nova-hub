import os
import sys
import inspect
from typing import Any, Callable, Dict, Optional, cast, get_args, get_origin
from pathlib import Path

def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

_load_dotenv()

from core.plugin_engine.registry import PluginRegistry
from core.plugin_engine.loader import PluginLoader
from core.permission_guard.tool_policy import ToolPolicy
from core.permission_guard.approval_flow import ApprovalFlow
from core.task_engine.runner import Runner

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CHAT_SEND_OP = "chat.send"

def approval_callback(req, res):
    print("\n=== APPROVAL REQUIRED ===")
    print("ToolGroup:", req.tool_group)
    print("Op:", req.op)
    print("Target:", req.target)
    print("Reason:", res.reason)
    print("Risk:", res.risk_score)
    ans = input("Approve? (y/n): ").strip().lower()
    return ans == "y"

def _prompt_bool(label: str, default: bool | None) -> bool | None:
    hint = "y/n"
    if default is not None:
        hint = f"y/n (default {str(default).lower()})"
    while True:
        s = input(f"{label} [{hint}]: ").strip().lower()
        if not s and default is not None:
            return default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        if not s and default is None:
            return None
        print("Please enter y or n.")

def _is_list_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is list or annotation is list:
        return True
    if origin is None:
        return False
    return any(get_origin(arg) is list or arg is list for arg in get_args(annotation))


def _is_bool_annotation(annotation: Any) -> bool:
    if annotation is bool or annotation == "bool":
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(arg is bool for arg in get_args(annotation))


def _parse_list_value(raw: str, default: Any) -> list[str]:
    if not raw.strip():
        if default is inspect._empty:
            return []
        if isinstance(default, list):
            return [str(item).strip() for item in default if str(item).strip()]
        return []
    return [chunk.strip() for chunk in raw.split(",") if chunk.strip()]


def _parse_scalar_value(raw: str, annotation: Any) -> Any:
    if annotation is int:
        return int(raw)
    if annotation is float:
        return float(raw)
    if annotation is bool:
        return raw.strip().lower() in ("y", "yes", "true", "1")
    return raw


def _parse_value(raw: str, annotation: Any, default: Any) -> Any:
    if annotation is inspect._empty:
        return raw
    if _is_list_annotation(annotation):
        return _parse_list_value(raw, default)
    return _parse_scalar_value(raw, annotation)


def _default_bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _prompt_generic_value(name: str, annotation: Any, default: Any, required: bool) -> tuple[bool, Any]:
    prompt = f"{name}"
    if not required:
        prompt += f" (default {default})"
    prompt += ": "
    while True:
        raw = input(prompt).strip()
        if not raw:
            if required:
                print("This value is required.")
                continue
            return False, None
        try:
            return True, _parse_value(raw, annotation, default)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            print("Invalid value. Try again.")


def _prompt_bool_value(name: str, default: Any, required: bool) -> tuple[bool, bool | None]:
    default_bool = None if required else _default_bool_value(default)
    value = _prompt_bool(name, default_bool)
    while value is None and required:
        print("This value is required.")
        value = _prompt_bool(name, None)
    if value is None and not required:
        return False, None
    return True, cast(Optional[bool], value)


def _prompt_for_params(handler: Callable[..., Any]) -> Dict[str, Any]:
    signature = inspect.signature(handler)
    kwargs: Dict[str, Any] = {}
    for name, param in signature.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        if name == "self":
            continue

        required = param.default is inspect._empty or (param.annotation is str and param.default == "")
        annotation = param.annotation
        default = param.default

        if _is_bool_annotation(annotation):
            include, value = _prompt_bool_value(name, default, required)
        else:
            include, value = _prompt_generic_value(name, annotation, default, required)

        if include:
            kwargs[name] = value
    return kwargs


def _handler_accepts_param(handler, name: str) -> bool:
    sig = inspect.signature(handler)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return True
    return name in sig.parameters


def _filter_handler_kwargs(handler, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    sig = inspect.signature(handler)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(kwargs)
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


def _execute_tool_with_filtered_kwargs(runner, tool, kwargs: Dict[str, Any], policy_target: str | None = None):
    target = policy_target if policy_target is not None else (kwargs.get("target") or tool.default_target)
    filtered = _filter_handler_kwargs(tool.handler, kwargs)
    accepts_target = _handler_accepts_param(tool.handler, "target")

    if accepts_target and target is not None and "target" not in filtered:
        filtered["target"] = target

    if accepts_target or target is None:
        return runner.execute_registered_tool(tool, **filtered)

    # Keep approval target semantics without passing unsupported kwargs to handler.
    original = tool.default_target
    tool.default_target = target
    try:
        return runner.execute_registered_tool(tool, **filtered)
    finally:
        tool.default_target = original

def _print_preview(tool, target):
    print("\n=== EXECUTION PREVIEW ===")
    print("Tool:", tool.tool_id)
    print("Group:", tool.tool_group)
    print("Op:", tool.op)
    print("Target:", target)

def _handle_list_tools_mode() -> int:
    registry = PluginRegistry()
    PluginLoader(PROJECT_ROOT).load_enabled(os.path.join(PROJECT_ROOT, "configs", "plugins_enabled.yaml"), registry)
    try:
        from core.ux.tools_index import write_tools_index_report

        report_path = write_tools_index_report(registry, os.path.join(PROJECT_ROOT, "reports", "tools_index.json"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        report_path = ""

    tools = sorted(registry.list_tools(), key=lambda t: t.tool_id)
    for i, tool in enumerate(tools, 1):
        print(f"{i:02d}) {tool.tool_id:22s} [{tool.tool_group}] - {tool.description}")
    if report_path:
        print(f"\nTools index report: {report_path}")
    return 0


def _build_cli_runtime() -> tuple[str, Runner, PluginRegistry]:
    profile = os.environ.get("NH_PROFILE", "engineering")
    policy = ToolPolicy(os.path.join(PROJECT_ROOT, "configs", "tool_policy.yaml"), active_profile=profile)
    approvals = ApprovalFlow(policy, os.path.join(PROJECT_ROOT, "configs", "approvals.yaml"))
    runner = Runner(approval_flow=approvals, approval_callback=approval_callback)

    registry = PluginRegistry()
    PluginLoader(PROJECT_ROOT).load_enabled(os.path.join(PROJECT_ROOT, "configs", "plugins_enabled.yaml"), registry)
    return profile, runner, registry


def _print_loaded_tools(profile: str, registry: PluginRegistry, tools: list[Any]) -> None:
    print(f"\nNH profile: {profile}")
    print("Loaded plugins:", [p.plugin_id for p in registry.list_plugins()])
    print("\nTools:")
    for i, tool in enumerate(tools, 1):
        print(f"{i:02d}) {tool.tool_id:22s} [{tool.tool_group}] - {tool.description}")


def _parse_rectangles_input(raw: str) -> list[list[float]]:
    if not raw.strip():
        return [[300, 200], [500, 300], [200, 200], [800, 400], [350, 250]]
    rects: list[list[float]] = []
    for chunk in raw.split(";"):
        item = chunk.strip()
        if not item:
            continue
        w, h = item.split(",")
        rects.append([float(w), float(h)])
    return rects


def _execute_tool_choice(runner: Runner, tool: Any) -> Any:
    if tool.tool_id == "nesting.solve_rectangles":
        print("Enter rectangles as: w,h;w,h;w,h  (mm)")
        rects = _parse_rectangles_input(input("rects: ").strip())
        target = tool.default_target
        _print_preview(tool, target)
        return _execute_tool_with_filtered_kwargs(runner, tool, {"rects": rects}, policy_target=target)

    if tool.tool_id == "conical.generate_helix":
        turns_raw = input("turns (blank=default): ").strip()
        turns = float(turns_raw) if turns_raw else None
        target = tool.default_target
        _print_preview(tool, target)
        return _execute_tool_with_filtered_kwargs(runner, tool, {"turns": turns}, policy_target=target)

    if tool.tool_id == "halftone.generate_pattern":
        target = tool.default_target
        _print_preview(tool, target)
        return _execute_tool_with_filtered_kwargs(runner, tool, {}, policy_target=target)

    if tool.tool_id == "fs.write_text":
        path = input(f"Path (default {tool.default_target}): ").strip() or tool.default_target
        text = input("Text: ").strip()
        _print_preview(tool, path)
        return _execute_tool_with_filtered_kwargs(
            runner,
            tool,
            {"path": path, "text": text, "target": path},
            policy_target=path,
        )

    kwargs = _prompt_for_params(tool.handler)
    target = kwargs.get("target") or tool.default_target
    _print_preview(tool, target)
    return _execute_tool_with_filtered_kwargs(runner, tool, kwargs, policy_target=target)


def _run_cli_loop(runner: Runner, tools: list[Any]) -> int:
    exit_code = 0
    while True:
        try:
            choice = input("\nSelect tool number (or q): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting CLI.")
            return 130 if exit_code == 0 else exit_code
        if choice == "q":
            return exit_code
        if not choice.isdigit() or not (1 <= int(choice) <= len(tools)):
            print("Invalid choice.")
            continue

        tool = tools[int(choice) - 1]
        try:
            out = _execute_tool_choice(runner, tool)
            print("\n--- RESULT ---")
            print(out)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            print("\n--- ERROR ---")
            print(str(exc))
            exit_code = 1


def _cli_main(args: list[str] | None = None) -> int:
    argv = list(args or [])
    if "--list-tools" in argv:
        return _handle_list_tools_mode()

    try:
        profile, runner, registry = _build_cli_runtime()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
        print(f"CLI initialization failed: {exc}")
        return 1

    tools = sorted(registry.list_tools(), key=lambda t: t.tool_id)
    if not tools:
        print("No enabled tools were loaded.")
        return 1

    _print_loaded_tools(profile, registry, tools)
    return _run_cli_loop(runner, tools)


def _launch_hud(args=None) -> int:
    from ui.hud_qml.app_qml import main as hud_main
    ui_version = getattr(args, "ui", None) if args is not None else None
    return int(hud_main(ui_version=ui_version))

def _launch_chat() -> int:
    from core.portable.paths import detect_base_dir, ensure_workspace_dirs, default_workspace_dir
    from PySide6.QtWidgets import QApplication
    from ui.chat.app import ChatWindow
    
    base_dir = detect_base_dir()
    ensure_workspace_dirs(base_dir)
    os.environ["NH_BASE_DIR"] = base_dir
    os.environ["NH_WORKSPACE"] = default_workspace_dir(base_dir)
    os.chdir(base_dir)
    
    app = QApplication(sys.argv)
    window = ChatWindow(project_root=base_dir)
    window.show()
    return app.exec()

def _launch_dashboard() -> int:
    from PySide6.QtWidgets import QApplication
    from ui.dashboard.app import DashboardWindow
    
    app = QApplication(sys.argv)
    window = DashboardWindow(project_root=PROJECT_ROOT)
    window.show()
    return app.exec()


def _legacy_whatsapp_enabled() -> bool:
    raw = str(os.environ.get("NH_UI_LEGACY_WHATSAPP") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _launch_whatsapp() -> int:
    if not _legacy_whatsapp_enabled():
        return _launch_quick_panel_v2()

    print(
        "Warning: legacy quick panel path enabled via NH_UI_LEGACY_WHATSAPP=1. "
        "Use quick_panel_v2 for Unified Shell V3.",
        file=sys.stderr,
    )
    from core.portable.paths import detect_base_dir, ensure_workspace_dirs, default_workspace_dir
    from PySide6.QtWidgets import QApplication
    from ui.quick_panel.app import QuickPanelWindow

    base_dir = detect_base_dir()
    ensure_workspace_dirs(base_dir)
    os.environ["NH_BASE_DIR"] = base_dir
    os.environ["NH_WORKSPACE"] = default_workspace_dir(base_dir)
    os.chdir(base_dir)

    app = QApplication(sys.argv)
    window = QuickPanelWindow(project_root=base_dir)
    window.show()
    return app.exec()


def _launch_quick_panel_v2() -> int:
    from ui.quick_panel_v2.app import main as quick_panel_v2_main

    return int(quick_panel_v2_main())

def _launch_core(args) -> int:
    import os
    import signal
    import threading
    import time
    from core.ipc.protocol import DEFAULT_HOST, resolve_ipc_events_port, resolve_ipc_port, resolve_ipc_token
    from core.ipc.server import LocalEventsServer, LocalIpcServer
    from core.ipc.service import NovaCoreService

    host = str(args.host or DEFAULT_HOST).strip() or DEFAULT_HOST
    if host != DEFAULT_HOST:
        print("Error: Core service is local-only and must bind to 127.0.0.1")
        return 1
    
    port = resolve_ipc_port(args.port)
    events_port = resolve_ipc_events_port(args.events_port, rpc_port=port)
    token = resolve_ipc_token()

    service = NovaCoreService()
    service.set_runtime_ports(ipc_port=port, events_port=events_port)
    stop_event = threading.Event()
    shutdown_complete = threading.Event()
    shutdown_lock = threading.Lock()
    shutdown_thread: Optional[threading.Thread] = None

    def _initiate_shutdown(payload: Dict[str, Any]) -> None:
        nonlocal shutdown_thread
        cfg = dict(payload or {})
        with shutdown_lock:
            if shutdown_thread is not None and shutdown_thread.is_alive():
                return

            def _shutdown_worker() -> None:
                timeout_sec = max(1, int(cfg.get("timeout_sec") or 15))
                force = bool(cfg.get("force"))
                try:
                    service.prepare_shutdown(
                        scope=str(cfg.get("scope") or "core_and_events"),
                        timeout_sec=timeout_sec,
                        force=force,
                        keep_ollama_running=bool(cfg.get("keep_ollama_running", True)),
                    )
                except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                    pass
                stop_event.set()
                if force and not shutdown_complete.wait(timeout=timeout_sec):
                    os._exit(0)

            shutdown_thread = threading.Thread(target=_shutdown_worker, name="nova-core-shutdown", daemon=True)
            shutdown_thread.start()

    service.set_shutdown_handler(_initiate_shutdown)

    def dispatch(op, payload, ctx):
        if str(op or "") == "service.stop":
            _initiate_shutdown(
                {
                    "scope": "core_and_events",
                    "timeout_sec": 5,
                    "force": False,
                    "keep_ollama_running": True,
                }
            )
            return {"ok": True}
        return service.dispatch(op, payload, ctx)

    rpc_server = LocalIpcServer(host=host, port=port, dispatcher=dispatch, token=token)
    events_server = LocalEventsServer(host=host, port=events_port, token=token)

    def _publish_event(session_id: str, project_id: str, topic: str, data: Dict[str, Any]) -> None:
        events_server.publish_event(
            session_id=session_id,
            project_id=project_id,
            topic=topic,
            data=data,
        )

    service.set_event_publisher(_publish_event)

    def _handle_signal(_signum, _frame) -> None:
        _initiate_shutdown(
            {
                "scope": "core_and_events",
                "timeout_sec": 5,
                "force": False,
                "keep_ollama_running": True,
            }
        )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    rpc_server.start_in_thread()
    events_server.start_in_thread()
    print(f"nova_core_service listening rpc={host}:{rpc_server.port} events={host}:{events_server.port}", flush=True)
    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    finally:
        try:
            service.prepare_shutdown(
                scope="core_and_events",
                timeout_sec=5,
                force=False,
                keep_ollama_running=True,
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass
        try:
            rpc_server.shutdown()
        finally:
            events_server.shutdown()
            shutdown_complete.set()
    return 0

def _launch_call(args) -> int:
    import json
    from core.ipc.client import IpcClient
    from core.ipc.protocol import DEFAULT_HOST, resolve_ipc_port, resolve_ipc_token
    from core.ipc.spawn import ensure_core_running_with_events

    host = str(args.host or DEFAULT_HOST)
    port = resolve_ipc_port(args.port)
    token = resolve_ipc_token()

    ensure_core_running_with_events(host=host, port=port, token=token)
    client = IpcClient(host=host, port=port, token=token, timeout_s=180.0)
    op = str(args.op or CHAT_SEND_OP).strip() or CHAT_SEND_OP
    if op == CHAT_SEND_OP:
        payload = {
            "text": str(args.text or ""),
            "mode": str(args.mode or "general"),
            "session_id": str(args.session or "ipc_cli"),
            "project_path": str(args.project_path or ""),
            "write_reports": True,
            "ui": "ipc_cli",
            "debug_routing": bool(args.debug_routing),
        }
    else:
        payload = {}
        raw = str(args.payload_json or "").strip()
        if raw:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                print("Error: --payload-json must be a JSON object")
                return 1
            payload = parsed
    result = client.call_ok(op, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def _launch_ui(ui_name: str) -> int:
    normalized = (ui_name or "").strip().lower()
    if normalized in ("hud", "hud_qml", "qml"):
        return _launch_hud()
    if normalized in ("chat",):
        return _launch_chat()
    if normalized in ("dashboard", "ui"):
        return _launch_dashboard()
    if normalized in ("quick", "quick_panel", "whatsapp"):
        return _launch_whatsapp()
    if normalized in ("quick_panel_v2", "quick_v2", "whatsapp_v2"):
        return _launch_quick_panel_v2()
    raise ValueError(f"Unknown UI '{ui_name}'. Expected: hud | chat | dashboard | quick | quick_panel_v2")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Nova Hub - Unified Entry Point")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # HUD (default)
    hud_parser = subparsers.add_parser("hud", help="Launch QML-based HUD")
    hud_parser.add_argument(
        "--ui",
        choices=("auto", "v2", "v1"),
        default=None,
        help="HUD variant selector (CLI > NH_UI_VERSION > default auto)",
    )

    # Core
    core_parser = subparsers.add_parser("core", help="Launch backend IPC core service")
    from core.ipc.protocol import DEFAULT_HOST, resolve_ipc_port
    core_parser.add_argument("--host", default=DEFAULT_HOST, help="bind host (must stay local)")
    core_parser.add_argument("--port", type=int, default=resolve_ipc_port(None), help="bind port")
    core_parser.add_argument("--events-port", type=int, default=None, help="events bind port")

    # UIs
    subparsers.add_parser("chat", help="Launch standalone chat UI")
    subparsers.add_parser("dashboard", help="Launch legacy dashboard UI")
    subparsers.add_parser("whatsapp", help="Launch WhatsApp bridge/panel")
    subparsers.add_parser("quick_panel_v2", help="Launch Quick Panel V2 (QML + backend)")

    # CLI
    cli_parser = subparsers.add_parser("cli", help="Open interactive tool CLI")
    cli_parser.add_argument("--list-tools", action="store_true", help="List enabled tools and exit")

    # Call (one-off IPC)
    call_parser = subparsers.add_parser("call", help="Executes a one-off IPC operation")
    call_parser.add_argument("--op", default=CHAT_SEND_OP, help="IPC operation")
    call_parser.add_argument("--payload-json", default="", help="Raw JSON payload")
    call_parser.add_argument("text", nargs="?", default="hello", help="message text")
    call_parser.add_argument("--mode", default="general", help="task mode id")
    call_parser.add_argument("--session", default="ipc_cli", help="session id")
    call_parser.add_argument("--project-path", default="", help="project working path")
    call_parser.add_argument("--debug-routing", action="store_true", help="include routing diagnostics in chat.send output")
    call_parser.add_argument("--host", default=DEFAULT_HOST, help="IPC host")
    call_parser.add_argument("--port", type=int, default=resolve_ipc_port(None), help="IPC port")

    args = parser.parse_args()

    if not args.command or args.command == "hud":
        return _launch_hud(args)
    
    if args.command == "core":
        return _launch_core(args)
    
    if args.command == "chat":
        return _launch_chat()
    
    if args.command == "dashboard":
        return _launch_dashboard()
    
    if args.command == "whatsapp":
        return _launch_whatsapp()

    if args.command == "quick_panel_v2":
        return _launch_quick_panel_v2()
    
    if args.command == "cli":
        if args.list_tools:
            return _cli_main(["--list-tools"])
        return _cli_main([])

    if args.command == "call":
        return _launch_call(args)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())

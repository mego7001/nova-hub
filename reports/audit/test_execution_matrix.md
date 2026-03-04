# Test Execution Matrix

Generated at: 2026-02-22T02:41:39Z

| Command | Status | Return Code | Duration (s) |
|---|---:|---:|---:|
| `pytest --collect-only -q` | pass | 0 | 0.968 |
| `pytest -q tests/test_no_naive_utcnow.py` | pass | 0 | 0.376 |
| `pytest -q tests/test_entrypoint_wrappers.py tests/test_main_dispatch.py tests/test_docs_launch_smoke.py tests/test_launchers_compat_smoke.py` | pass | 0 | 2.457 |
| `pytest -q tests/test_ipc_server_health.py tests/test_ipc_chat_send_smoke.py tests/test_ipc_autospawn.py tests/test_ipc_reconnect_respawn.py` | pass | 0 | 4.617 |
| `pytest -q tests/test_gating.py tests/test_project_manager_security.py tests/test_online_policy_multilingual.py tests/test_doctor_report.py` | pass | 0 | 0.927 |
| `pytest -q tests/test_hud_qml_smoke.py tests/test_hud_qml_ux_wiring.py` | pass | 0 | 0.724 |

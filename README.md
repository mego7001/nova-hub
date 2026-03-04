<<<<<<< HEAD
# nova-hub
AI egant
=======
# Nova Hub

## Closing Nova Safely

- In HUD, use `⏻ Exit` and choose `Shutdown Nova` (default) to stop core cleanly.
- Optional: keep `Keep Ollama running` checked if you do not want Ollama stopped.
- HUD calls `system.shutdown`, waits up to 15 seconds for core exit, and if needed force-kills only the returned core PID, then verifies IPC/events ports are closed.
- Choose `Exit HUD only` to close the window without stopping the core service.
>>>>>>> 6eee61b (Initial commit)

from __future__ import annotations

import json
import os

from ui.hud_qml.managers.chat_manager import ChatManager


def test_chat_manager_load_messages_reads_bounded_tail(tmp_path) -> None:
    manager = ChatManager(str(tmp_path))
    primary = manager.general_message_log()
    os.makedirs(os.path.dirname(primary), exist_ok=True)

    with open(primary, "w", encoding="utf-8") as f:
        for i in range(1000):
            f.write(json.dumps({"role": "assistant", "text": f"m{i}", "timestamp": str(i)}) + "\n")

    items = manager.load_messages(primary)
    assert len(items) == 400
    assert items[0]["text"] == "m600"
    assert items[-1]["text"] == "m999"

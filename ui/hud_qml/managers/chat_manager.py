import os
import re
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal

from ui.hud_qml.models import DictListModel
from core.utils.jsonl_tail import tail_jsonl_dicts

GENERAL_CHAT_ID = "__general__"
CHAT_SESSION_PREFIX = "chat_"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def _safe_read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
        return {}
    return payload if isinstance(payload, dict) else {}

class ChatManager(QObject):
    chatsChanged = Signal()
    
    def __init__(self, workspace_root: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._workspace_root = workspace_root
        self._chat_sessions_rows: List[Dict[str, Any]] = []
        
        self.chats_model = DictListModel(
            ["chat_id", "title", "status", "last_opened", "linked_project_id"],
            parent=self,
        )
        self.messages_model = DictListModel(["role", "text", "timestamp"], parent=self)
        
        self.refresh_chats()

    def _chat_index_path(self) -> str:
        return os.path.join(self._workspace_root, "chat", "sessions.json")

    def _chat_logs_root(self) -> str:
        return os.path.join(self._workspace_root, "chat", "sessions")

    def _normalize_chat_id(self, chat_id: str) -> str:
        cid = str(chat_id or "").strip()
        if cid == GENERAL_CHAT_ID:
            return GENERAL_CHAT_ID
        if re.match(r"^chat_[a-z0-9]{8,64}$", cid):
            return cid
        return ""

    def _default_chat_row(self) -> Dict[str, Any]:
        return {
            "chat_id": GENERAL_CHAT_ID,
            "title": "General Chat",
            "status": "chat",
            "last_opened": "",
            "linked_project_id": "",
        }

    def _load_chat_rows(self) -> List[Dict[str, Any]]:
        path = self._chat_index_path()
        payload = _safe_read_json(path)
        raw_rows: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            sessions = payload.get("sessions")
            if isinstance(sessions, list):
                raw_rows = [x for x in sessions if isinstance(x, dict)]
        elif isinstance(payload, list):
            raw_rows = [x for x in payload if isinstance(x, dict)]

        rows_by_id: Dict[str, Dict[str, Any]] = {}
        for row in raw_rows:
            cid = self._normalize_chat_id(str(row.get("chat_id") or ""))
            if not cid:
                continue
            rows_by_id[cid] = {
                "chat_id": cid,
                "title": str(row.get("title") or ("General Chat" if cid == GENERAL_CHAT_ID else cid)),
                "status": str(row.get("status") or "chat"),
                "last_opened": str(row.get("last_opened") or ""),
                "linked_project_id": str(row.get("linked_project_id") or ""),
            }

        if GENERAL_CHAT_ID not in rows_by_id:
            rows_by_id[GENERAL_CHAT_ID] = self._default_chat_row()

        rows = list(rows_by_id.values())
        general = [r for r in rows if r.get("chat_id") == GENERAL_CHAT_ID]
        others = [r for r in rows if r.get("chat_id") != GENERAL_CHAT_ID]
        others.sort(key=lambda x: str(x.get("last_opened") or ""), reverse=True)
        return [*general, *others]

    def _save_chat_rows(self, rows: List[Dict[str, Any]]) -> None:
        safe_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = self._normalize_chat_id(str(row.get("chat_id") or ""))
            if not cid:
                continue
            safe_rows.append(
                {
                    "chat_id": cid,
                    "title": str(row.get("title") or ("General Chat" if cid == GENERAL_CHAT_ID else cid)),
                    "status": str(row.get("status") or "chat"),
                    "last_opened": str(row.get("last_opened") or ""),
                    "linked_project_id": str(row.get("linked_project_id") or ""),
                }
            )
        path = self._chat_index_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"sessions": safe_rows}, f, indent=2, ensure_ascii=False)

    def refresh_chats(self) -> List[Dict[str, Any]]:
        rows = self._load_chat_rows()
        self._chat_sessions_rows = [dict(x) for x in rows]
        self.chats_model.set_items(rows)
        self.chatsChanged.emit()
        return rows

    def create_chat_session(self, title: str = "") -> str:
        base = str(title or "").strip()
        if not base:
            base = f"Chat {datetime.now(timezone.utc).strftime('%H:%M')}"
        cid = f"{CHAT_SESSION_PREFIX}{uuid.uuid4().hex[:10]}"
        rows = self._load_chat_rows()
        rows.append(
            {
                "chat_id": cid,
                "title": base,
                "status": "chat",
                "last_opened": _now(),
                "linked_project_id": "",
            }
        )
        self._save_chat_rows(rows)
        self.refresh_chats()
        return cid

    def touch_chat(self, chat_id: str) -> None:
        cid = self._normalize_chat_id(chat_id)
        if not cid:
            return
        rows = self._load_chat_rows()
        changed = False
        for row in rows:
            if str(row.get("chat_id") or "") != cid:
                continue
            row["last_opened"] = _now()
            changed = True
            break
        if not changed and cid == GENERAL_CHAT_ID:
            default_row = self._default_chat_row()
            default_row["last_opened"] = _now()
            rows.insert(0, default_row)
        if changed or cid == GENERAL_CHAT_ID:
            self._save_chat_rows(rows)
            self.refresh_chats()

    def mark_chat_converted(self, chat_id: str, project_id: str) -> None:
        cid = self._normalize_chat_id(chat_id)
        if not cid:
            return
        rows = self._load_chat_rows()
        changed = False
        for row in rows:
            if str(row.get("chat_id") or "") != cid:
                continue
            row["status"] = "converted"
            row["linked_project_id"] = str(project_id or "")
            row["last_opened"] = _now()
            changed = True
            break
        if changed:
            self._save_chat_rows(rows)
            self.refresh_chats()

    def get_chat_row(self, chat_id: str) -> Dict[str, Any]:
        cid = self._normalize_chat_id(chat_id)
        if not cid:
            return {}
        for row in self._chat_sessions_rows:
            if str(row.get("chat_id") or "") == cid:
                return dict(row)
        return {}

    def chat_message_log(self, chat_id: str) -> str:
        cid = self._normalize_chat_id(chat_id)
        if not cid:
            return self.general_message_log()
        if cid == GENERAL_CHAT_ID:
            return self.general_message_log()
        root = self._chat_logs_root()
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, f"{cid}.jsonl")

    def general_message_log(self) -> str:
        return os.path.join(self._workspace_root, "chat", "general_messages.jsonl")

    def is_chat_session(self, chat_id: str) -> bool:
        cid = str(chat_id or "")
        return cid == GENERAL_CHAT_ID or cid.startswith(CHAT_SESSION_PREFIX)

    def append_message(self, chat_id: str, role: str, text: str) -> None:
        cid = self._normalize_chat_id(chat_id)
        if not cid:
            return
        item = {"role": role, "text": str(text or ""), "timestamp": _now()}
        # We only update the model if this chat is "active" in the view, 
        # but for now the controller manages the active view. 
        # So we just provide the data persistence here.
        # The controller will update the model via a signal or direct call if it's the active chat.
        
        try:
            target_path = self.chat_message_log(cid)
            self._write_jsonl(target_path, item)
            if self.is_chat_session(cid):
                self.touch_chat(cid)
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            pass

    def load_messages(self, primary_path: str, fallback_markdown_path: str = "") -> List[Dict[str, Any]]:
        # Try loading JSONL first
        items = tail_jsonl_dicts(primary_path, limit=400)
        if not items and fallback_markdown_path:
             items = self._parse_chat_markdown(fallback_markdown_path)
        
        normalized = []
        for item in items[-400:]:
             normalized.append({
                 "role": str(item.get("role") or "assistant"),
                 "text": str(item.get("text") or ""),
                 "timestamp": str(item.get("timestamp") or ""),
             })
        return normalized

    def _parse_chat_markdown(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return []
            
        items: List[Dict[str, Any]] = []
        cur_role = ""
        cur_ts = ""
        body: List[str] = []

        def flush() -> None:
            nonlocal cur_role, cur_ts, body
            if cur_role and body:
                role = "user" if cur_role.lower().startswith("user") else "assistant"
                items.append(
                    {
                        "role": role,
                        "text": "\n".join(body).strip(),
                        "timestamp": cur_ts or "",
                    }
                )
            cur_role = ""
            cur_ts = ""
            body = []

        for line in lines:
            if line.startswith("## ") and " - " in line:
                flush()
                raw = line[3:]
                try:
                    ts, role = raw.split(" - ", 1)
                    cur_ts = ts.strip()
                    cur_role = role.strip()
                except ValueError:
                    continue
                continue
            if cur_role:
                body.append(line)
        flush()
        return items

    def _write_jsonl(self, path: str, payload: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _read_jsonl(self, path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            return []
        out: List[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        item = json.loads(s)
                        if isinstance(item, dict):
                            out.append(item)
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                        continue
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
            return []
        return out

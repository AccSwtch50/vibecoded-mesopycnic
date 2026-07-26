import sqlite3
import json
import uuid
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("MESOPYCNIC_DB_PATH", "mesopycnic.db")

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    system_prompt TEXT DEFAULT '',
                    base_url TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    reasoning_content TEXT DEFAULT '',
                    tool_calls TEXT DEFAULT NULL,
                    tool_call_id TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            conn.commit()

    # --- Conversation CRUD ---

    def create_conversation(
        self,
        title: str = "New Chat",
        system_prompt: str = "",
        base_url: str = "",
        model: str = ""
    ) -> Dict[str, Any]:
        conv_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, system_prompt, base_url, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conv_id, title, system_prompt, base_url, model)
            )
            conn.commit()
        return self.get_conversation(conv_id)

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)

    def list_conversations(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC"
            )
            return [dict(row) for row in cur.fetchall()]

    def update_conversation(self, conv_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        allowed = {"title", "system_prompt", "base_url", "model"}
        updates = []
        params = []
        for k, v in kwargs.items():
            if k in allowed:
                updates.append(f"{k} = ?")
                params.append(v)
        if not updates:
            return self.get_conversation(conv_id)

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(conv_id)
        sql = f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?"

        with self.get_connection() as conn:
            conn.execute(sql, tuple(params))
            conn.commit()
        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        with self.get_connection() as conn:
            cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
            return cur.rowcount > 0

    # --- Message CRUD ---

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        reasoning_content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        tool_calls_json = json.dumps(tool_calls) if tool_calls else None

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, reasoning_content, tool_calls, tool_call_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, role, content, reasoning_content, tool_calls_json, tool_call_id)
            )
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conversation_id,)
            )
            conn.commit()
        return self.get_message(msg_id)

    def get_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            if res["tool_calls"]:
                try:
                    res["tool_calls"] = json.loads(res["tool_calls"])
                except Exception:
                    pass
            return res

    def get_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,)
            )
            messages = []
            for row in cur.fetchall():
                m = dict(row)
                if m["tool_calls"]:
                    try:
                        m["tool_calls"] = json.loads(m["tool_calls"])
                    except Exception:
                        pass
                messages.append(m)
            return messages

    # --- Settings CRUD ---

    def get_setting(self, key: str, default: str = "") -> str:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cur.fetchall()}

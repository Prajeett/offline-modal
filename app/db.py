import os
import sqlite3
from datetime import datetime, timezone

from app.models import ChatRequest


class ChatRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    session_id TEXT,
                    client_ip TEXT,
                    use_search TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_chars INTEGER NOT NULL,
                    response_chars INTEGER NOT NULL,
                    max_tokens INTEGER
                )
                """
            )
            conn.commit()

    def save_chat_event(
        self,
        request: ChatRequest,
        client_ip: str,
        model_name: str,
        response_text: str,
        resolved_max_tokens: int,
    ) -> None:
        prompt_chars = sum(len(msg.content) for msg in request.messages)
        created_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO chat_events
                (created_at, session_id, client_ip, use_search, model_name, prompt_chars, response_chars, max_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    request.session_id,
                    client_ip,
                    request.use_search,
                    model_name,
                    prompt_chars,
                    len(response_text),
                    resolved_max_tokens,
                ),
            )
            conn.commit()

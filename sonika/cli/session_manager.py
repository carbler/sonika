"""Session persistence — stores chat history in ~/.sonika/sessions/."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sonika.cli.models_catalog import get_model

SESSIONS_DIR = Path.home() / ".sonika" / "sessions"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


class Session:
    def __init__(
        self,
        provider: str,
        model: str,
        session_id: Optional[str] = None,
        title: str = "New session",
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        messages: Optional[List[dict]] = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
    ):
        self.id = session_id or _short_id()
        self.provider = provider
        self.model = model
        self.title = title
        self.created_at = created_at or _now_iso()
        self.updated_at = updated_at or _now_iso()
        self.messages: List[dict] = messages or []
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost = cost

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": self.messages,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost": self.cost,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(
            provider=data["provider"],
            model=data["model"],
            session_id=data.get("id"),
            title=data.get("title", "Untitled"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            messages=data.get("messages", []),
            tokens_in=data.get("tokens_in", 0),
            tokens_out=data.get("tokens_out", 0),
            cost=data.get("cost", 0.0),
        )

    def save(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.updated_at = _now_iso()
        path = SESSIONS_DIR / f"{self.id}.json"
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        approx = max(1, len(content) // 4)
        if role == "user":
            self.tokens_in += approx
        else:
            self.tokens_out += approx
        model_info = get_model(self.provider, self.model)
        if model_info:
            self.cost = model_info.cost_for(self.tokens_in, self.tokens_out)
        if len(self.messages) == 1 and role == "user":
            self.title = content[:60].replace("\n", " ").strip()


class SessionManager:
    def list_sessions(self) -> List[dict]:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        sessions = []
        for path in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    def load(self, session_id: str) -> Session:
        path = SESSIONS_DIR / f"{session_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return Session.from_dict(data)

    def new_session(self, provider: str, model: str) -> Session:
        session = Session(provider=provider, model=model)
        session.save()
        return session

    def delete(self, session_id: str):
        path = SESSIONS_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()

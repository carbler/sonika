"""Base renderer interface for Sonika CLI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseRenderer(ABC):
    """Abstract base for all Sonika CLI renderers."""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @abstractmethod
    async def init(
        self,
        provider: str,
        model: str,
        session_id: str,
        app_title: str = "SONIKA",
        recent_sessions: list[dict] | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_input(
        self,
        mode: str,
        provider: str,
        model: str,
        on_tab: Any | None = None,
    ) -> str: ...

    @abstractmethod
    async def shutdown(self) -> None: ...

    # ── Chat display ──────────────────────────────────────────────────────────

    @abstractmethod
    def show_user_message(self, text: str) -> None: ...

    @abstractmethod
    def show_ai_start(self, provider: str = "", model: str = "") -> None: ...

    @abstractmethod
    def show_thinking(self, text: str, line_count: int) -> None: ...

    @abstractmethod
    def show_thinking_end(self, full_text: str) -> None: ...

    @abstractmethod
    def show_token(self, token: str, is_pre_tool: bool) -> None: ...

    @abstractmethod
    def show_final_response(self, markdown_text: str) -> None: ...

    @abstractmethod
    def show_ai_end(
        self,
        elapsed: float,
        provider: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
    ) -> None: ...

    # ── Tools ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def show_tool_start(self, name: str, args_str: str) -> None: ...

    @abstractmethod
    def show_tool_result(
        self,
        name: str,
        status: str,
        output: str,
        args_str: str,
        elapsed: float,
    ) -> None: ...

    # ── Approval ──────────────────────────────────────────────────────────────

    @abstractmethod
    async def show_approval(self, tool_name: str, args_str: str) -> bool: ...

    # ── System ────────────────────────────────────────────────────────────────

    def show_partial_response(self, text: str) -> None:
        """Show intermediate progress text from the agent. Default: no-op."""
        pass

    @abstractmethod
    def show_retry(self, attempt: int, wait_s: float) -> None: ...

    @abstractmethod
    def show_system(self, text: str) -> None: ...

    @abstractmethod
    def show_error(self, text: str) -> None: ...

    # ── Pickers ───────────────────────────────────────────────────────────────

    @abstractmethod
    def show_setup_prompt(self) -> dict[str, str]: ...

    @abstractmethod
    async def show_model_picker(
        self,
        models: list[Any],
        configured_providers: list[str],
    ) -> tuple[str, str] | None: ...

    @abstractmethod
    async def show_session_picker(
        self, sessions: list[dict],
    ) -> tuple[str, str] | None: ...

    @abstractmethod
    def show_key_input(self, provider: str) -> str | None: ...

    @abstractmethod
    def show_help(self) -> None: ...


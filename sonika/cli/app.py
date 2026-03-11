"""Sonika CLI — renderer-agnostic main loop (Claude Code style)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from sonika.cli.config import Config, PROVIDERS
from sonika.cli.models_catalog import MODELS, all_providers, models_for_provider
from sonika.cli.session_manager import Session, SessionManager
from sonika.cli.renderers import BaseRenderer
from sonika.config_schema import SonikaAppConfig

MODES = ["ask", "auto", "plan"]


class SonikaCLI:
    """Main CLI loop, decoupled from any specific renderer."""

    def __init__(
        self,
        config: SonikaAppConfig | None = None,
        renderer: BaseRenderer | None = None,
    ) -> None:
        self._app_config = config or SonikaAppConfig()
        if renderer is None:
            from sonika.cli.renderers.claude_style import ClaudeStyleRenderer
            renderer = ClaudeStyleRenderer()
        self._renderer = renderer
        self._config = Config(self._app_config.config_dir)
        self._mgr = SessionManager()
        self._session: Optional[Session] = None
        self._bot = None
        self._mode: str = "ask"
        self._streaming: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        # Setup if needed
        if not self._config.is_configured:
            keys = self._renderer.show_setup_prompt()
            for prov, key in keys.items():
                if prov in PROVIDERS:
                    self._config.set_key(prov, key)
            self._auto_model()

        # Start session (skip if already started, e.g. in tests)
        if not self._session:
            await self._start_session()
        if not self._session:
            self._renderer.show_error("Sin modelo configurado. Ejecuta de nuevo y configura tu API key.")
            return

        recent = self._mgr.list_sessions()[:3]
        await self._renderer.init(
            self._session.provider,
            self._session.model,
            self._session.id,
            self._app_config.app_title,
            recent_sessions=recent,
        )

        # Main loop
        try:
            while True:
                try:
                    text = await self._renderer.get_input(
                        self._mode,
                        self._session.provider if self._session else "?",
                        self._session.model if self._session else "?",
                        on_tab=self._cycle_mode,
                    )
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break

                if not text:
                    continue

                if text.startswith("/"):
                    should_exit = await self._handle_command(text)
                    if should_exit:
                        break
                else:
                    await self._send(text)
        finally:
            await self._renderer.shutdown()

    # ── Session management ────────────────────────────────────────────────────

    async def _start_session(self) -> None:
        prov = self._config.active_provider
        model = self._config.active_model
        if not prov or not model:
            self._auto_model()
            prov = self._config.active_provider
            model = self._config.active_model
        if not prov or not model:
            return
        self._session = self._mgr.new_session(prov, model)
        self._rebuild_bot()

    def _rebuild_bot(self) -> None:
        if not self._session:
            return
        key = self._config.get_key(self._session.provider)
        if not key:
            return
        env_map = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }
        ev = env_map.get(self._session.provider)
        if ev:
            os.environ[ev] = key
        try:
            from sonika.factory import create_orchestrator
            self._bot = create_orchestrator(
                provider=self._session.provider,
                model_name=self._session.model,
                risk_level=self._app_config.risk_level,
                session_id=self._session.id,
                config=self._app_config,
            )
        except Exception as exc:
            self._renderer.show_error(f"Bot: {exc}")
            self._bot = None

    def _auto_model(self) -> None:
        if self._config.active_provider and self._config.active_model:
            return
        for m in MODELS:
            if self._config.has_key(m.provider):
                self._config.set_active(m.provider, m.model_id)
                return

    # ── Commands ──────────────────────────────────────────────────────────────

    async def _handle_command(self, text: str) -> bool:
        """Handle slash commands. Returns True if the app should exit."""
        parts = text.split()
        cmd = parts[0].lower()

        # Extra commands from config
        if cmd.lstrip("/") in self._app_config.extra_commands:
            handler = self._app_config.extra_commands[cmd.lstrip("/")]
            try:
                handler(self, parts[1:])
            except Exception as exc:
                self._renderer.show_error(str(exc))
            return False

        if cmd == "/model":
            result = await self._renderer.show_model_picker(
                MODELS, self._config.configured_providers()
            )
            if result:
                prov, model = result
                if not self._config.has_key(prov):
                    key = self._renderer.show_key_input(prov)
                    if not key:
                        self._renderer.show_system("Sin key — modelo no cambiado.")
                        return False
                    self._config.set_key(prov, key)
                self._config.set_active(prov, model)
                await self._new_session()

        elif cmd == "/session":
            sessions = self._mgr.list_sessions()
            result = await self._renderer.show_session_picker(sessions)
            if result:
                action, sid = result
                if action == "open":
                    await self._load_session(sid)
                elif action == "deleted":
                    self._mgr.delete(sid)
                    self._renderer.show_system(f"Sesion {sid} borrada.")

        elif cmd in ("/new", "/n"):
            await self._new_session()

        elif cmd == "/key" and len(parts) >= 3:
            prov, key = parts[1].lower(), parts[2]
            if prov in PROVIDERS:
                self._config.set_key(prov, key)
                self._renderer.show_system(f"Key guardada para {prov}.")
                if self._session and self._session.provider == prov:
                    self._rebuild_bot()
            else:
                self._renderer.show_error(f"Proveedor desconocido: {prov}")

        elif cmd in ("/exit", "/quit", "/q"):
            return True

        elif cmd == "/mode":
            new = self._cycle_mode()
            self._renderer.show_system(f"Modo: {new.upper()}")

        elif cmd == "/help":
            self._renderer.show_help()

        else:
            self._renderer.show_error(f"Comando desconocido: {cmd}. Escribe /help.")

        return False

    def _cycle_mode(self) -> str:
        idx = MODES.index(self._mode)
        self._mode = MODES[(idx + 1) % len(MODES)]
        return self._mode

    # ── Session actions ───────────────────────────────────────────────────────

    async def _new_session(self) -> None:
        prov = self._config.active_provider
        model = self._config.active_model
        if not prov or not model:
            self._renderer.show_error("Sin modelo configurado. Usa /model.")
            return
        self._session = self._mgr.new_session(prov, model)
        self._rebuild_bot()
        self._renderer.show_system(f"Nueva sesion — {prov}/{model}")

    async def _load_session(self, session_id: str) -> None:
        try:
            session = self._mgr.load(session_id)
        except FileNotFoundError:
            self._renderer.show_error(f"Sesion no encontrada: {session_id}")
            return
        self._session = session
        if self._config.has_key(session.provider):
            self._config.set_active(session.provider, session.model)
            self._rebuild_bot()
        # Show previous messages
        for msg in session.messages:
            if msg["role"] == "user":
                self._renderer.show_user_message(msg.get("content", ""))
            else:
                self._renderer.show_final_response(msg.get("content", ""))
        self._renderer.show_system(
            f"Sesion cargada: {session.provider}/{session.model} #{session.id}"
        )

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def _send(self, text: str) -> None:
        if self._streaming:
            return
        if not self._session:
            self._renderer.show_error("Sin sesion activa. Configura tu API key con /key.")
            return
        if not self._bot:
            self._renderer.show_error("Bot no listo. Usa /key <proveedor> <apikey>.")
            return

        self._renderer.show_user_message(text)
        self._session.add_message("user", text)
        self._streaming = True
        prov = self._session.provider if self._session else "?"
        model = self._session.model if self._session else "?"
        self._renderer.show_ai_start(provider=prov, model=model)
        t_start = time.monotonic()

        full_thinking = ""
        thinking_finalized = False
        full_pre_response = ""
        full_final_response = ""
        tools_ever_started = False
        tool_timers: dict[str, float] = {}
        tool_call_count: dict[str, int] = {}
        tool_args_map: dict[str, str] = {}

        try:
            from langchain_core.messages import AIMessageChunk

            goal = text
            thread_id = self._session.id

            while True:
                interrupted = False
                interrupt_tool = ""
                interrupt_args = ""

                async for stream_mode, payload in self._bot.astream_events(
                    goal, mode=self._mode, thread_id=thread_id
                ):
                    # ── Token chunks ──────────────────────────────────────
                    if stream_mode == "messages":
                        chunk, _ = payload
                        if not isinstance(chunk, AIMessageChunk):
                            continue
                        content = chunk.content

                        def _handle_token(text_chunk: str) -> None:
                            nonlocal full_pre_response, full_final_response, thinking_finalized
                            # Finalize thinking before first response token
                            if full_thinking and not thinking_finalized:
                                self._renderer.show_thinking_end(full_thinking)
                                thinking_finalized = True
                            if not tools_ever_started:
                                full_pre_response += text_chunk
                                self._renderer.show_token(text_chunk, is_pre_tool=True)
                            else:
                                full_final_response += text_chunk
                                self._renderer.show_token(text_chunk, is_pre_tool=False)

                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, str) and part:
                                    _handle_token(part)
                                elif isinstance(part, dict):
                                    if part.get("type") == "thinking":
                                        t = part.get("thinking", "")
                                        if t:
                                            full_thinking += t
                                            lines = len(full_thinking.splitlines())
                                            self._renderer.show_thinking(full_thinking, lines)
                                    else:
                                        c = part.get("text", "") or part.get("content", "")
                                        if c:
                                            _handle_token(str(c))
                        elif isinstance(content, str) and content:
                            _handle_token(content)

                    # ── Node updates ──────────────────────────────────────
                    elif stream_mode == "updates":
                        for node_name, update in payload.items():
                            if node_name == "agent":
                                # Retry events
                                for ev in update.get("status_events", []):
                                    if ev.get("type") == "retrying":
                                        self._renderer.show_retry(
                                            ev["attempt"], ev["wait_s"]
                                        )

                                # Tool calls
                                msgs = update.get("messages", [])
                                last = msgs[-1] if msgs else None
                                if last and getattr(last, "tool_calls", None):
                                    tools_ever_started = True
                                    for tc in last.tool_calls:
                                        name = tc.get("name", "unknown")
                                        args = tc.get("args", {})
                                        pairs = ", ".join(
                                            f"{k}={repr(v)[:40]}"
                                            for k, v in args.items()
                                        )[:120]
                                        n = tool_call_count.get(name, 0)
                                        tool_call_count[name] = n + 1
                                        key = f"{name}#{n}"
                                        tool_timers[key] = time.monotonic()
                                        tool_args_map[key] = pairs
                                        self._renderer.show_tool_start(name, pairs)

                                # Partial responses (intermediate progress)
                                for partial in update.get("partial_responses", []):
                                    self._renderer.show_partial_response(partial)

                                # Final report
                                if update.get("final_report"):
                                    already = bool(full_final_response) or (
                                        not tools_ever_started
                                        and bool(full_pre_response)
                                    )
                                    if not already:
                                        full_final_response = update["final_report"]

                            elif node_name == "tools":
                                done_count: dict[str, int] = {}
                                for t in update.get("tools_executed", []):
                                    name = t.get("tool_name", "?")
                                    status = t.get("status", "?")
                                    output = str(t.get("output", ""))
                                    n = done_count.get(name, 0)
                                    done_count[name] = n + 1
                                    key = f"{name}#{n}"
                                    elapsed = time.monotonic() - tool_timers.pop(
                                        key, t_start
                                    )
                                    args_brief = tool_args_map.pop(key, "")
                                    self._renderer.show_tool_result(
                                        name, status, output, args_brief, elapsed
                                    )

                            elif node_name == "__interrupt__":
                                iv = update[0].value if update else {}
                                interrupt_tool = iv.get(
                                    "tool", iv.get("tool_name", "?")
                                )
                                interrupt_args = str(iv.get("params", {}))[:200]
                                interrupted = True

                if not interrupted:
                    break

                # Approval flow
                approved = await self._renderer.show_approval(
                    interrupt_tool, interrupt_args
                )
                self._bot.set_resume_command({"approved": approved})
                goal = None

        except Exception as exc:
            self._renderer.show_error(str(exc))
        finally:
            self._streaming = False

        # Thinking summary (if never finalized during streaming)
        if full_thinking and not thinking_finalized:
            self._renderer.show_thinking_end(full_thinking)

        # Determine final text
        final_text = full_final_response or full_pre_response
        if final_text:
            self._renderer.show_final_response(final_text)

        elapsed = time.monotonic() - t_start
        prov = self._session.provider if self._session else "?"
        model = self._session.model if self._session else "?"

        # Persist and get token/cost stats
        tokens_in = tokens_out = 0
        cost = 0.0
        if final_text and self._session:
            self._session.add_message("assistant", final_text)
            self._session.save()
            tokens_in = self._session.tokens_in
            tokens_out = self._session.tokens_out
            cost = self._session.cost

        self._renderer.show_ai_end(
            elapsed, prov, model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
        )

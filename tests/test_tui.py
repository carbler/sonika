"""
Tests for Sonika CLI (new renderer-agnostic architecture).

Uses a MockRenderer to verify command dispatch, mode cycling,
streaming dispatch, approval flow, and config injection.
"""

import asyncio
import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dotenv import load_dotenv

from sonika.cli.renderers import BaseRenderer
from sonika.cli.app import SonikaCLI, MODES
from sonika.config_schema import SonikaAppConfig

load_dotenv()


# ── Mock renderer ─────────────────────────────────────────────────────────────

class MockRenderer(BaseRenderer):
    """Records all calls for assertions."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self._input_queue: list[str] = []
        self._approval_response: bool = False

    def queue_input(self, *texts: str):
        self._input_queue.extend(texts)

    def set_approval(self, approved: bool):
        self._approval_response = approved

    def _record(self, method: str, *args):
        self.calls.append((method, args))

    def call_names(self) -> list[str]:
        return [c[0] for c in self.calls]

    def calls_for(self, method: str) -> list[tuple]:
        return [args for name, args in self.calls if name == method]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(self, provider, model, session_id, app_title="SONIKA", recent_sessions=None):
        self._record("init", provider, model, session_id, app_title)

    async def get_input(self, mode, provider, model, on_tab=None):
        self._record("get_input", mode, provider, model)
        if self._input_queue:
            return self._input_queue.pop(0)
        raise EOFError  # exit the loop

    async def shutdown(self):
        self._record("shutdown")

    # ── Chat display ──────────────────────────────────────────────────────────

    def show_user_message(self, text):
        self._record("show_user_message", text)

    def show_ai_start(self, provider="", model=""):
        self._record("show_ai_start", provider, model)

    def show_thinking(self, text, line_count):
        self._record("show_thinking", text, line_count)

    def show_thinking_end(self, full_text):
        self._record("show_thinking_end", full_text)

    def show_token(self, token, is_pre_tool):
        self._record("show_token", token, is_pre_tool)

    def show_final_response(self, markdown_text):
        self._record("show_final_response", markdown_text)

    def show_ai_end(self, elapsed, provider, model, tokens_in=0, tokens_out=0, cost=0.0):
        self._record("show_ai_end", elapsed, provider, model, tokens_in, tokens_out, cost)

    # ── Tools ─────────────────────────────────────────────────────────────────

    def show_tool_start(self, name, args_str):
        self._record("show_tool_start", name, args_str)

    def show_tool_result(self, name, status, output, args_str, elapsed):
        self._record("show_tool_result", name, status, output, args_str, elapsed)

    # ── Approval ──────────────────────────────────────────────────────────────

    async def show_approval(self, tool_name, args_str):
        self._record("show_approval", tool_name, args_str)
        return self._approval_response

    # ── System ────────────────────────────────────────────────────────────────

    def show_retry(self, attempt, wait_s):
        self._record("show_retry", attempt, wait_s)

    def show_system(self, text):
        self._record("show_system", text)

    def show_error(self, text):
        self._record("show_error", text)

    # ── Pickers ───────────────────────────────────────────────────────────────

    def show_setup_prompt(self):
        self._record("show_setup_prompt")
        return {}

    async def show_model_picker(self, models, configured_providers):
        self._record("show_model_picker")
        return None

    async def show_session_picker(self, sessions):
        self._record("show_session_picker")
        return None

    def show_key_input(self, provider):
        self._record("show_key_input", provider)
        return None

    def show_help(self):
        self._record("show_help")



# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolated_config(tmp_path):
    """Every test gets its own config dir so we never touch ~/.sonika/."""
    os.environ["_SONIKA_TEST_CONFIG_DIR"] = str(tmp_path)
    yield
    os.environ.pop("_SONIKA_TEST_CONFIG_DIR", None)


def _make_cli(renderer: MockRenderer, config: SonikaAppConfig | None = None) -> SonikaCLI:
    """Create a SonikaCLI with google key pre-configured in a temp dir."""
    cfg = config or SonikaAppConfig()
    # Use the isolated tmp dir from the fixture
    cfg.config_dir = Path(os.environ["_SONIKA_TEST_CONFIG_DIR"])
    cli = SonikaCLI(config=cfg, renderer=renderer)
    # Pre-configure so setup is skipped
    api_key = os.environ.get("GOOGLE_API_KEY", "test-key")
    cli._config.set_key("google", api_key)
    cli._config.set_active("google", "gemini-2.5-flash")
    return cli


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_help_command():
    """Verify /help calls renderer.show_help()."""
    r = MockRenderer()
    r.queue_input("/help")
    cli = _make_cli(r)

    await cli.run()

    assert "show_help" in r.call_names()


@pytest.mark.asyncio
async def test_exit_command():
    """Verify /exit ends the loop."""
    r = MockRenderer()
    r.queue_input("/exit")
    cli = _make_cli(r)

    await cli.run()

    assert "shutdown" in r.call_names()


@pytest.mark.asyncio
async def test_mode_cycling():
    """Verify /mode cycles through ask -> auto -> plan -> ask."""
    r = MockRenderer()
    r.queue_input("/mode", "/mode", "/mode")
    cli = _make_cli(r)

    await cli.run()

    system_calls = r.calls_for("show_system")
    modes_shown = [args[0] for args in system_calls if "Modo:" in args[0]]
    assert len(modes_shown) == 3
    assert "AUTO" in modes_shown[0]
    assert "PLAN" in modes_shown[1]
    assert "ASK" in modes_shown[2]


@pytest.mark.asyncio
async def test_unknown_command():
    """Verify unknown command shows error."""
    r = MockRenderer()
    r.queue_input("/foobar")
    cli = _make_cli(r)

    await cli.run()

    error_calls = r.calls_for("show_error")
    assert any("foobar" in args[0] for args in error_calls)


@pytest.mark.asyncio
async def test_config_injection():
    """Verify SonikaAppConfig is respected."""
    r = MockRenderer()
    r.queue_input("/exit")
    config = SonikaAppConfig(
        app_name="TestApp",
        app_title="TEST",
    )
    cli = _make_cli(r, config=config)

    await cli.run()

    # init should receive the custom title
    init_calls = r.calls_for("init")
    assert init_calls
    assert init_calls[0][3] == "TEST"  # app_title param


@pytest.mark.asyncio
async def test_key_command():
    """Verify /key saves a provider key."""
    r = MockRenderer()
    r.queue_input("/key google fake-key-123")
    cli = _make_cli(r)

    await cli.run()

    assert cli._config.get_key("google") == "fake-key-123"
    system_calls = r.calls_for("show_system")
    assert any("google" in args[0] for args in system_calls)


@pytest.mark.asyncio
async def test_new_session():
    """Verify /new creates a new session."""
    r = MockRenderer()
    r.queue_input("/new")
    cli = _make_cli(r)

    await cli.run()

    system_calls = r.calls_for("show_system")
    assert any("Nueva sesion" in args[0] for args in system_calls)


@pytest.mark.asyncio
async def test_model_picker_cancel():
    """Verify /model with cancel doesn't crash."""
    r = MockRenderer()
    r.queue_input("/model")
    cli = _make_cli(r)

    await cli.run()

    assert "show_model_picker" in r.call_names()


@pytest.mark.asyncio
async def test_session_picker_cancel():
    """Verify /session with cancel doesn't crash."""
    r = MockRenderer()
    r.queue_input("/session")
    cli = _make_cli(r)

    await cli.run()

    assert "show_session_picker" in r.call_names()


@pytest.mark.asyncio
async def test_send_message_calls_renderer():
    """Verify sending a message triggers AI streaming lifecycle."""
    r = MockRenderer()
    r.queue_input("hello")
    cli = _make_cli(r)

    # Mock the bot to avoid real API calls
    mock_bot = MagicMock()

    async def fake_stream(*args, **kwargs):
        # Yield no events — just empty stream
        return
        yield  # make it an async generator

    mock_bot.astream_events = fake_stream

    # Run first to set up session, then inject mock bot
    await cli._start_session()
    cli._bot = mock_bot

    # Now run the main loop
    await cli.run()

    names = r.call_names()
    assert "show_user_message" in names
    assert "show_ai_start" in names
    assert "show_ai_end" in names


@pytest.mark.asyncio
async def test_streaming_with_tokens():
    """Verify tokens are dispatched to renderer during streaming."""
    r = MockRenderer()
    r.queue_input("hello")
    cli = _make_cli(r)

    # Mock bot that yields token chunks
    from langchain_core.messages import AIMessageChunk

    mock_bot = MagicMock()

    async def fake_stream(*args, **kwargs):
        chunk = AIMessageChunk(content="Hello world!")
        yield "messages", (chunk, {})

    mock_bot.astream_events = fake_stream

    # Set up session first, then inject mock bot
    await cli._start_session()
    cli._bot = mock_bot

    await cli.run()

    # Should have show_token and show_final_response
    names = r.call_names()
    assert "show_token" in names
    assert "show_final_response" in names


@pytest.mark.asyncio
async def test_extra_commands():
    """Verify extra_commands from config are dispatched."""
    handler = MagicMock()
    config = SonikaAppConfig(extra_commands={"ping": handler})

    r = MockRenderer()
    r.queue_input("/ping arg1")
    cli = _make_cli(r, config=config)

    await cli.run()

    handler.assert_called_once()
    call_args = handler.call_args[0]
    assert call_args[1] == ["arg1"]


# ── Integration test (requires GOOGLE_API_KEY) ───────────────────────────────

pytestmark_integration = pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set",
)


@pytest.mark.asyncio
@pytestmark_integration
async def test_send_real_message():
    """Send a real message to the API and verify response flows through renderer."""
    r = MockRenderer()
    r.queue_input("Say exactly: pong")
    cli = _make_cli(r)

    await cli.run()

    names = r.call_names()
    assert "show_user_message" in names
    assert "show_ai_start" in names

    # Check for errors first
    errors = r.calls_for("show_error")
    if errors:
        pytest.skip(f"API error (may be quota/network): {errors[0][0][:100]}")

    # Should have either tokens or final_response
    has_response = "show_token" in names or "show_final_response" in names
    assert has_response, f"No response tokens/final in: {names}"

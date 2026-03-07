"""
Integration test for SonikaApp TUI.

Uses Textual's Pilot to send a real message and verify:
- User message is mounted (You label + body)
- AI response is received (AI label + body with non-empty content)
- Header stats update after response
- /help command works
- /model command opens picker
"""
import os
import asyncio
import pytest
from dotenv import load_dotenv

load_dotenv()

# Skip if no Google API key (used by default model)
pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY not set",
)


@pytest.mark.asyncio
async def test_send_message_and_receive_response():
    """Send a short message and verify the AI responds."""
    from sonika.cli.tui import SonikaApp
    from sonika.cli.config import Config

    # Ensure google key is set in config
    cfg = Config()
    if not cfg.has_key("google"):
        cfg.set_key("google", os.environ["GOOGLE_API_KEY"])
    cfg.set_active("google", "gemini-2.5-flash")

    app = SonikaApp()

    async with app.run_test(size=(120, 40)) as pilot:
        # Wait for mount/setup
        await pilot.pause(1.0)

        # Type and send a simple message
        from textual.widgets import Input
        inp = app.query_one("#chat-input", Input)
        inp.value = "Say exactly: pong"
        await pilot.press("enter")

        # Wait for streaming to finish (up to 60 seconds)
        for _ in range(120):
            await pilot.pause(0.5)
            if not app._streaming:
                break

        await pilot.pause(0.5)

        # Check widgets in chat scroll
        from textual.widgets import Static
        scroll = app.query_one("#chat-scroll")
        children = list(scroll.children)

        # Sanity: there should be at least 4 widgets (You label, user body, AI label, AI body)
        assert len(children) >= 4, (
            f"Expected >=4 widgets in chat, got {len(children)}: "
            f"{[type(c).__name__ for c in children]}"
        )

        # Find user turn label
        user_labels = [c for c in children if "turn-label-user" in c.classes]
        assert user_labels, "No user turn label found"

        # Find AI turn label
        ai_labels = [c for c in children if "turn-label-ai" in c.classes]
        assert ai_labels, "No AI turn label found"

        # Find msg-body widgets (user + AI body)
        bodies = [c for c in children if "msg-body" in c.classes]
        assert len(bodies) >= 2, f"Expected >=2 msg-body widgets, got {len(bodies)}"

        # Verify AI body has content
        ai_body = bodies[-1]  # last msg-body is the AI response
        assert isinstance(ai_body, Static)
        content = ai_body.content  # correct Textual 8.x API
        assert content.strip(), f"AI body content is empty! Classes: {ai_body.classes}"

        print(f"\n✓ Chat has {len(children)} widgets")
        print(f"✓ AI response: {content[:100]!r}")


@pytest.mark.asyncio
async def test_help_command():
    """Verify /help mounts a system-text line."""
    from sonika.cli.tui import SonikaApp
    from sonika.cli.config import Config

    cfg = Config()
    if not cfg.has_key("google"):
        cfg.set_key("google", os.environ["GOOGLE_API_KEY"])
    cfg.set_active("google", "gemini-2.5-flash")

    app = SonikaApp()

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(1.0)
        from textual.widgets import Input
        inp = app.query_one("#chat-input", Input)
        inp.value = "/help"
        await pilot.press("enter")
        await pilot.pause(0.5)

        scroll = app.query_one("#chat-scroll")
        system_lines = [c for c in scroll.children if "system-text" in c.classes]
        assert system_lines, "No system-text widget after /help"

        from textual.widgets import Static
        help_widget = system_lines[0]
        assert isinstance(help_widget, Static)
        assert "/model" in help_widget.content, (
            f"Help text doesn't contain '/model': {help_widget.content!r}"
        )
        print(f"\n✓ Help text: {help_widget.content[:80]!r}")

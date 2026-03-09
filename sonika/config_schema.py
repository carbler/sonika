"""Extensible configuration for Sonika-based apps."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class SonikaAppConfig:
    """Configuration dataclass for Sonika and derivative apps (e.g. sonika-code)."""

    # Branding
    app_name: str = "Sonika"
    app_title: str = "SONIKA"

    # Prompts
    prompts_dir: str | None = None
    system_instructions: str = (
        "You are Sonika CLI (ExecutorBot Edition). "
        "Use provided tools to execute precise coding and system tasks. "
        "Always reason before acting. If you modify files, verify changes."
    )

    # Tools
    tool_groups: list[str] = field(
        default_factory=lambda: ["core", "integrations", "scheduler"]
    )
    extra_tools: list[Any] = field(default_factory=list)
    extra_tool_groups: dict[str, Callable] = field(default_factory=dict)

    # Behavior
    default_provider: str = "google"
    default_model: str = "gemini-2.5-flash"
    risk_level: int = 2

    # Paths
    config_dir: Path = field(default_factory=lambda: Path.home() / ".sonika")

    # Custom commands
    extra_commands: dict[str, Callable] = field(default_factory=dict)

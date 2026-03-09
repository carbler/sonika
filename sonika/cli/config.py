"""Config manager — stores API keys and active model in ~/.sonika/config.json."""

import json
from pathlib import Path
from typing import Optional

SONIKA_DIR = Path.home() / ".sonika"
CONFIG_FILE = SONIKA_DIR / "config.json"

PROVIDERS = ["openai", "google", "deepseek"]


class Config:
    def __init__(self, config_dir: Path | None = None):
        self._dir = config_dir or SONIKA_DIR
        self._file = self._dir / "config.json"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._data: dict = {}
        self._load()

    def _load(self):
        if self._file.exists():
            try:
                self._data = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        # Merge with existing file to preserve keys written by other components
        on_disk: dict = {}
        if self._file.exists():
            try:
                on_disk = json.loads(self._file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                on_disk = {}
        on_disk.update(self._data)
        self._file.write_text(
            json.dumps(on_disk, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── API Keys ──────────────────────────────────────────────────────────────

    def get_key(self, provider: str) -> Optional[str]:
        return self._data.get("keys", {}).get(provider)

    def set_key(self, provider: str, key: str):
        if "keys" not in self._data:
            self._data["keys"] = {}
        self._data["keys"][provider] = key
        self._save()

    def has_key(self, provider: str) -> bool:
        return bool(self.get_key(provider))

    # ── Active model ──────────────────────────────────────────────────────────

    @property
    def active_provider(self) -> Optional[str]:
        return self._data.get("active_provider")

    @property
    def active_model(self) -> Optional[str]:
        return self._data.get("active_model")

    def set_active(self, provider: str, model: str):
        self._data["active_provider"] = provider
        self._data["active_model"] = model
        self._save()

    # ── Status ────────────────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        has_any_key = any(self.has_key(p) for p in PROVIDERS)
        return has_any_key and bool(self.active_provider) and bool(self.active_model)

    def configured_providers(self) -> list[str]:
        return [p for p in PROVIDERS if self.has_key(p)]

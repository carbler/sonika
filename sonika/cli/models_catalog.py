"""Catalog of reasoning models with pricing and context window info."""

from dataclasses import dataclass
from typing import List


@dataclass
class ModelInfo:
    provider: str
    model_id: str
    context_k: int        # context window in thousands of tokens
    input_per_1m: float   # USD per 1M input tokens
    output_per_1m: float  # USD per 1M output tokens

    @property
    def context_label(self) -> str:
        if self.context_k >= 1_000_000:
            return f"{self.context_k // 1_000_000}M"
        if self.context_k >= 1000:
            return f"{self.context_k // 1000}K"
        return str(self.context_k)

    @property
    def price_label(self) -> str:
        if self.input_per_1m == 0 and self.output_per_1m == 0:
            return "free"
        return f"${self.input_per_1m:.2f} / ${self.output_per_1m:.2f}"

    def cost_for(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in / 1_000_000) * self.input_per_1m + (
            tokens_out / 1_000_000
        ) * self.output_per_1m


MODELS: List[ModelInfo] = [
    ModelInfo("openai",    "o4-mini",                       200_000,   1.10,  4.40),
    ModelInfo("openai",    "o3-mini",                       200_000,   1.10,  4.40),
    ModelInfo("openai",    "o3",                            200_000,  10.00, 40.00),
    ModelInfo("openai",    "o1",                            200_000,  15.00, 60.00),
    ModelInfo("openai",    "o1-mini",                       128_000,   3.00, 12.00),
    ModelInfo("google",    "gemini-2.5-pro",              1_000_000,   1.25, 10.00),
    ModelInfo("google",    "gemini-2.5-flash",            1_000_000,   0.15,  0.60),
    ModelInfo("google",    "gemini-2.0-flash-thinking-exp",1_000_000, 0.00,  0.00),
    ModelInfo("deepseek",  "deepseek-reasoner",             64_000,   0.55,  2.19),
]

_BY_KEY: dict[tuple[str, str], ModelInfo] = {
    (m.provider, m.model_id): m for m in MODELS
}


def get_model(provider: str, model_id: str) -> ModelInfo | None:
    return _BY_KEY.get((provider, model_id))


def models_for_provider(provider: str) -> List[ModelInfo]:
    return [m for m in MODELS if m.provider == provider]


def all_providers() -> List[str]:
    seen: list[str] = []
    for m in MODELS:
        if m.provider not in seen:
            seen.append(m.provider)
    return seen

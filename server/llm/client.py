"""
DeepSeek client base classes and factory for Texas Hold'em Poker AI.

Provides:
- LLMDecision dataclass for structured LLM responses.
- LLMClient ABC for LLM provider adapters.
- LLMClientFactory to instantiate the DeepSeek adapter from YAML config.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class LLMDecision:
    """Structured decision returned by an LLM.

    Attributes:
        action: One of ``"FOLD"``, ``"CHECK"``, ``"CALL"``, ``"RAISE"``,
                ``"ALL_IN"``.
        amount: Bet amount (meaningful for RAISE / ALL_IN).
        reasoning: Human-readable explanation of the decision.
        confidence: How confident the LLM is in its decision (0.0-1.0).
    """

    action: str
    amount: int = 0
    reasoning: str = ""
    confidence: float = 0.5


# ---------------------------------------------------------------------------
# Abstract Base Class
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """Abstract interface for LLM provider adapters.

    Subclasses must implement ``async def decide(self, prompt: str)`` and
    return an :class:`LLMDecision`.
    """

    @abstractmethod
    async def decide(self, prompt: str) -> LLMDecision:
        """Send *prompt* to the LLM and return a structured poker decision.

        Args:
            prompt: The full prompt string to send.

        Returns:
            An :class:`LLMDecision` with the LLM's chosen action.
        """
        ...


# ---------------------------------------------------------------------------
# Shared helpers (used by all adapters)
# ---------------------------------------------------------------------------


def _envsubst(value: Optional[str]) -> Optional[str]:
    """Substitute ``${ENV_VAR}`` patterns in *value*.

    Returns *value* unchanged if it is ``None`` or contains no ``${}`` patterns.
    """
    if value is None:
        return None
    # Match ${VAR_NAME} patterns
    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")
    return re.sub(r"\$\{(\w+)\}", _replacer, value)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class LLMClientFactory:
    """Create the DeepSeek client configured in ``config/llm_config.yaml``."""

    @staticmethod
    def create(config_path: Optional[str] = None) -> Optional[LLMClient]:
        """Create a DeepSeek client, or ``None`` without ``DEEPSEEK_API_KEY``."""
        if config_path is None:
            config_path = str(
                Path(__file__).resolve().parent.parent.parent
                / "config"
                / "llm_config.yaml"
            )

        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                config = yaml.safe_load(fh) or {}
        except Exception:
            return None

        api_key = _envsubst(config.get("api_key", "")) or ""
        if not api_key.strip():
            return None

        from server.llm.deepseek_adapter import DeepSeekAdapter

        config["api_key"] = api_key
        return DeepSeekAdapter(config)

"""
OpenAI adapter for Texas Hold'em Poker AI.

Uses the OpenAI Chat Completions API to request a poker decision and parses
the JSON response into an :class:`LLMDecision`.
"""

from __future__ import annotations

import logging
from typing import Optional

import aiohttp

from server.llm.client import (
    LLMClient,
    LLMDecision,
    _envsubst,
    _extract_json_from_response,
)

logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMClient):
    """LLM client for OpenAI's Chat Completions API.

    Configuration keys read from the YAML config dict:

    * ``model`` — model id (default ``"gpt-4"``).
    * ``api_key`` — API key or ``${ENV_VAR}`` placeholder.
    * ``max_tokens`` — maximum output tokens (default 500).
    * ``temperature`` — sampling temperature (default 0.7).
    * ``timeout_seconds`` — HTTP request timeout (default 30).
    """

    def __init__(self, config: dict) -> None:
        self.model = config.get("model", "gpt-4")
        self.api_key = _envsubst(config.get("api_key", ""))
        self.max_tokens = config.get("max_tokens", 500)
        self.temperature = config.get("temperature", 0.7)
        self.timeout = config.get("timeout_seconds", 30)
        self._api_url = "https://api.openai.com/v1/chat/completions"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decide(self, prompt: str) -> LLMDecision:
        """Send *prompt* to OpenAI and return a structured poker decision.

        On any error returns a conservative ``FOLD`` fallback.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self._api_url, json=payload, headers=headers
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(
                            "OpenAI API error %s: %s", resp.status, error_text[:500]
                        )
                        return self._fallback()

                    data = await resp.json()

        except aiohttp.ClientError as exc:
            logger.error("OpenAI API request failed: %s", exc)
            return self._fallback()
        except Exception as exc:
            logger.error("Unexpected error calling OpenAI: %s", exc)
            return self._fallback()

        text = self._extract_text(data)
        if not text:
            logger.error("OpenAI response contained no text content.")
            return self._fallback()

        return self._parse_decision(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(data: dict) -> Optional[str]:
        """Pull the first message content from a Chat Completions response."""
        choices = data.get("choices", [])
        if not choices:
            return None
        message = choices[0].get("message", {})
        return message.get("content", "")

    def _parse_decision(self, text: str) -> LLMDecision:
        """Parse JSON from the LLM's text response.

        Falls back to a conservative ``FOLD`` on parse failure.
        """
        parsed = _extract_json_from_response(text)
        if parsed is None:
            logger.warning(
                "Failed to extract JSON from OpenAI response: %s", text[:300]
            )
            return self._fallback()

        action = str(parsed.get("action", "FOLD")).upper()
        amount = int(parsed.get("amount", 0))
        reasoning = str(parsed.get("reasoning", ""))
        confidence = float(parsed.get("confidence", 0.5))

        valid_actions = {"FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"}
        if action not in valid_actions:
            logger.warning("Invalid action '%s' from OpenAI, falling back to FOLD.", action)
            return self._fallback()

        return LLMDecision(
            action=action,
            amount=max(0, amount),
            reasoning=reasoning,
            confidence=max(0.0, min(1.0, confidence)),
        )

    def _fallback(self) -> LLMDecision:
        """Conservative fallback when the LLM is unreachable."""
        return LLMDecision(
            action="FOLD",
            amount=0,
            reasoning="LLM unavailable — conservative fold.",
            confidence=0.0,
        )

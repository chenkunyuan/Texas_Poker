"""
Generic OpenAI-compatible adapter for Texas Hold'em Poker AI.

Supports any API that implements an OpenAI-compatible
``/chat/completions`` endpoint (e.g. Ollama, vLLM, local models,
third-party proxies).

Configuration is read from the ``custom`` block in the YAML config.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp

from server.llm.client import (
    LLMClient,
    LLMDecision,
    _envsubst,
    _extract_json_from_response,
)

logger = logging.getLogger(__name__)


class CustomAdapter(LLMClient):
    """LLM client for any OpenAI-compatible Chat Completions API.

    Reads these keys from the top-level config:

    * ``model`` — model id to pass in the request body.
    * ``max_tokens`` — maximum output tokens (default 500).
    * ``temperature`` — sampling temperature (default 0.7).
    * ``timeout_seconds`` — HTTP request timeout (default 30).

    Reads these keys from the ``custom`` block:

    * ``base_url`` — the base URL of the API (required).
    * ``api_key_env`` — environment variable holding the API key.
    * ``headers`` — extra headers to include in every request (dict).
    """

    def __init__(self, config: dict) -> None:
        custom = config.get("custom", {}) or {}

        self.model = config.get("model", "local-model")
        self.max_tokens = config.get("max_tokens", 500)
        self.temperature = config.get("temperature", 0.7)
        self.timeout = config.get("timeout_seconds", 30)

        # Custom-provider specifics
        base_url = custom.get("base_url", "")
        if isinstance(base_url, str) and base_url:
            self._api_url = base_url.rstrip("/") + "/chat/completions"
        else:
            self._api_url = "http://localhost:11434/v1/chat/completions"

        api_key_env = custom.get("api_key_env")
        if api_key_env:
            self.api_key = os.environ.get(api_key_env, "")
        else:
            self.api_key = _envsubst(config.get("api_key", "")) or ""

        self._extra_headers = custom.get("headers", {}) or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def decide(self, prompt: str) -> LLMDecision:
        """Send *prompt* to the custom API and return a structured decision.

        On any error returns a conservative ``FOLD`` fallback.
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Merge extra headers from config
        headers.update(self._extra_headers)

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
                            "Custom API error %s from %s: %s",
                            resp.status,
                            self._api_url,
                            error_text[:500],
                        )
                        return self._fallback()

                    data = await resp.json()

        except aiohttp.ClientError as exc:
            logger.error("Custom API request failed (%s): %s", self._api_url, exc)
            return self._fallback()
        except Exception as exc:
            logger.error("Unexpected error calling custom API: %s", exc)
            return self._fallback()

        text = self._extract_text(data)
        if not text:
            logger.error("Custom API response contained no text content.")
            return self._fallback()

        return self._parse_decision(text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text(data: dict) -> Optional[str]:
        """Pull the first message content from an OpenAI-compatible response."""
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
                "Failed to extract JSON from custom API response: %s", text[:300]
            )
            return self._fallback()

        action = str(parsed.get("action", "FOLD")).upper()
        amount = int(parsed.get("amount", 0))
        reasoning = str(parsed.get("reasoning", ""))
        confidence = float(parsed.get("confidence", 0.5))

        valid_actions = {"FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"}
        if action not in valid_actions:
            logger.warning("Invalid action '%s' from custom API, falling back to FOLD.", action)
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

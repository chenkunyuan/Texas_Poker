"""OpenAI Responses API adapter for poker AI decisions."""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from server.llm.client import LLMClient, LLMDecision, _envsubst

logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """Raised when OpenAI cannot provide a usable poker decision."""


class OpenAIPokerDecision(BaseModel):
    """Schema enforced for every OpenAI poker decision."""

    action: Literal["FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"]
    amount: int = Field(default=0, ge=0)
    reasoning: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)


class OpenAIAdapter(LLMClient):
    """Request schema-validated poker decisions from OpenAI."""

    def __init__(self, config: dict, client: Optional[Any] = None) -> None:
        self.model = config.get("model", "gpt-5.6-terra")
        self.api_key = _envsubst(config.get("api_key", "")) or ""
        self.max_output_tokens = int(config.get("max_output_tokens", 500))
        self.timeout = float(config.get("timeout_seconds", 30))
        self._client = client or AsyncOpenAI(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=0,
        )

    async def decide(self, prompt: str) -> LLMDecision:
        """Return an OpenAI decision or raise a controlled service error."""
        try:
            response = await self._client.responses.parse(
                model=self.model,
                input=[{"role": "user", "content": prompt}],
                text_format=OpenAIPokerDecision,
                max_output_tokens=self.max_output_tokens,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise LLMServiceError("OpenAI returned no parsed decision")
        except LLMServiceError:
            raise
        except Exception as exc:
            logger.warning(
                "OpenAI decision request failed: %s", type(exc).__name__
            )
            raise LLMServiceError("OpenAI decision request failed") from exc

        return LLMDecision(
            action=parsed.action,
            amount=parsed.amount,
            reasoning=parsed.reasoning,
            confidence=parsed.confidence,
        )

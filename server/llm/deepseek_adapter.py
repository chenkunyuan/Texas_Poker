"""DeepSeek Chat Completions adapter for poker AI decisions."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from server.llm.client import LLMClient, LLMDecision, _envsubst

logger = logging.getLogger(__name__)


class DeepSeekServiceError(RuntimeError):
    """Raised when DeepSeek cannot provide a usable poker decision."""


class DeepSeekPokerDecision(BaseModel):
    action: Literal["FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"]
    amount: int = Field(default=0, ge=0)
    reasoning: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)


class DeepSeekAdapter(LLMClient):
    def __init__(self, config: dict, client: Optional[Any] = None) -> None:
        self.model = config.get("model", "deepseek-v4-flash")
        self.api_key = _envsubst(config.get("api_key", "")) or ""
        self.max_tokens = int(config.get("max_tokens", 500))
        self.timeout = float(config.get("timeout_seconds", 30))
        self._client = client or AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
            timeout=self.timeout,
            max_retries=0,
        )

    async def decide(self, prompt: str) -> LLMDecision:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            if not content:
                raise DeepSeekServiceError("DeepSeek returned empty content")
            parsed = DeepSeekPokerDecision.model_validate(json.loads(content))
        except DeepSeekServiceError:
            raise
        except (json.JSONDecodeError, ValidationError, IndexError, AttributeError) as exc:
            logger.warning("DeepSeek response invalid: %s", type(exc).__name__)
            raise DeepSeekServiceError("DeepSeek response invalid") from exc
        except Exception as exc:
            logger.warning("DeepSeek request failed: %s", type(exc).__name__)
            raise DeepSeekServiceError("DeepSeek request failed") from exc

        return LLMDecision(
            action=parsed.action,
            amount=parsed.amount,
            reasoning=parsed.reasoning,
            confidence=parsed.confidence,
        )

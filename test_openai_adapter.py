import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from server.llm.openai_adapter import (
    LLMServiceError,
    OpenAIAdapter,
    OpenAIPokerDecision,
)


class OpenAIAdapterTests(unittest.IsolatedAsyncioTestCase):
    def _adapter(self, parse_mock: AsyncMock) -> OpenAIAdapter:
        client = SimpleNamespace(responses=SimpleNamespace(parse=parse_mock))
        return OpenAIAdapter(
            {
                "model": "gpt-5.6-terra",
                "api_key": "test-key",
                "max_output_tokens": 500,
                "timeout_seconds": 3,
            },
            client=client,
        )

    async def test_returns_schema_validated_decision(self):
        parsed = OpenAIPokerDecision(
            action="RAISE", amount=120, reasoning="Value bet", confidence=0.82
        )
        parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))

        decision = await self._adapter(parse).decide("poker state")

        self.assertEqual(decision.action, "RAISE")
        self.assertEqual(decision.amount, 120)
        self.assertAlmostEqual(decision.confidence, 0.82)
        self.assertEqual(parse.await_args.kwargs["text_format"], OpenAIPokerDecision)

    async def test_missing_parsed_output_raises_controlled_error(self):
        adapter = self._adapter(
            AsyncMock(return_value=SimpleNamespace(output_parsed=None))
        )
        with self.assertRaises(LLMServiceError):
            await adapter.decide("poker state")

    async def test_sdk_failure_raises_controlled_error(self):
        adapter = self._adapter(AsyncMock(side_effect=RuntimeError("network")))
        with self.assertRaises(LLMServiceError):
            await adapter.decide("poker state")


if __name__ == "__main__":
    unittest.main()

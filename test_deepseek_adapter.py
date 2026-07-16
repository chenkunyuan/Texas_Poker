import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from server.llm.deepseek_adapter import (
    DeepSeekAdapter,
    DeepSeekServiceError,
)


class DeepSeekAdapterTests(unittest.IsolatedAsyncioTestCase):
    def _adapter(self, create_mock: AsyncMock) -> DeepSeekAdapter:
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_mock)
            )
        )
        return DeepSeekAdapter(
            {
                "model": "deepseek-v4-flash",
                "api_key": "test-key",
                "max_tokens": 500,
                "timeout_seconds": 3,
            },
            client=client,
        )

    def test_configures_deepseek_base_url(self):
        with patch("server.llm.deepseek_adapter.AsyncOpenAI") as client_class:
            DeepSeekAdapter({"api_key": "test-key"})
        kwargs = client_class.call_args.kwargs
        self.assertEqual(kwargs["base_url"], "https://api.deepseek.com")
        self.assertEqual(kwargs["api_key"], "test-key")

    async def test_returns_validated_json_decision(self):
        content = (
            '{"action":"RAISE","amount":120,'
            '"reasoning":"Value bet","confidence":0.82}'
        )
        create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )
        )

        decision = await self._adapter(create).decide("Return JSON")

        self.assertEqual(decision.action, "RAISE")
        self.assertEqual(decision.amount, 120)
        self.assertAlmostEqual(decision.confidence, 0.82)
        kwargs = create.await_args.kwargs
        self.assertEqual(kwargs["model"], "deepseek-v4-flash")
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})

    async def test_empty_content_raises_controlled_error(self):
        create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
            )
        )
        with self.assertRaises(DeepSeekServiceError):
            await self._adapter(create).decide("Return JSON")

    async def test_malformed_json_raises_controlled_error(self):
        create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="not json"))]
            )
        )
        with self.assertRaises(DeepSeekServiceError):
            await self._adapter(create).decide("Return JSON")

    async def test_schema_violation_raises_controlled_error(self):
        content = (
            '{"action":"WAIT","amount":0,'
            '"reasoning":"Invalid","confidence":0.5}'
        )
        create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )
        )
        with self.assertRaises(DeepSeekServiceError):
            await self._adapter(create).decide("Return JSON")

    async def test_sdk_failure_raises_controlled_error(self):
        adapter = self._adapter(AsyncMock(side_effect=RuntimeError("network")))
        with self.assertRaises(DeepSeekServiceError):
            await adapter.decide("Return JSON")


if __name__ == "__main__":
    unittest.main()

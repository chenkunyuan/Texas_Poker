import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.llm.client import LLMClientFactory
from server.models.schemas import GameConfig


class LLMClientFactoryTests(unittest.TestCase):
    def _config(self, directory: str) -> str:
        path = Path(directory) / "llm.yaml"
        path.write_text(
            "model: gpt-5.6-terra\napi_key: ${OPENAI_API_KEY}\n",
            encoding="utf-8",
        )
        return str(path)

    def test_missing_key_disables_llm(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"OPENAI_API_KEY": ""}, clear=False
        ):
            self.assertIsNone(LLMClientFactory.create(self._config(tmp)))

    def test_present_key_creates_openai_adapter(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False
        ):
            client = LLMClientFactory.create(self._config(tmp))

        self.assertEqual(type(client).__name__, "OpenAIAdapter")


class GameConfigTests(unittest.TestCase):
    def test_provider_field_is_not_part_of_game_config(self):
        config = GameConfig(ai_player_count=3)
        self.assertNotIn("llm_provider", config.model_dump())


if __name__ == "__main__":
    unittest.main()

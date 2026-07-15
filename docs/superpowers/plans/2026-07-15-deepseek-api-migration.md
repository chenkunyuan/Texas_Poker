# DeepSeek API Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the OpenAI Responses integration with DeepSeek V4 Flash through the OpenAI-compatible Chat Completions API.

**Architecture:** `AIManager` and its rule-engine-first trigger flow remain unchanged. A renamed `DeepSeekAdapter` calls `chat.completions.create` with JSON Output, parses the returned JSON string, validates it with Pydantic, and raises a controlled error so the existing manager retains its rule decision on failure.

**Tech Stack:** Python 3.9+, OpenAI Python SDK 2.45.0 as the DeepSeek-compatible client, Pydantic 2, DeepSeek Chat Completions, `unittest`.

## Global Constraints

- Implement on branch `codex/deepseek-api`.
- Use `https://api.deepseek.com`, model `deepseek-v4-flash`, and `DEEPSEEK_API_KEY`.
- Preserve the existing trigger thresholds, rule-engine fallback, legal-action validation, and raise clamping.
- Never log credentials, complete prompts, raw response bodies, or private cards belonging to other players.
- Keep requests stateless and do not persist reasoning content or response identifiers.

---

### Task 1: DeepSeek Chat Completions adapter

**Files:**
- Delete: `server/llm/openai_adapter.py`
- Create: `server/llm/deepseek_adapter.py`
- Delete: `test_openai_adapter.py`
- Create: `test_deepseek_adapter.py`

**Interfaces:**
- Consumes: `LLMClient`, `LLMDecision`, and `_envsubst` from `server.llm.client`.
- Produces: `DeepSeekPokerDecision(BaseModel)`, `DeepSeekServiceError(RuntimeError)`, and `DeepSeekAdapter.decide(prompt: str) -> LLMDecision`.
- The optional injected client must expose async `chat.completions.create(...)`.

- [ ] **Step 1: Replace the old adapter test with failing DeepSeek tests**

Create `test_deepseek_adapter.py`:

```python
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from server.llm.deepseek_adapter import (
    DeepSeekAdapter,
    DeepSeekPokerDecision,
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
```

Delete `test_openai_adapter.py` only after its DeepSeek replacement exists.

- [ ] **Step 2: Run the new test and confirm it fails**

Run: `.\.venv\Scripts\python.exe -m unittest test_deepseek_adapter.py -v`

Expected: import failure because `server.llm.deepseek_adapter` does not exist.

- [ ] **Step 3: Implement the DeepSeek adapter**

Create `server/llm/deepseek_adapter.py`:

```python
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
```

Delete `server/llm/openai_adapter.py` after the new adapter is present.

- [ ] **Step 4: Run adapter tests**

Run: `.\.venv\Scripts\python.exe -m unittest test_deepseek_adapter.py -v`

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/llm/openai_adapter.py server/llm/deepseek_adapter.py test_openai_adapter.py test_deepseek_adapter.py
git commit -m "feat: add DeepSeek poker adapter"
```

---

### Task 2: Factory, prompt, and configuration migration

**Files:**
- Modify: `server/llm/client.py`
- Modify: `server/ai/prompts.py`
- Modify: `config/llm_config.yaml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `test_llm_factory.py`
- Modify: `test_ai_manager_llm.py`

**Interfaces:**
- Consumes: `DeepSeekAdapter(config: dict)` from Task 1.
- Produces: `LLMClientFactory.create(...) -> Optional[DeepSeekAdapter]` using `DEEPSEEK_API_KEY` and a prompt that explicitly requests the schema required by JSON Output.

- [ ] **Step 1: Write failing factory and prompt assertions**

In `test_llm_factory.py`, replace `_config`, the missing-key test, and the
present-key test with:

```python
def _config(self, directory: str) -> str:
    path = Path(directory) / "llm.yaml"
    path.write_text(
        "model: deepseek-v4-flash\napi_key: ${DEEPSEEK_API_KEY}\n",
        encoding="utf-8",
    )
    return str(path)

def test_missing_key_disables_llm(self):
    with tempfile.TemporaryDirectory() as tmp, patch.dict(
        os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False
    ):
        self.assertIsNone(LLMClientFactory.create(self._config(tmp)))

def test_present_key_creates_deepseek_adapter(self):
    with tempfile.TemporaryDirectory() as tmp, patch.dict(
        os.environ, {"DEEPSEEK_API_KEY": "test-key"}, clear=False
    ):
        client = LLMClientFactory.create(self._config(tmp))

    self.assertEqual(type(client).__name__, "DeepSeekAdapter")
```

In `test_ai_manager_llm.py`, replace the prompt-shape test with:

```python
def test_prompt_explicitly_requests_json_schema(self):
    prompt = build_poker_prompt(
        personality=None,
        hole_cards=[],
        community_cards=[],
        pot=0,
        current_bet=0,
        player_chips=100,
        position=None,
        action_history=[],
    )
    self.assertIn("single JSON object", prompt)
    self.assertIn('"action"', prompt)
    self.assertIn('"confidence"', prompt)
```

- [ ] **Step 2: Run tests and confirm factory/prompt failures**

Run: `.\.venv\Scripts\python.exe -m unittest test_llm_factory.py test_ai_manager_llm.py -v`

Expected: failures because the factory still imports `OpenAIAdapter` and the prompt does not request JSON.

- [ ] **Step 3: Switch the factory to DeepSeek**

In `server/llm/client.py`, keep the missing-key early return and replace the local import/return with:

```python
from server.llm.deepseek_adapter import DeepSeekAdapter

config["api_key"] = api_key
return DeepSeekAdapter(config)
```

Update module, class, and return-value docstrings from OpenAI to DeepSeek and state that `DEEPSEEK_API_KEY` is required.

Use these exact factory docstrings:

```python
class LLMClientFactory:
    """Create the DeepSeek client configured in ``config/llm_config.yaml``."""

    @staticmethod
    def create(config_path: Optional[str] = None) -> Optional[LLMClient]:
        """Create a DeepSeek client, or ``None`` without ``DEEPSEEK_API_KEY``."""
```

- [ ] **Step 4: Restore explicit JSON instructions in the poker prompt**

Replace the two final structured-API instruction lines in `server/ai/prompts.py` with:

```python
lines.append("Respond with a single JSON object in exactly this shape:")
lines.append("{")
lines.append('  "action": "FOLD|CHECK|CALL|RAISE|ALL_IN",')
lines.append('  "amount": 0,')
lines.append('  "reasoning": "brief poker reasoning",')
lines.append('  "confidence": 0.0')
lines.append("}")
lines.append("Use an integer amount and confidence between 0.0 and 1.0.")
```

- [ ] **Step 5: Update runtime configuration and documentation**

Set the top of `config/llm_config.yaml` to:

```yaml
# DeepSeek Chat Completions configuration
model: deepseek-v4-flash
api_key: ${DEEPSEEK_API_KEY}
max_tokens: 500
timeout_seconds: 30
```

Keep the existing `trigger` block unchanged. Set `.env.example` to:

```dotenv
# DeepSeek API key for AI poker decisions. Never commit a real key.
DEEPSEEK_API_KEY=sk-...
```

In `README.md`, make these exact replacements:

```text
Rule engine + DeepSeek V4 Flash enhancement for difficult decisions

Edit `config/llm_config.yaml` to tune DeepSeek and the trigger thresholds:

model: deepseek-v4-flash
api_key: ${DEEPSEEK_API_KEY}
max_tokens: 500
timeout_seconds: 30

Copy `.env.example` to `.env` and set `DEEPSEEK_API_KEY`. Never commit `.env`.

llm/                 # DeepSeek Chat Completions adapter

DeepSeek V4 Flash via the OpenAI-compatible Chat Completions API
```

Keep `openai==2.45.0` in `requirements.txt`; it remains the protocol-compatible
Python client and does not mean requests are sent to OpenAI.

- [ ] **Step 6: Run migrated tests and reference search**

Run: `.\.venv\Scripts\python.exe -m unittest test_deepseek_adapter.py test_llm_factory.py test_ai_manager_llm.py -v`

Expected: 12 tests pass.

Run: `rg -n "OpenAIAdapter|OpenAIPokerDecision|OPENAI_API_KEY|gpt-5.6-terra|responses.parse|openai_adapter" server config README.md .env.example test_*.py`

Expected: no matches for the removed OpenAI integration.

- [ ] **Step 7: Commit**

```bash
git add server/llm/client.py server/ai/prompts.py config/llm_config.yaml .env.example README.md test_llm_factory.py test_ai_manager_llm.py
git commit -m "refactor: switch poker AI to DeepSeek"
```

---

### Task 3: Regression and live verification

**Files:**
- Modify only if verification exposes a defect in files listed in Tasks 1-2.

**Interfaces:**
- Verifies imports, all unit and poker scenarios, server startup, secret handling, and one minimal real DeepSeek decision when account access permits.

- [ ] **Step 1: Compile and run all automated tests**

Run: `.\.venv\Scripts\python.exe -m compileall -q server test_deepseek_adapter.py test_llm_factory.py test_ai_manager_llm.py`

Run: `.\.venv\Scripts\python.exe -m unittest test_deepseek_adapter.py test_llm_factory.py test_ai_manager_llm.py -v`

Run: `.\.venv\Scripts\python.exe test_betting_and_pot.py`

Expected: compilation succeeds, 12 new tests pass, and all 11 poker scenarios pass.

- [ ] **Step 2: Verify server startup without starting a paid game**

Run: `.\.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000`

Verify: `GET /` returns 200 and `POST /api/game/start` accepts the provider-free `GameConfig`. Stop the server after the request.

- [ ] **Step 3: Make one minimal live DeepSeek request**

Run this short script through `.\.venv\Scripts\python.exe`:

```python
import asyncio

from dotenv import load_dotenv

from server.llm.client import LLMClientFactory

load_dotenv()
client = LLMClientFactory.create()
assert client is not None, "DeepSeek client unavailable"
decision = asyncio.run(
    client.decide(
        "Return JSON. Hold'em test: AK suited, pot 15, call 10, "
        "stack 990; legal actions FOLD, CALL, RAISE 20-990."
    )
)
print("action=" + decision.action)
print("amount=" + str(decision.amount))
print("confidence=" + str(decision.confidence))
```

Print only `action`, `amount`, and `confidence`; never print credentials, full prompts, reasoning, or raw errors.

Expected when account access is funded: a valid legal action is returned. If DeepSeek returns an account-side authentication, balance, or model-access error, report it separately; mocked tests and local fallback verification remain the code acceptance gate.

- [ ] **Step 4: Review branch scope and secrets**

Run: `git diff --check`

Run: `git status --short`

Run: `rg -n "sk-[A-Za-z0-9_-]{20,}" . -g '!.env' -g '!.venv/**' -g '!.git/**'`

Expected: no whitespace errors, `.env` absent from Git changes, no real secret patterns, and only `AGENTS.md` remains as the pre-existing unrelated untracked file.

- [ ] **Step 5: Commit verification fixes only if needed**

If verification required a correction, stage only the affected migration files and commit:

```bash
git commit -m "fix: complete DeepSeek migration verification"
```

If no correction was needed, do not create an empty commit.

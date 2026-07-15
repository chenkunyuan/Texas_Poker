# OpenAI AI Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all non-OpenAI LLM integrations with an OpenAI Responses API adapter while preserving rule-engine-first poker decisions and safe fallback behavior.

**Architecture:** `AIManager` keeps computing a rule decision before optionally calling one `OpenAIAdapter`. The adapter uses `AsyncOpenAI.responses.parse` with a Pydantic schema and raises a controlled error on API failure so `AIManager` retains the rule result. Startup loads the ignored root `.env`; missing credentials disable the LLM without stopping the game.

**Tech Stack:** Python 3.9+, FastAPI, Pydantic 2, OpenAI Python SDK 2.45.0, python-dotenv, vanilla JavaScript, `unittest`/`pytest`-compatible tests.

## Global Constraints

- Use the Responses API with model `gpt-5.6-terra`.
- Preserve the existing trigger thresholds and rule-engine-first decision flow.
- Never include opponents' hole cards, credentials, or full prompts in API logs.
- Remove Anthropic, custom-provider, provider-selection, and browser API-key UI support.
- Any OpenAI failure must retain the precomputed rule-engine result.

---

### Task 1: OpenAI-only configuration and credential loading

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `config/llm_config.yaml`
- Modify: `server/main.py`
- Modify: `server/llm/client.py`
- Create: `test_llm_factory.py`

**Interfaces:**
- Produces: `LLMClientFactory.create(config_path: Optional[str] = None) -> Optional[LLMClient]` that returns `None` without `OPENAI_API_KEY`, otherwise an `OpenAIAdapter`.
- Consumes: root `.env` loaded once by `server.main` and `${OPENAI_API_KEY}` substitution already provided by `_envsubst`.

- [ ] **Step 1: Write failing factory tests**

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.llm.client import LLMClientFactory


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

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm the old provider factory fails**

Run: `python -m unittest test_llm_factory.py -v`

Expected: FAIL because the current factory requires `provider: openai` before it evaluates the credential.

- [ ] **Step 3: Pin dependencies and simplify configuration**

Set `requirements.txt` to include these new runtime entries while retaining the existing FastAPI, Uvicorn, WebSocket, PyYAML, and Pydantic pins:

```text
openai==2.45.0
python-dotenv==1.1.1
```

Remove the unused direct `httpx==0.27.0` pin because the OpenAI SDK owns its HTTP dependency. Set `.env.example` to:

```dotenv
# OpenAI API key for AI poker decisions. Never commit a real key.
OPENAI_API_KEY=sk-proj-...
```

Replace the provider-specific portion of `config/llm_config.yaml` with:

```yaml
# OpenAI Responses API configuration
model: gpt-5.6-terra
api_key: ${OPENAI_API_KEY}
max_output_tokens: 500
timeout_seconds: 30
```

Keep the existing `trigger` block unchanged.

- [ ] **Step 4: Load `.env` at application startup**

In `server/main.py`, import `load_dotenv` and execute this before constructing any LLM client:

```python
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
```

Keep the existing `_FRONTEND_DIR` derived from `_PROJECT_ROOT`; remove the later duplicate root assignment.

- [ ] **Step 5: Make the factory OpenAI-only and credential-aware**

Replace provider branching in `LLMClientFactory.create` with the following code. Keep the adapter import inside the method to avoid a circular import:

```python
api_key = _envsubst(config.get("api_key", "")) or ""
if not api_key.strip():
    return None

from server.llm.openai_adapter import OpenAIAdapter

config["api_key"] = api_key
return OpenAIAdapter(config)
```

Update factory docstrings to describe OpenAI-only behavior. Keep `_extract_json_from_response` temporarily because the old adapter still imports it until Task 2.

- [ ] **Step 6: Install dependencies and rerun factory tests**

Run: `pip install -r requirements.txt`

Run: `python -m unittest test_llm_factory.py -v`

Expected: 1 test passes.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example config/llm_config.yaml server/main.py server/llm/client.py test_llm_factory.py
git commit -m "refactor: configure OpenAI-only LLM client"
```

---

### Task 2: Structured Responses API adapter

**Files:**
- Modify: `server/llm/openai_adapter.py`
- Modify: `server/llm/client.py`
- Create: `test_openai_adapter.py`
- Modify: `test_llm_factory.py`

**Interfaces:**
- Produces: `OpenAIPokerDecision(BaseModel)`, `LLMServiceError(RuntimeError)`, and `OpenAIAdapter.decide(prompt: str) -> LLMDecision`.
- Consumes: `LLMDecision` from `server.llm.client` and an optional injected client exposing async `responses.parse(...)`.

- [ ] **Step 1: Write failing adapter tests**

```python
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
```

- [ ] **Step 2: Run tests and confirm the current Chat Completions adapter fails**

Run: `python -m unittest test_openai_adapter.py -v`

Expected: import or constructor failures because the schema, controlled error, injection point, and Responses API are absent.

- [ ] **Step 3: Implement the structured adapter**

Use this shape in `server/llm/openai_adapter.py`:

```python
import logging
from typing import Any, Literal, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from server.llm.client import LLMClient, LLMDecision, _envsubst

logger = logging.getLogger(__name__)


class LLMServiceError(RuntimeError):
    """Raised when OpenAI cannot provide a usable poker decision."""


class OpenAIPokerDecision(BaseModel):
    action: Literal["FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"]
    amount: int = Field(default=0, ge=0)
    reasoning: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)


class OpenAIAdapter(LLMClient):
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
            logger.warning("OpenAI decision request failed: %s", type(exc).__name__)
            raise LLMServiceError("OpenAI decision request failed") from exc

        return LLMDecision(
            action=parsed.action,
            amount=parsed.amount,
            reasoning=parsed.reasoning,
            confidence=parsed.confidence,
        )
```

Do not log `prompt`, `api_key`, response bodies, or exception text.

After the adapter no longer imports `_extract_json_from_response`, delete that helper from `server/llm/client.py` and remove the now-unused `re` import only if `_envsubst` is rewritten without it; `_envsubst` still requires `re` in the planned implementation.

Append this factory integration test to `LLMClientFactoryTests` in `test_llm_factory.py`:

```python
def test_present_key_creates_openai_adapter(self):
    with tempfile.TemporaryDirectory() as tmp, patch.dict(
        os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False
    ):
        client = LLMClientFactory.create(self._config(tmp))
        self.assertEqual(type(client).__name__, "OpenAIAdapter")
```

- [ ] **Step 4: Run adapter and factory tests**

Run: `python -m unittest test_openai_adapter.py test_llm_factory.py -v`

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/llm/openai_adapter.py server/llm/client.py test_openai_adapter.py test_llm_factory.py
git commit -m "feat: use structured OpenAI Responses decisions"
```

---

### Task 3: Preserve rule decisions on LLM failure and enforce isolation

**Files:**
- Modify: `server/ai/prompts.py`
- Modify: `server/ai/manager.py`
- Create: `test_ai_manager_llm.py`

**Interfaces:**
- Consumes: `LLMClient.decide(prompt) -> LLMDecision`, which may raise `LLMServiceError`.
- Produces: `AIManager.get_decision(...) -> Tuple[PlayerAction, int, str]`, retaining source `RULE` on every LLM failure.

- [ ] **Step 1: Write failing manager tests**

Create tests with a stub engine and client:

```python
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.ai.manager import AIManager
from server.models.schemas import GameState, Player, PlayerAction


class AIManagerLLMTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self, client):
        manager = AIManager(llm_client=client)
        manager._apply_thinking_delay = AsyncMock()
        manager._trigger_config = {"confidence_threshold": 1.0}
        engine = MagicMock()
        engine.decide.return_value = (PlayerAction.CALL, 10, 0.1)
        manager.engines["ai-1"] = engine
        return manager

    async def test_llm_failure_preserves_rule_result(self):
        client = MagicMock()
        client.decide = AsyncMock(side_effect=RuntimeError("unavailable"))
        manager = self._manager(client)
        state = GameState(players=[Player(id="ai-1", name="AI", chips=100)])
        player = state.players[0]
        valid = {"CALL": {"action": PlayerAction.CALL, "amount": 10}}

        with patch("server.ai.manager.RuleEngine.should_use_llm", return_value=True):
            result = await manager.get_decision(state, player, valid)

        self.assertEqual(result, (PlayerAction.CALL, 10, "RULE"))

    async def test_prompt_contains_only_acting_players_cards(self):
        client = MagicMock()
        client.decide = AsyncMock(side_effect=RuntimeError("stop after capture"))
        manager = self._manager(client)
        actor = Player(id="ai-1", name="AI", chips=100)
        opponent = Player(id="ai-2", name="Other", chips=100)
        state = GameState(players=[actor, opponent])

        with patch("server.ai.manager.build_poker_prompt", return_value="safe") as build:
            with patch("server.ai.manager.RuleEngine.should_use_llm", return_value=True):
                await manager.get_decision(state, actor, {"CHECK": {"action": PlayerAction.CHECK, "amount": 0}})

        self.assertEqual(build.call_args.kwargs["hole_cards"], actor.hole_cards)
        self.assertNotIn("players", build.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify the isolation/fallback contract**

Run: `python -m unittest test_ai_manager_llm.py -v`

Expected: tests pass only if the existing rule decision remains untouched on error and prompt construction receives no player collection. If the current implementation already satisfies a test, retain it as a regression test.

- [ ] **Step 3: Remove text-JSON prompt instructions**

Replace the final JSON/code-fence section of `build_poker_prompt` with:

```python
lines.append("Choose the strongest legal action for this situation.")
lines.append("Keep the reasoning brief and base it only on the information above.")
```

The Pydantic `text_format` now owns the output shape.

- [ ] **Step 4: Narrow manager error logging**

Keep the already-computed `action`, `amount`, and `decision_source = "RULE"` when `_call_llm` raises. Replace stack-trace logging with a safe category-only warning:

```python
except Exception as exc:
    logger.warning(
        "LLM decision unavailable for player %s: %s; using rule engine.",
        player.id,
        type(exc).__name__,
    )
```

Do not change legal-action validation or raise clamping.

- [ ] **Step 5: Run all backend tests**

Run: `python -m unittest test_openai_adapter.py test_llm_factory.py test_ai_manager_llm.py -v`

Run: `python test_betting_and_pot.py`

Expected: 7 new tests pass and the existing script ends with `All tests passed!`.

- [ ] **Step 6: Commit**

```bash
git add server/ai/prompts.py server/ai/manager.py test_ai_manager_llm.py
git commit -m "fix: retain rule decisions when OpenAI is unavailable"
```

---

### Task 4: Remove obsolete providers and frontend provider controls

**Files:**
- Delete: `server/llm/claude_adapter.py`
- Delete: `server/llm/custom_adapter.py`
- Modify: `server/models/schemas.py`
- Modify: `server/config.py`
- Modify: `server/main.py`
- Modify: `frontend/index.html`
- Modify: `frontend/js/setup.js`
- Modify: `README.md`

**Interfaces:**
- Produces: `GameConfig` without `llm_provider`; frontend start payload matches that schema.
- Consumes: server-level OpenAI configuration only; browser clients never receive or submit secrets.

- [ ] **Step 1: Add a schema regression test**

Append to `test_llm_factory.py`:

```python
from server.models.schemas import GameConfig


class GameConfigTests(unittest.TestCase):
    def test_provider_field_is_not_part_of_game_config(self):
        config = GameConfig(ai_player_count=3)
        self.assertNotIn("llm_provider", config.model_dump())
```

- [ ] **Step 2: Run the schema test and confirm it fails**

Run: `python -m unittest test_llm_factory.GameConfigTests -v`

Expected: FAIL because `llm_provider` is still present.

- [ ] **Step 3: Remove backend provider surface**

Delete `llm_provider` from `GameConfig`. Update `server/config.py` docstrings to describe OpenAI model and trigger settings. Remove `llm_provider` from the request example in `server/main.py`. Delete the Claude and custom adapter modules.

- [ ] **Step 4: Remove browser provider and key inputs**

Delete both `LLM Provider` and `API Key` form groups from `frontend/index.html`. Remove this property from `frontend/js/setup.js`:

```javascript
llm_provider: _readSelect("llm-provider", "anthropic"),
```

This ensures API keys are configured only on the server and never entered into an unused browser field.

- [ ] **Step 5: Update user documentation**

Change README feature/configuration text to state that the hybrid AI uses OpenAI only, with `gpt-5.6-terra` configured in `config/llm_config.yaml` and `OPENAI_API_KEY` stored in `.env`. Update the project tree and tech-stack descriptions so `server/llm/` is described as the OpenAI Responses adapter.

- [ ] **Step 6: Search for obsolete provider references**

Run: `rg -n "anthropic|claude|custom_adapter|llm_provider|llm-provider|api-key" server frontend config README.md requirements.txt`

Expected: no matches related to removed provider support or browser credentials.

- [ ] **Step 7: Run regression tests**

Run: `python -m unittest test_openai_adapter.py test_llm_factory.py test_ai_manager_llm.py -v`

Run: `python test_betting_and_pot.py`

Expected: all new tests pass and existing scenarios end with `All tests passed!`.

- [ ] **Step 8: Commit**

```bash
git add server/llm/claude_adapter.py server/llm/custom_adapter.py server/models/schemas.py server/config.py server/main.py frontend/index.html frontend/js/setup.js README.md test_llm_factory.py
git commit -m "refactor: remove non-OpenAI provider support"
```

---

### Task 5: End-to-end verification

**Files:**
- Modify only if verification exposes a migration defect in files already listed above.

**Interfaces:**
- Verifies the complete HTTP startup path, static frontend, and safe LLM-disable behavior.

- [ ] **Step 1: Verify syntax and imports**

Run: `python -m compileall server test_openai_adapter.py test_llm_factory.py test_ai_manager_llm.py`

Expected: compilation succeeds without errors.

- [ ] **Step 2: Run the complete automated suite**

Run: `python -m unittest test_openai_adapter.py test_llm_factory.py test_ai_manager_llm.py -v`

Run: `python test_betting_and_pot.py`

Expected: all tests pass.

- [ ] **Step 3: Smoke-test application startup without making a paid API call**

Run: `python -m uvicorn server.main:app --host 127.0.0.1 --port 8000`

Verify: `GET http://127.0.0.1:8000/` returns the setup page, the provider/API-key controls are absent, and server startup logs contain no credential values. Stop the server without starting a game so no OpenAI request is made.

- [ ] **Step 4: Review the final diff for secrets and scope**

Run: `git status --short`

Run: `git diff --check`

Run: `git diff --stat HEAD~4..HEAD`

Expected: `.env` is absent from status/diffs, no whitespace errors appear, and only migration files are changed.

- [ ] **Step 5: Commit verification-only fixes if needed**

If verification required a code correction, stage only that correction and commit it with:

```bash
git commit -m "fix: complete OpenAI migration verification"
```

If no correction was needed, do not create an empty commit.

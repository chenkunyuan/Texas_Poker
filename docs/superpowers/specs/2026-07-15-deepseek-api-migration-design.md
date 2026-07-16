# DeepSeek API Migration Design

## Goal

Replace the OpenAI Responses API integration with DeepSeek V4 Flash while preserving the rule-engine-first poker decision pipeline and its data-isolation guarantees.

## Architecture

Rename `server/llm/openai_adapter.py` to `server/llm/deepseek_adapter.py` and expose `DeepSeekAdapter`. The adapter will continue using the `openai` Python SDK, configured with `base_url="https://api.deepseek.com"`, `DEEPSEEK_API_KEY`, and model `deepseek-v4-flash`.

DeepSeek uses the OpenAI-compatible Chat Completions interface rather than the Responses API. `DeepSeekAdapter.decide` will call `chat.completions.create` with `response_format={"type": "json_object"}`. The poker prompt will explicitly request one JSON object with `action`, `amount`, `reasoning`, and `confidence`. The returned string will pass through `json.loads` and a Pydantic schema before becoming an `LLMDecision`.

`LLMClientFactory` will create only `DeepSeekAdapter`. `config/llm_config.yaml`, `.env.example`, README instructions, class names, and documentation will use DeepSeek terminology and `DEEPSEEK_API_KEY`. The existing OpenAI SDK dependency remains because DeepSeek officially supports its client format.

## Data Flow and Isolation

1. `RuleEngine` computes the baseline action and confidence.
2. Existing trigger thresholds decide whether to call DeepSeek.
3. The prompt contains public state plus only the acting AI player's hole cards.
4. DeepSeek returns JSON text through Chat Completions.
5. JSON and Pydantic validation run before `AIManager` validates legal actions and clamps bet amounts.
6. A valid DeepSeek decision changes the source to `LLM`; otherwise the original rule result remains.

Requests are stateless. Reasoning content, response IDs, and conversation history are not persisted.

## Error Handling

Missing credentials disable the LLM client without stopping the game. Network failures, timeouts, authentication errors, quota errors, empty content, malformed JSON, and schema validation failures raise a controlled service error. `AIManager` catches it and preserves the precomputed rule-engine decision. Logs include only safe categories such as exception type; they never contain credentials, full prompts, or raw response bodies.

## Testing

Mock Chat Completions to cover valid JSON, empty content, malformed JSON, schema violations, and SDK failures. Assert the DeepSeek base URL, `deepseek-v4-flash` model, and JSON Output request parameters. Retain tests for legal-action validation, raise clamping, rule fallback, and private-card isolation. Run all existing poker tests. When credentials and account balance permit, make one minimal live DeepSeek decision request without starting a full game.

## References

- [DeepSeek API quick start](https://api-docs.deepseek.com/)
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)

# OpenAI AI Migration Design

## Goal

Replace all Anthropic and custom LLM support with OpenAI while preserving the existing hybrid poker decision pipeline. The rule engine remains the default; OpenAI is consulted only for low-confidence or strategically important decisions.

## Architecture

`AIManager` continues to obtain a baseline action from `RuleEngine` and evaluate the configured trigger thresholds. When a trigger fires, it sends only public game information and the acting AI player's own hole cards to `OpenAIAdapter`.

`OpenAIAdapter` will use the asynchronous official Python SDK and the Responses API with `gpt-5.6-terra`. A Pydantic response model will constrain output to `action`, `amount`, `reasoning`, and `confidence`. `AIManager` remains responsible for validating actions and clamping bet amounts to the engine's current legal range.

The repository will support OpenAI only. Remove the Claude and custom adapters, provider branches, provider-specific configuration, frontend provider selector, and the unused provider field in `GameConfig`. `config/llm_config.yaml` will contain only OpenAI model, output, timeout, and trigger settings.

The ignored root `.env` file supplies `OPENAI_API_KEY`. Application startup will load this file without logging its contents. If the key is absent, the factory returns no LLM client and the game continues with rule-engine decisions.

## Data Flow and Isolation

1. `RuleEngine` creates a baseline decision and confidence score.
2. Existing thresholds decide whether to consult OpenAI.
3. The prompt contains public state plus only the acting player's private cards.
4. The Responses API returns a schema-validated decision.
5. `AIManager` verifies the action and amount, then records the source as `LLM` or retains the rule result.

Requests are stateless between decisions and hands. No response IDs or conversation history are retained.

## Error Handling

Missing credentials, timeouts, rate limits, network failures, API errors, refusals, and invalid structured results must preserve the already-computed rule-engine decision. The adapter raises a controlled error instead of manufacturing a `FOLD`. Logs may include the error category and HTTP status, but never credentials or full prompts.

## Testing

Add isolated tests using mocked SDK responses for successful parsing, timeout/rate-limit handling, invalid output, legal-action validation, raise clamping, and missing credentials. Retain data-isolation coverage so opponents' hole cards cannot enter prompts. Run the existing betting and pot suite alongside the new LLM tests. Verify that the frontend no longer sends or displays a provider choice and that configuration loads `OPENAI_API_KEY` from `.env`.

## References

- [OpenAI model guidance](https://developers.openai.com/api/docs/models)
- [GPT-5.6 model family](https://developers.openai.com/api/docs/models/gpt-5.6-sol)

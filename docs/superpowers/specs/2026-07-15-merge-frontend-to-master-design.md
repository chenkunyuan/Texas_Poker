# Merge Frontend Refactor into Master Design

## Goal

Bring the complete frontend-refactor increment into `master` without bringing
the DeepSeek API migration into `master`.

## Source Boundary

The source change set is the ordered commit range:

```text
origin/codex/deepseek-api..origin/codex/frontend-refactor
```

This range contains 29 commits. It includes the modular frontend, desktop
layout, action feedback, reconnect and pending-turn replay behavior, frontend
tests and documentation, plus the supporting changes to:

- `server/engine/game_controller.py`
- `server/main.py`
- `server/ws/manager.py`

It excludes the five commits in `master..origin/codex/deepseek-api`, including
the DeepSeek adapter, DeepSeek environment variable, model configuration, and
provider migration documentation.

## Integration Method

Create `codex/integrate-frontend-to-master` from `master`, then cherry-pick the
29 commits in chronological order. Resolve any conflict by preserving the
OpenAI configuration and provider implementation from `master` while retaining
the frontend-refactor behavior from the selected range. After structural
verification, fast-forward `master` to the integration branch.

This approach preserves the frontend-refactor commit history and avoids a
merge from `origin/codex/frontend-refactor`, which would also introduce its
DeepSeek ancestors.

## Verification

Per the user's instruction, do not run automated tests. Perform only structural
checks:

- confirm `master` contains the selected 29 commit changes;
- confirm `server/llm/openai_adapter.py` remains present;
- confirm `server/llm/deepseek_adapter.py` is absent;
- confirm configuration still uses `OPENAI_API_KEY` and the OpenAI model;
- confirm the worktree is clean after integration.

## Result

`master` retains its OpenAI backend and gains the frontend refactor together
with the WebSocket and turn-replay server support required by that frontend.

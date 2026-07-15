# Merge Frontend Refactor into Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the complete frontend-refactor increment and its supporting WebSocket server changes to `master` without adding the DeepSeek API migration.

**Architecture:** Use `origin/codex/deepseek-api` as the exclusion boundary and cherry-pick every commit through `origin/codex/frontend-refactor` onto an integration branch created from `master`. Preserve the OpenAI provider configuration during conflict resolution, structurally verify the resulting tree, then fast-forward `master` to the integration result.

**Tech Stack:** Git, JavaScript ES modules, HTML/CSS, Python, FastAPI/WebSockets

## Global Constraints

- Include all 29 commits in `origin/codex/deepseek-api..origin/codex/frontend-refactor`.
- Include supporting changes to `server/engine/game_controller.py`, `server/main.py`, and `server/ws/manager.py`.
- Do not include commits in `master..origin/codex/deepseek-api`.
- Preserve the OpenAI adapter, `OPENAI_API_KEY`, and the OpenAI model configuration from `master`.
- Per user instruction, do not run automated tests.
- Perform structural Git and content verification before updating `master`.

---

### Task 1: Confirm the Integration Baseline

**Files:**
- Inspect: repository and branch metadata
- Inspect: `docs/superpowers/specs/2026-07-15-merge-frontend-to-master-design.md`

**Interfaces:**
- Consumes: `master`, `origin/codex/deepseek-api`, and `origin/codex/frontend-refactor` refs
- Produces: a clean `codex/integrate-frontend-to-master` branch based on `master`

- [ ] **Step 1: Confirm branch and clean state**

Run:

```powershell
git status --short --branch
git merge-base master origin/codex/deepseek-api
git merge-base origin/codex/deepseek-api origin/codex/frontend-refactor
git rev-list --count origin/codex/deepseek-api..origin/codex/frontend-refactor
```

Expected: the integration branch is clean, both merge bases match the lower branch tips, and the selected range contains 29 commits.

### Task 2: Cherry-Pick the Frontend Increment

**Files:**
- Modify: `frontend/**`
- Modify: `server/engine/game_controller.py`
- Modify: `server/main.py`
- Modify: `server/ws/manager.py`
- Create: `test_websocket_turn_replay.py`
- Modify/Create: frontend-refactor documentation and tests selected by the commit range

**Interfaces:**
- Consumes: ordered commits in `origin/codex/deepseek-api..origin/codex/frontend-refactor`
- Produces: the frontend-refactor tree on top of the OpenAI-based integration branch

- [ ] **Step 1: Apply the commits in chronological order**

Run:

```powershell
git cherry-pick origin/codex/deepseek-api..origin/codex/frontend-refactor
```

Expected: all 29 commits apply, or Git pauses at an explicit conflict.

- [ ] **Step 2: Resolve any conflict without importing DeepSeek configuration**

For each conflict, compare the current `master`-based version with the selected frontend commit. Preserve OpenAI content in provider/configuration files and retain frontend-refactor content in UI and WebSocket lifecycle files, then run:

```powershell
git add --all
git cherry-pick --continue
```

Expected: the cherry-pick sequence completes with no unmerged paths.

### Task 3: Structurally Verify the Integrated Tree

**Files:**
- Inspect: `.env.example`
- Inspect: `config/llm_config.yaml`
- Inspect: `server/llm/openai_adapter.py`
- Confirm absent: `server/llm/deepseek_adapter.py`
- Inspect: integrated Git history and tree

**Interfaces:**
- Consumes: completed integration branch
- Produces: evidence that the frontend increment is present and DeepSeek migration is absent

- [ ] **Step 1: Verify provider files and configuration**

Run:

```powershell
git ls-files server/llm/openai_adapter.py server/llm/deepseek_adapter.py
rg -n "OPENAI_API_KEY|DEEPSEEK_API_KEY|deepseek" .env.example config/llm_config.yaml server/llm
```

Expected: `openai_adapter.py` is tracked, `deepseek_adapter.py` is absent, OpenAI configuration remains, and no DeepSeek provider reference appears in active configuration or `server/llm`.

- [ ] **Step 2: Verify the selected tree delta and clean state**

Run:

```powershell
git diff --check master..HEAD
git status --short --branch
git diff --stat master..HEAD
```

Expected: no whitespace errors, no uncommitted files, and the frontend/server-support change set is present.

### Task 4: Fast-Forward Master

**Files:**
- Modify: Git ref `master`

**Interfaces:**
- Consumes: verified `codex/integrate-frontend-to-master`
- Produces: local `master` pointing to the integration result

- [ ] **Step 1: Switch to master**

Run:

```powershell
git switch master
```

Expected: current branch becomes `master`.

- [ ] **Step 2: Fast-forward master only**

Run:

```powershell
git merge --ff-only codex/integrate-frontend-to-master
```

Expected: `master` advances to the integration branch tip without a merge commit.

- [ ] **Step 3: Verify final refs and state without running tests**

Run:

```powershell
git status --short --branch
git rev-parse master
git rev-parse codex/integrate-frontend-to-master
git log --oneline --decorate -5
```

Expected: both local refs match, `master` is clean, and it is ahead of `origin/master` by the design, plan, and 29 selected frontend-refactor commits.

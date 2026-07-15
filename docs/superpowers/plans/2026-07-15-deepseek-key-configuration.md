# DeepSeek API Key Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Securely migrate the existing DeepSeek API key from tracked YAML into ignored `.env`, align README instructions with runtime behavior, and restart the local game server.

**Architecture:** Keep secret material only in project-root `.env`, which `server/main.py` loads at startup. Keep model and trigger settings in `config/llm_config.yaml`, referencing `${DEEPSEEK_API_KEY}`, and document that single configuration path in Quick Start.

**Tech Stack:** Markdown, YAML, python-dotenv, PowerShell, Uvicorn

## Global Constraints

- Never print, log, commit, or copy the API key into a tracked file.
- Preserve all non-secret settings in `config/llm_config.yaml`.
- Keep `.env` ignored by Git.
- Bind the restarted server to `127.0.0.1:8000`.
- Verify the root page returns HTTP 200 after restart.

---

### Task 1: Migrate the Existing Secret

**Files:**
- Create: `.env`
- Modify: `config/llm_config.yaml`
- Inspect: `.gitignore`

**Interfaces:**
- Consumes: the existing literal `api_key` YAML value
- Produces: `DEEPSEEK_API_KEY` in ignored `.env` and `${DEEPSEEK_API_KEY}` in tracked YAML

- [ ] **Step 1: Confirm `.env` is ignored**

Run:

```powershell
git check-ignore -v .env
```

Expected: `.gitignore` reports the `.env` rule.

- [ ] **Step 2: Move the key without displaying it**

Run a local PowerShell transformation that reads the literal YAML value into
memory, rejects empty or already-indirect values, writes it as
`DEEPSEEK_API_KEY` in `.env`, and replaces only the YAML `api_key` line with:

```yaml
api_key: ${DEEPSEEK_API_KEY}
```

Expected: the command reports only `migration:ok`; it never prints the key.

### Task 2: Align README with Runtime Configuration

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the secure configuration boundary from Task 1
- Produces: one unambiguous Quick Start for PowerShell and POSIX shells

- [ ] **Step 1: Update Quick Start**

Add `.env.example` copy commands for PowerShell and POSIX before server startup,
show `DEEPSEEK_API_KEY=your-key-here` as a placeholder, and retain the dependency,
startup, and browser commands.

- [ ] **Step 2: Clarify the Configuration section**

State that `.env` stores secrets, `config/llm_config.yaml` stores non-secret
model and trigger settings, and the YAML must retain:

```yaml
api_key: ${DEEPSEEK_API_KEY}
```

State that configuration changes require a server restart and that `.env` must
never be committed.

### Task 3: Verify and Commit Tracked Changes

**Files:**
- Inspect: `.env`
- Inspect: `config/llm_config.yaml`
- Inspect: `README.md`
- Commit: `README.md`, `config/llm_config.yaml`, and this plan

**Interfaces:**
- Consumes: migrated configuration and updated documentation
- Produces: a tracked commit containing no secret

- [ ] **Step 1: Verify without exposing the secret**

Check that `.env` contains a non-placeholder `DEEPSEEK_API_KEY`, that YAML
contains exactly the environment reference, that `.env` is absent from
`git status`, and that the staged diff contains no literal API key.

- [ ] **Step 2: Commit only tracked documentation and configuration**

Run:

```powershell
git add README.md config/llm_config.yaml docs/superpowers/plans/2026-07-15-deepseek-key-configuration.md
git commit -m "docs: clarify secure DeepSeek key setup"
```

Expected: `.env` is not part of the commit.

### Task 4: Restart and Verify the Server

**Files:**
- Runtime only: Uvicorn process

**Interfaces:**
- Consumes: project configuration loaded through `.env`
- Produces: a local game server at `http://127.0.0.1:8000/`

- [ ] **Step 1: Start Uvicorn**

Run:

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Expected: Uvicorn remains running and listens on port 8000.

- [ ] **Step 2: Verify the root page**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/ -TimeoutSec 5
```

Expected: HTTP status 200.

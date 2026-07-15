# README Game Screenshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture three consistent screenshots from the real poker application and add them to a new README Screenshots section.

**Architecture:** Run the existing FastAPI application locally, use the in-app browser at a fixed 1366×768 viewport to drive a short real game, and save browser screenshots directly as PNG assets. Reference the repository-relative assets from README without changing application behavior.

**Tech Stack:** FastAPI/Uvicorn, in-app Chromium browser, PNG, Markdown

## Global Constraints

- Capture only the real application UI at `http://127.0.0.1:8000/`.
- Use a 1366×768 CSS viewport for every image.
- Do not expose API keys, browser chrome, developer tools, or desktop content.
- Save PNG files under `docs/images/`.
- Do not modify application source code to manufacture screenshot states.
- Stop the temporary server after capture and verification.

---

### Task 1: Start the Capture Environment

**Files:**
- Runtime only: `.venv` Uvicorn process
- Create directory: `docs/images/`

**Interfaces:**
- Consumes: the existing application and project `.venv`
- Produces: a reachable local game and an image destination directory

- [ ] **Step 1: Confirm the worktree is clean**

Run:

```powershell
git status --short --branch
```

Expected: no uncommitted files.

- [ ] **Step 2: Start Uvicorn**

Run:

```powershell
.venv\Scripts\python.exe -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Expected: the process remains running and the root page returns HTTP 200.

- [ ] **Step 3: Create the image directory**

Create `docs/images/` before writing screenshot assets.

### Task 2: Capture the Setup and Active Table

**Files:**
- Create: `docs/images/game-setup.png`
- Create: `docs/images/game-table.png`

**Interfaces:**
- Consumes: the live setup and game-table views
- Produces: two 1366×768 PNG assets

- [ ] **Step 1: Prepare the browser**

Open `http://127.0.0.1:8000/`, set the viewport override to 1366×768, wait for
the setup controls, and verify that the page title is `Texas Hold'em Poker`.

- [ ] **Step 2: Capture setup**

Capture the viewport after the default setup form is fully visible and save the
bytes unchanged to `docs/images/game-setup.png`.

- [ ] **Step 3: Start a short game**

Configure one AI player, 100 starting chips, fixed blinds of 25/50, and random
personality. Start the game and wait until the table and player-action controls
are visible.

- [ ] **Step 4: Capture the active table**

Capture the viewport with the real table state visible and save it unchanged to
`docs/images/game-table.png`.

### Task 3: Capture Results

**Files:**
- Create: `docs/images/game-results.png`

**Interfaces:**
- Consumes: the active short game from Task 2
- Produces: one 1366×768 results PNG

- [ ] **Step 1: Complete the game through normal controls**

Whenever the human action dock is enabled, choose `All-in`; otherwise wait for
the next concrete state transition. Continue until the results view appears.

- [ ] **Step 2: Capture results**

Capture the completed-game viewport and save it unchanged to
`docs/images/game-results.png`.

### Task 4: Add the README Gallery

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: the three PNG assets
- Produces: a GitHub-renderable `Screenshots` section

- [ ] **Step 1: Insert the section**

Between `Features` and `Quick Start`, add:

```markdown
## Screenshots

### Poker Table

![Active Texas Hold'em poker table](docs/images/game-table.png)

| Game Setup | Game Results |
| --- | --- |
| ![Texas Hold'em game setup](docs/images/game-setup.png) | ![Texas Hold'em game results](docs/images/game-results.png) |
```

### Task 5: Verify and Commit

**Files:**
- Inspect: `docs/images/game-setup.png`
- Inspect: `docs/images/game-table.png`
- Inspect: `docs/images/game-results.png`
- Test: `frontend/tests/*.test.mjs`
- Commit: README, image assets, and this plan

**Interfaces:**
- Consumes: completed screenshot gallery
- Produces: verified committed documentation assets

- [ ] **Step 1: Verify PNG metadata and visual content**

Confirm each file has the PNG signature and exact dimensions 1366×768, then
visually inspect all three images for the intended state and absence of secrets.

- [ ] **Step 2: Run frontend tests**

Run:

```powershell
node --test frontend/tests/*.test.mjs
```

Expected: all frontend tests pass.

- [ ] **Step 3: Verify README paths and Git diff**

Run `git diff --check` and confirm every README image target exists under
`docs/images/`.

- [ ] **Step 4: Stop the temporary server**

Terminate the Uvicorn process and confirm port 8000 is free.

- [ ] **Step 5: Commit**

Run:

```powershell
git add README.md docs/images/game-setup.png docs/images/game-table.png docs/images/game-results.png docs/superpowers/plans/2026-07-15-readme-game-screenshots.md
git commit -m "docs: add game screenshots to README"
```

Expected: the commit contains only the README, three PNG assets, and this plan.

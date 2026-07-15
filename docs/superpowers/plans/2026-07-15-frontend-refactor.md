# Desktop Frontend Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current three-column global-script frontend with a maintainable, table-first “Midnight Casino” desktop interface that fits in one viewport and preserves all backend contracts.

**Architecture:** Keep the app as a no-build vanilla JavaScript SPA, but convert scripts to native ES modules. Route server messages through a small store, render focused DOM regions from normalized state, and keep HTTP/WebSocket access behind service modules.

**Tech Stack:** HTML5, CSS custom properties, native ES modules, browser WebSocket/fetch/localStorage/Web Audio APIs, Node.js built-in test runner, FastAPI static hosting.

## Global Constraints

- Support desktop viewports at 1024 px and wider; mobile and tablet layouts are out of scope.
- The complete game view must fit at 1024×768, 1366×768, and 1920×1080 without a page-level scrollbar.
- Do not add a framework, bundler, runtime dependency, or backend API/WebSocket/game-rule change.
- Preserve the existing message types: `game_state`, `your_turn`, `player_action`, `ai_thinking`, `hand_result`, and `game_over`.
- Keep game state server-authoritative; persist only log collapse and sound preference.
- Sound is off by default and motion must respect `prefers-reduced-motion`.
- Run `python test_betting_and_pot.py` before final delivery.

---

### Task 1: Extract deterministic game-state and betting helpers

**Files:**
- Create: `frontend/js/game/betting.js`
- Create: `frontend/js/game/seat-layout.js`
- Create: `frontend/js/state/game-state.js`
- Create: `frontend/tests/betting.test.mjs`
- Create: `frontend/tests/seat-layout.test.mjs`
- Create: `frontend/tests/game-state.test.mjs`

**Interfaces:**
- Produces: `getBetPreset(fraction, pot, minRaise, maxRaise): number`
- Produces: `validateRaise(amount, minRaise, maxRaise): string|null`
- Produces: `getSeatPositions(count): Array<{x:number,y:number}>`
- Produces: `normalizeGameState(raw): object`
- Produces: `findHuman(state): object|null`

- [ ] **Step 1: Write failing betting tests**

```js
import test from "node:test";
import assert from "node:assert/strict";
import { getBetPreset, validateRaise } from "../js/game/betting.js";

test("getBetPreset rounds the pot fraction and clamps it", () => {
    assert.equal(getBetPreset(0.5, 480, 100, 1000), 240);
    assert.equal(getBetPreset(0.5, 100, 80, 1000), 80);
    assert.equal(getBetPreset(1, 2000, 80, 900), 900);
});

test("validateRaise explains invalid targets", () => {
    assert.equal(validateRaise(79, 80, 900), "Minimum raise is 80.");
    assert.equal(validateRaise(901, 80, 900), "Maximum raise is 900.");
    assert.equal(validateRaise(320, 80, 900), null);
});
```

- [ ] **Step 2: Run the betting tests and confirm the import fails**

Run: `node --test frontend/tests/betting.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND` for `game/betting.js`.

- [ ] **Step 3: Implement betting helpers**

```js
export function getBetPreset(fraction, pot, minRaise, maxRaise) {
    const target = Math.round(Number(pot || 0) * fraction);
    return Math.min(maxRaise, Math.max(minRaise, target));
}

export function validateRaise(amount, minRaise, maxRaise) {
    if (!Number.isFinite(amount)) return "Enter a valid raise amount.";
    if (amount < minRaise) return `Minimum raise is ${minRaise}.`;
    if (amount > maxRaise) return `Maximum raise is ${maxRaise}.`;
    return null;
}
```

- [ ] **Step 4: Add seat-layout and state-normalization tests**

```js
// frontend/tests/seat-layout.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { getSeatPositions } from "../js/game/seat-layout.js";

test("the human seat remains centered at the bottom", () => {
    for (const count of [2, 6, 9]) {
        const positions = getSeatPositions(count);
        assert.equal(positions.length, count);
        assert.deepEqual(positions[0], { x: 50, y: 86 });
    }
});

// frontend/tests/game-state.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { findHuman, normalizeGameState } from "../js/state/game-state.js";

test("normalizeGameState supplies render-safe defaults", () => {
    const state = normalizeGameState({ hand_number: 3, players: [{ id: "human", is_human: true }] });
    assert.equal(state.hand_number, 3);
    assert.deepEqual(state.community_cards, []);
    assert.deepEqual(state.action_history, []);
    assert.equal(findHuman(state).id, "human");
});
```

- [ ] **Step 5: Implement the seat and state modules**

Move the existing 2–9 player coordinates from `frontend/js/table.js` into `seat-layout.js`, changing each human coordinate to `{ x: 50, y: 86 }`. Export this complete public function after the map:

```js
export function getSeatPositions(count) {
    if (PLAYER_POSITIONS[count]) return PLAYER_POSITIONS[count].map((position) => ({ ...position }));
    if (count < 2) return [];
    const positions = [{ x: 50, y: 86 }];
    for (let index = 0; index < count - 1; index += 1) {
        const fraction = (index + 1) / count;
        positions.push({
            x: Math.round(5 + fraction * 90),
            y: Math.round(14 + Math.sin(fraction * Math.PI) * 24),
        });
    }
    return positions;
}
```

```js
// frontend/js/state/game-state.js
export function normalizeGameState(raw = {}) {
    return {
        ...raw,
        players: Array.isArray(raw.players) ? raw.players : [],
        community_cards: Array.isArray(raw.community_cards) ? raw.community_cards : [],
        action_history: Array.isArray(raw.action_history) ? raw.action_history : [],
        pots: Array.isArray(raw.pots) ? raw.pots : [],
        pot: Number(raw.pot || raw.total_pot || 0),
        hand_number: Number(raw.hand_number || 0),
    };
}

export function findHuman(state) {
    return state.players.find((player) => player.is_human) || null;
}
```

- [ ] **Step 6: Run all pure-function tests**

Run: `node --test frontend/tests/*.test.mjs`

Expected: 4 tests PASS with 0 failures.

- [ ] **Step 7: Commit the helpers**

```powershell
git add frontend/js/game/betting.js frontend/js/game/seat-layout.js frontend/js/state/game-state.js frontend/tests
git commit -m "refactor: extract frontend game helpers"
```

---

### Task 2: Add preferences, application store, and transport services

**Files:**
- Create: `frontend/js/state/preferences.js`
- Create: `frontend/js/state/store.js`
- Create: `frontend/js/services/api.js`
- Create: `frontend/js/services/websocket.js`
- Create: `frontend/tests/preferences.test.mjs`
- Create: `frontend/tests/store.test.mjs`

**Interfaces:**
- Consumes: `normalizeGameState(raw)` from Task 1.
- Produces: `loadPreferences(storage)`, `savePreferences(storage, preferences)`.
- Produces: `createStore(): {getState, update, subscribe, reset}`.
- Produces: `startGame(config): Promise<{game_id:string}>`.
- Produces: `createWebSocketClient(options): {connect, on, send, close, isConnected}`.

- [ ] **Step 1: Write failing preferences and store tests**

```js
// frontend/tests/preferences.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { loadPreferences, savePreferences } from "../js/state/preferences.js";

test("preferences default to sound off and expanded log", () => {
    const storage = { getItem: () => null, setItem() {} };
    assert.deepEqual(loadPreferences(storage), { soundEnabled: false, logCollapsed: false });
});

test("preferences round-trip through injected storage", () => {
    const values = new Map();
    const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
    savePreferences(storage, { soundEnabled: true, logCollapsed: true });
    assert.deepEqual(loadPreferences(storage), { soundEnabled: true, logCollapsed: true });
});

// frontend/tests/store.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createStore } from "../js/state/store.js";

test("store publishes immutable top-level updates", () => {
    const store = createStore();
    let published;
    store.subscribe((state) => { published = state; });
    store.update({ connection: "connected", pendingAction: true });
    assert.equal(published.connection, "connected");
    assert.equal(published.pendingAction, true);
});
```

- [ ] **Step 2: Run tests and confirm missing-module failures**

Run: `node --test frontend/tests/preferences.test.mjs frontend/tests/store.test.mjs`

Expected: FAIL with `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement preferences and store**

```js
// frontend/js/state/preferences.js
const KEY = "texas-poker-ui";
const DEFAULTS = Object.freeze({ soundEnabled: false, logCollapsed: false });

export function loadPreferences(storage = window.localStorage) {
    try { return { ...DEFAULTS, ...JSON.parse(storage.getItem(KEY) || "{}") }; }
    catch { return { ...DEFAULTS }; }
}

export function savePreferences(storage = window.localStorage, preferences) {
    storage.setItem(KEY, JSON.stringify({
        soundEnabled: Boolean(preferences.soundEnabled),
        logCollapsed: Boolean(preferences.logCollapsed),
    }));
}
```

```js
// frontend/js/state/store.js
const INITIAL = Object.freeze({
    game: null, turn: null, connection: "disconnected", pendingAction: false,
    error: null, thinkingPlayer: null,
});

export function createStore() {
    let state = { ...INITIAL };
    const listeners = new Set();
    return {
        getState: () => state,
        update(patch) { state = Object.freeze({ ...state, ...patch }); listeners.forEach((fn) => fn(state)); },
        subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
        reset() { state = { ...INITIAL }; listeners.forEach((fn) => fn(state)); },
    };
}
```

- [ ] **Step 4: Implement the HTTP and WebSocket services**

```js
// frontend/js/services/api.js
export async function startGame(config, baseUrl = window.location.origin) {
    const response = await fetch(`${baseUrl}/api/game/start`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.detail || `Server returned ${response.status}`);
    return body;
}

export function replayUrl(id, baseUrl = window.location.origin) {
    return `${baseUrl}/api/replay/${encodeURIComponent(id)}`;
}
```

Convert the existing `WSClient` prototype in `frontend/js/ws.js` into `frontend/js/services/websocket.js`. Preserve its retry limit of 5 and 2000 ms delay, and add connection notifications:

```js
export function createWebSocketClient({ WebSocketImpl = WebSocket, maxRetries = 5, retryDelay = 2000 } = {}) {
    const handlers = new Map();
    let socket = null, url = "", manualClose = false, attempts = 0;
    const emit = (type, payload = {}) => (handlers.get(type) || []).forEach((fn) => fn(payload));
    const on = (type, fn) => { handlers.set(type, [...(handlers.get(type) || []), fn]); };
    const connect = (nextUrl) => new Promise((resolve, reject) => {
        url = nextUrl; manualClose = false; emit("connection", { status: attempts ? "reconnecting" : "connecting" });
        try { socket = new WebSocketImpl(url); } catch (error) { reject(error); return; }
        socket.onopen = () => { attempts = 0; emit("connection", { status: "connected" }); resolve(); };
        socket.onmessage = (event) => { try { const message = JSON.parse(event.data); emit(message.type || "_unknown", message); } catch { emit("protocol_error", { message: "Invalid server message." }); } };
        socket.onerror = () => emit("connection", { status: "error" });
        socket.onclose = () => {
            emit("connection", { status: "disconnected" });
            if (!manualClose && attempts < maxRetries) { attempts += 1; setTimeout(() => connect(url).catch(() => {}), retryDelay); }
        };
    });
    return {
        connect, on,
        send(message) { if (!socket || socket.readyState !== WebSocketImpl.OPEN) return false; socket.send(JSON.stringify(message)); return true; },
        close() { manualClose = true; socket?.close(); socket = null; },
        isConnected: () => socket?.readyState === WebSocketImpl.OPEN,
    };
}
```

- [ ] **Step 5: Run state tests and backend tests**

Run: `node --test frontend/tests/*.test.mjs`

Expected: 7 tests PASS with 0 failures.

Run: `python test_betting_and_pot.py`

Expected: script exits 0 and reports all betting/pot scenarios passed.

- [ ] **Step 6: Commit services and state**

```powershell
git add frontend/js/services frontend/js/state frontend/tests
git commit -m "refactor: add frontend state and transport modules"
```

---

### Task 3: Build the single-viewport shell and design system

**Files:**
- Create: `frontend/design-preview.html`
- Create: `frontend/css/tokens.css`
- Create: `frontend/css/base.css`
- Create: `frontend/css/setup.css`
- Create: `frontend/css/game.css`
- Create: `frontend/css/results.css`

**Interfaces:**
- Produces stable DOM regions: `#connection-status`, `#error-banner`, `#game-stage`, `#player-spots`, `#hand-panel`, `#action-log-panel`, `#action-bar`, and `#live-announcer`.

- [ ] **Step 1: Create a standalone design preview**

Create `frontend/design-preview.html` with `<!DOCTYPE html>`, UTF-8 and viewport metadata, then use this exact stylesheet order in `<head>`:

```html
<link rel="stylesheet" href="/static/css/tokens.css">
<link rel="stylesheet" href="/static/css/base.css">
<link rel="stylesheet" href="/static/css/setup.css">
<link rel="stylesheet" href="/static/css/game.css">
<link rel="stylesheet" href="/static/css/results.css">
```

Do not load application scripts in this preview; it exists to verify the shell independently while module migration is in progress.

- [ ] **Step 2: Replace the game-view shell**

Use this semantic structure as the preview body and as the exact game-view markup to move into `index.html` in Task 8:

```html
<section id="game-view" class="view game-view" hidden>
  <header class="game-topbar">
    <div class="brand"><span class="brand-mark" aria-hidden="true">♠</span><span>Texas Hold'em</span></div>
    <div class="game-meta"><span>Hand #<b id="hand-number">0</b></span><span id="phase-display">Waiting</span><span id="blinds-display">0 / 0</span></div>
    <div class="game-tools"><span id="connection-status" role="status">Disconnected</span><button id="btn-sound" type="button" aria-pressed="false">Sound off</button></div>
  </header>
  <div id="error-banner" class="error-banner" role="alert" hidden><span id="error-message"></span><button id="btn-dismiss-error" type="button" aria-label="Dismiss error">×</button></div>
  <main id="game-stage" class="game-stage">
    <section id="poker-table" class="poker-table" aria-label="Poker table"><div class="table-felt"><div id="pot-label" class="pot-label">Pot 0</div><div id="community-cards" class="community-cards"></div><div id="player-spots"></div></div></section>
    <aside id="hand-panel" class="floating-panel hand-panel" aria-label="Your hand"></aside>
    <aside id="action-log-panel" class="floating-panel action-log-panel"><header><h2>Action log</h2><button id="btn-toggle-log" type="button" aria-expanded="true">Collapse</button></header><div id="action-log" aria-live="polite"></div></aside>
    <div id="thinking-indicator" class="thinking-indicator" hidden><span id="thinking-text"></span></div>
  </main>
  <footer id="action-bar" class="action-dock" aria-label="Poker actions"></footer>
  <div id="live-announcer" class="sr-only" aria-live="assertive"></div>
</section>
```

- [ ] **Step 3: Add design tokens and base rules**

```css
/* frontend/css/tokens.css */
:root { --bg:#020d0b; --surface:#071b17; --felt:#10513c; --felt-dark:#092f25; --wood:#3a2116; --gold:#caa660; --gold-soft:#dcc080; --text:#f1e6cc; --muted:#98afa7; --danger:#d89a91; --line:rgba(202,166,96,.24); --radius:12px; --shadow:0 18px 44px rgba(0,0,0,.42); --fast:140ms; }
```

```css
/* frontend/css/base.css */
*{box-sizing:border-box}html,body,#app{width:100%;min-height:100%;margin:0}body{color:var(--text);background:var(--bg);font-family:Inter,"Segoe UI",sans-serif}button,input{font:inherit}.view[hidden]{display:none!important}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}button:focus-visible,input:focus-visible{outline:2px solid var(--gold);outline-offset:3px}@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;animation-duration:.01ms!important;transition-duration:.01ms!important}}
```

- [ ] **Step 4: Implement the viewport contract in game.css**

Start `frontend/css/game.css` with these non-negotiable layout rules, then port component styling from the approved mockup:

```css
.game-view{height:100vh;min-width:1024px;overflow:hidden;display:grid;grid-template-rows:54px minmax(0,1fr) 76px;background:radial-gradient(circle at 50% 42%,#164d3b 0,var(--surface) 48%,var(--bg) 82%)}
.game-topbar{display:flex;align-items:center;justify-content:space-between;padding:0 22px;border-bottom:1px solid var(--line)}
.game-stage{position:relative;min-height:0;overflow:hidden}
.poker-table{position:absolute;left:50%;top:48%;transform:translate(-50%,-50%);width:min(66vw,calc((100vh - 176px)*1.62));aspect-ratio:1.92/1;border:clamp(8px,1.2vw,16px) solid var(--wood);border-radius:50%;background:radial-gradient(ellipse,var(--felt),var(--felt-dark));box-shadow:0 0 0 3px #ad8448,0 0 0 7px #24140e,var(--shadow)}
.action-dock{display:flex;align-items:center;justify-content:center;gap:8px;padding:10px 18px;border-top:1px solid var(--line);background:rgba(2,12,10,.96)}
body:has(.game-view:not([hidden])){overflow:hidden}
```

- [ ] **Step 5: Start the app and inspect the empty shell**

Run: `python -m uvicorn server.main:app --host 127.0.0.1 --port 8000`

Expected: `http://localhost:8000/static/design-preview.html` loads without missing resources, fits within the viewport, and has no duplicate IDs.

- [ ] **Step 6: Commit the shell**

```powershell
git add frontend/design-preview.html frontend/css/tokens.css frontend/css/base.css frontend/css/setup.css frontend/css/game.css frontend/css/results.css
git commit -m "feat: add single-viewport poker shell"
```

---

### Task 4: Convert setup and results views to ES modules

**Files:**
- Modify: `frontend/js/setup.js`
- Modify: `frontend/js/results.js`
- Modify: `frontend/css/setup.css`
- Modify: `frontend/css/results.css`

**Interfaces:**
- Produces: `createSetupView(root): {onStart,setBusy,showError,clearError,reset}`.
- Produces: `createResultsView(root): {onPlayAgain,onViewReplay,render}`.

- [ ] **Step 1: Export setup view factory**

Replace the IIFE/global return with an exported factory. Preserve the existing configuration shape and validation, and use this public boundary:

```js
export function createSetupView(root = document) {
    let onStart = () => {};
    const button = root.querySelector("#btn-start-game");
    const error = root.querySelector("#setup-error");
    button.addEventListener("click", () => {
        const config = readConfig(root);
        const message = validateConfig(config);
        if (message) { showError(message); return; }
        clearError(); onStart(config);
    });
    const showError = (message) => { error.textContent = message; error.hidden = false; };
    const clearError = () => { error.textContent = ""; error.hidden = true; };
    return {
        onStart(fn) { onStart = fn; }, showError, clearError,
        setBusy(busy) { button.disabled = busy; button.querySelector(".btn-label").textContent = busy ? "Starting…" : "Start game"; },
        reset() { clearError(); },
    };
}
```

Keep `readConfig(root)` and `validateConfig(config)` as private named functions in the same file; convert all `var` declarations to `const`/`let` and all DOM lookups to `root.querySelector`.

- [ ] **Step 2: Export results view factory**

```js
export function createResultsView(root = document) {
    const rankings = root.querySelector("#rankings-list");
    const stats = root.querySelector("#stats-container");
    const totalHands = root.querySelector("#total-hands");
    let replayId = null, playAgain = () => {}, viewReplay = () => {};
    root.querySelector("#btn-play-again").addEventListener("click", () => playAgain());
    root.querySelector("#btn-view-replay").addEventListener("click", () => viewReplay(replayId));
    return {
        onPlayAgain(fn) { playAgain = fn; }, onViewReplay(fn) { viewReplay = fn; },
        render(message, handCount) {
            replayId = message.replay_id || null; totalHands.textContent = String(handCount);
            renderRankings(rankings, message.rankings || []); renderStats(stats, message.stats || {}, handCount);
        },
    };
}
```

Move the current `_renderRankings`, `_renderStats`, and `_fmtChips` logic into private module functions without changing server field names.

- [ ] **Step 3: Style setup and results with the shared visual system**

Use centered panels, `var(--surface)`, `var(--gold)`, `var(--line)`, and visible focus styles. Keep both views vertically scrollable if content exceeds 768 px; the no-scroll requirement applies to the active game view only.

- [ ] **Step 4: Verify modules parse**

Run: `node --check frontend/js/setup.js`

Run: `node --check frontend/js/results.js`

Expected: both commands exit 0 without syntax errors.

- [ ] **Step 5: Commit view modules**

```powershell
git add frontend/js/setup.js frontend/js/results.js frontend/css/setup.css frontend/css/results.css
git commit -m "refactor: modularize setup and results views"
```

---

### Task 5: Split card, player, and table rendering

**Files:**
- Create: `frontend/js/game/cards.js`
- Create: `frontend/js/game/players.js`
- Create: `frontend/js/game/table.js`
- Modify: `frontend/css/game.css`

**Interfaces:**
- Consumes: `getSeatPositions(count)` and `findHuman(state)` from Task 1.
- Produces: `renderCards(container, cards, {placeholders,faceDown})`.
- Produces: `renderPlayers(container, state)`.
- Produces: `createTableView(root): {render,showThinking,hideThinking}`.

- [ ] **Step 1: Implement card rendering as a focused module**

```js
const SUITS = { HEARTS: "♥", DIAMONDS: "♦", CLUBS: "♣", SPADES: "♠" };
export function renderCards(container, cards = [], { placeholders = 0, faceDown = false } = {}) {
    container.replaceChildren();
    for (const card of cards) {
        const element = document.createElement("div"); element.className = `card ${faceDown ? "face-down" : ["HEARTS","DIAMONDS"].includes(card.suit) ? "suit-red" : "suit-black"}`;
        if (!faceDown) element.innerHTML = `<span class="card-rank"></span><span class="card-suit"></span>`;
        if (!faceDown) { element.children[0].textContent = card.rank; element.children[1].textContent = SUITS[card.suit] || card.suit; }
        container.appendChild(element);
    }
    for (let index = cards.length; index < placeholders; index += 1) { const slot = document.createElement("div"); slot.className = "card-slot empty"; container.appendChild(slot); }
}
```

- [ ] **Step 2: Implement player rendering**

`renderPlayers` must use `getSeatPositions(players.length)`, set `data-player-id`, and append visible text for name, chips, dealer, active turn, and the last action. Use `textContent` for server-supplied data. Export only:

```js
export function renderPlayers(container, state) {
    const positions = getSeatPositions(state.players.length); container.replaceChildren();
    const lastActions = new Map((state.action_history || []).map((action) => [action.player_id, action]));
    state.players.forEach((player, index) => container.appendChild(createPlayerSeat(player, positions[index], {
        dealer: index === state.dealer_index, active: index === state.current_player_index, action: lastActions.get(player.id),
    })));
}
```

- [ ] **Step 3: Implement table orchestration**

```js
import { findHuman } from "../state/game-state.js";
import { renderCards } from "./cards.js";
import { renderPlayers } from "./players.js";

export function createTableView(root = document) {
    const community = root.querySelector("#community-cards"), players = root.querySelector("#player-spots");
    const hand = root.querySelector("#hand-panel"), pot = root.querySelector("#pot-label");
    const thinking = root.querySelector("#thinking-indicator"), thinkingText = root.querySelector("#thinking-text");
    return {
        render(state) {
            renderCards(community, state.community_cards, { placeholders: 5 }); renderPlayers(players, state);
            const human = findHuman(state); pot.textContent = `Pot ${Number(state.pot || 0).toLocaleString()}`;
            hand.replaceChildren();
            const title = document.createElement("h2"); title.textContent = "Your hand"; hand.appendChild(title);
            const cards = document.createElement("div"); cards.className = "hole-cards"; hand.appendChild(cards);
            renderCards(cards, human?.hole_cards || [], { placeholders: 2 });
        },
        showThinking(name) { thinkingText.textContent = `${name || "AI"} is thinking…`; thinking.hidden = false; },
        hideThinking() { thinking.hidden = true; },
    };
}
```

- [ ] **Step 4: Complete table component styles**

Port seat coordinates, card faces, active-turn ring, folded opacity, dealer marker, community-card row, hand panel, and thinking indicator from the approved mockup into `game.css`. Keep dimensions based on `clamp()`, `%`, `vw`, and `vh`; do not introduce fixed stage heights.

- [ ] **Step 5: Parse-check and commit**

Run: `node --check frontend/js/game/cards.js`

Run: `node --check frontend/js/game/players.js`

Run: `node --check frontend/js/game/table.js`

Expected: exit 0.

```powershell
git add frontend/js/game frontend/css/game.css
git commit -m "refactor: split poker table rendering"
```

---

### Task 6: Build action controls, presets, preferences, and sound

**Files:**
- Create: `frontend/js/game/actions.js`
- Create: `frontend/js/services/sound.js`
- Modify: `frontend/index.html`
- Modify: `frontend/css/game.css`

**Interfaces:**
- Consumes: `getBetPreset`, `validateRaise`, `findHuman`, `loadPreferences`, `savePreferences`.
- Produces: `createActionControls(root): {onSubmit,setTurn,setPending,disable}`.
- Produces: `createSoundService(): {setEnabled,isEnabled,play}`.

- [ ] **Step 1: Add complete action-dock markup**

Inside `#action-bar`, add fold/check/call/all-in buttons, number input `#raise-amount`, error `#raise-error`, preset buttons with `data-fraction="0.5"`, `"0.75"`, and `"1"`, and `#btn-raise`. Preserve F/C/A/R/I shortcuts in visible `<kbd>` elements.

- [ ] **Step 2: Implement action controls**

```js
import { getBetPreset, validateRaise } from "./betting.js";
import { findHuman } from "../state/game-state.js";
export function createActionControls(root = document) {
    const buttons = Object.fromEntries(["FOLD","CHECK","CALL","RAISE","ALL_IN"].map((action) => [action, root.querySelector(`[data-action="${action}"]`)]));
    const input = root.querySelector("#raise-amount"), error = root.querySelector("#raise-error");
    let turn = null, pot = 0, humanChips = 0, submit = () => {}, pending = false;
    const disable = () => { Object.values(buttons).forEach((button) => { button.disabled = true; }); input.disabled = true; };
    const act = (action) => {
        if (pending || !turn?.valid_actions?.[action]) return;
        const amount = action === "RAISE" ? Number(input.value) : action === "CALL" ? Number(turn.call_amount || 0) : action === "ALL_IN" ? humanChips : 0;
        const message = action === "RAISE" ? validateRaise(amount, turn.min_raise, turn.max_raise) : null;
        if (message) { error.textContent = message; error.hidden = false; return; }
        error.hidden = true; pending = true; disable(); submit(action, amount);
    };
    Object.entries(buttons).forEach(([action, button]) => button.addEventListener("click", () => act(action)));
    root.querySelectorAll("[data-fraction]").forEach((button) => button.addEventListener("click", () => { input.value = String(getBetPreset(Number(button.dataset.fraction), pot, turn.min_raise, turn.max_raise)); }));
    document.addEventListener("keydown", (event) => {
        if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
        const action = ({ F:"FOLD", C:"CHECK", A:"CALL", R:"RAISE", I:"ALL_IN" })[event.key.toUpperCase()];
        if (action && !buttons[action].disabled) { event.preventDefault(); buttons[action].click(); }
    });
    return {
        onSubmit(fn) { submit = fn; }, disable,
        setPending(value) { pending = value; if (value) disable(); },
        setTurn(nextTurn, state) { turn = nextTurn; pot = Number(state?.pot || 0); humanChips = Number(findHuman(state)?.chips || 0); pending = false; Object.entries(buttons).forEach(([action, button]) => { button.disabled = !turn.valid_actions?.[action]; }); input.disabled = !turn.valid_actions?.RAISE; input.value = String(turn.min_raise || 0); },
    };
}
```

- [ ] **Step 3: Implement sound with no binary assets**

```js
export function createSoundService(AudioContextImpl = window.AudioContext || window.webkitAudioContext) {
    let enabled = false;
    return {
        setEnabled(value) { enabled = Boolean(value); }, isEnabled: () => enabled,
        play(kind) {
            if (!enabled || !AudioContextImpl) return;
            const context = new AudioContextImpl(), oscillator = context.createOscillator(), gain = context.createGain();
            oscillator.frequency.value = kind === "turn" ? 660 : 440; gain.gain.setValueAtTime(0.04, context.currentTime); gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.12);
            oscillator.connect(gain).connect(context.destination); oscillator.start(); oscillator.stop(context.currentTime + 0.12);
        },
    };
}
```

- [ ] **Step 4: Wire sound/log preferences in the game view**

Load preferences once, set `aria-pressed` and button text on `#btn-sound`, save on each toggle, and toggle `.is-collapsed` plus `aria-expanded` on `#action-log-panel`. Do not persist any game fields.

- [ ] **Step 5: Verify helpers and keyboard behavior**

Run: `node --test frontend/tests/*.test.mjs`

Expected: all tests PASS.

Manually verify: F/C/A/R/I trigger only enabled actions; typing in `#raise-amount` does not trigger shortcuts; rapid double-click sends once.

- [ ] **Step 6: Commit actions and preferences UI**

```powershell
git add frontend/index.html frontend/js/game/actions.js frontend/js/services/sound.js frontend/css/game.css
git commit -m "feat: add desktop poker action dock"
```

---

### Task 7: Add action log, connection feedback, and accessible errors

**Files:**
- Create: `frontend/js/game/action-log.js`
- Create: `frontend/js/game/status.js`
- Modify: `frontend/css/game.css`

**Interfaces:**
- Produces: `createActionLog(root): {append,clear,setCollapsed}`.
- Produces: `createStatusView(root): {setConnection,showError,clearError,announce}`.

- [ ] **Step 1: Implement safe action-log rendering**

```js
export function createActionLog(root = document) {
    const list = root.querySelector("#action-log"), panel = root.querySelector("#action-log-panel");
    const append = (message) => {
        const entry = document.createElement("p"); entry.className = `log-entry action-${String(message.action || "system").toLowerCase()}`;
        if (message.type === "player_action") entry.textContent = `${message.player_name || message.player_id} ${message.action.toLowerCase()}${message.amount ? ` ${Number(message.amount).toLocaleString()}` : ""}`;
        else if (message.type === "hand_result") entry.textContent = `Winner: ${(message.winners || []).map((winner) => winner.player_name || winner.player_id).join(", ")}`;
        else entry.textContent = message.message || "Game update";
        list.appendChild(entry); while (list.children.length > 100) list.firstElementChild.remove(); list.scrollTop = list.scrollHeight;
    };
    return { append, clear() { list.replaceChildren(); append({ message: "Waiting for first hand…" }); }, setCollapsed(value) { panel.classList.toggle("is-collapsed", value); } };
}
```

- [ ] **Step 2: Implement status/error feedback**

```js
export function createStatusView(root = document) {
    const connection = root.querySelector("#connection-status"), banner = root.querySelector("#error-banner");
    const message = root.querySelector("#error-message"), announcer = root.querySelector("#live-announcer");
    root.querySelector("#btn-dismiss-error").addEventListener("click", () => { banner.hidden = true; });
    return {
        setConnection(status) { connection.dataset.status = status; connection.textContent = ({ connected:"Connected",connecting:"Connecting…",reconnecting:"Reconnecting…",disconnected:"Disconnected",error:"Connection error" })[status] || status; },
        showError(text) { message.textContent = text; banner.hidden = false; }, clearError() { message.textContent = ""; banner.hidden = true; },
        announce(text) { announcer.textContent = ""; requestAnimationFrame(() => { announcer.textContent = text; }); },
    };
}
```

- [ ] **Step 3: Add connection and collapsed-log styles**

Use text plus color for every status. `.action-log-panel.is-collapsed #action-log{display:none}` must leave the panel header and expand button visible. Error banners must overlay below the top bar without increasing the three-row game grid height.

- [ ] **Step 4: Parse-check and commit**

Run: `node --check frontend/js/game/action-log.js`

Run: `node --check frontend/js/game/status.js`

Expected: exit 0.

```powershell
git add frontend/js/game/action-log.js frontend/js/game/status.js frontend/css/game.css
git commit -m "feat: add game status and action feedback"
```

---

### Task 8: Integrate the modules in the application controller

**Files:**
- Modify: `frontend/js/app.js`
- Delete: `frontend/js/ws.js`
- Delete: `frontend/js/table.js`
- Modify: `frontend/index.html`
- Delete: `frontend/design-preview.html`

**Interfaces:**
- Consumes every factory from Tasks 2, 4, 5, 6, and 7.
- Produces the single `type="module"` application entry point.

- [ ] **Step 1: Promote the preview shell into the SPA**

Replace the legacy `#game-view` in `frontend/index.html` with the exact game-view markup from Task 3. Add the five stylesheet links from Task 3 after the legacy `style.css` link, change the setup button contents to `<span class="btn-icon" aria-hidden="true">♠</span><span class="btn-label">Start game</span>`, and replace all five classic scripts with:

```html
<script type="module" src="/static/js/app.js"></script>
```

Delete `frontend/design-preview.html` after its markup is moved.

- [ ] **Step 2: Replace globals with imports and explicit view switching**

Replace the top of `app.js` with the complete import and initialization block below. Use `element.hidden` for view switching:

```js
import { startGame, replayUrl } from "./services/api.js";
import { createWebSocketClient } from "./services/websocket.js";
import { createSoundService } from "./services/sound.js";
import { createStore } from "./state/store.js";
import { normalizeGameState } from "./state/game-state.js";
import { loadPreferences, savePreferences } from "./state/preferences.js";
import { createSetupView } from "./setup.js";
import { createResultsView } from "./results.js";
import { createTableView } from "./game/table.js";
import { createActionControls } from "./game/actions.js";
import { createActionLog } from "./game/action-log.js";
import { createStatusView } from "./game/status.js";

const store = createStore();
const socket = createWebSocketClient();
const sound = createSoundService();
const setup = createSetupView();
const results = createResultsView();
const table = createTableView();
const actions = createActionControls();
const log = createActionLog();
const status = createStatusView();
let preferences = loadPreferences();
let currentGameId = null, currentReplayId = null, maxHand = 0;

function showView(name) {
    for (const viewName of ["setup", "game", "results"]) document.querySelector(`#${viewName}-view`).hidden = viewName !== name;
}

sound.setEnabled(preferences.soundEnabled);
const soundButton = document.querySelector("#btn-sound");
const updateSoundButton = () => { soundButton.setAttribute("aria-pressed", String(preferences.soundEnabled)); soundButton.textContent = preferences.soundEnabled ? "Sound on" : "Sound off"; };
soundButton.addEventListener("click", () => { preferences = { ...preferences, soundEnabled: !preferences.soundEnabled }; sound.setEnabled(preferences.soundEnabled); savePreferences(window.localStorage, preferences); updateSoundButton(); });
const logButton = document.querySelector("#btn-toggle-log");
const updateLog = () => { log.setCollapsed(preferences.logCollapsed); logButton.setAttribute("aria-expanded", String(!preferences.logCollapsed)); logButton.textContent = preferences.logCollapsed ? "Expand" : "Collapse"; };
logButton.addEventListener("click", () => { preferences = { ...preferences, logCollapsed: !preferences.logCollapsed }; savePreferences(window.localStorage, preferences); updateLog(); });
updateSoundButton(); updateLog(); showView("setup");
```

- [ ] **Step 3: Implement start and action flows**

```js
setup.onStart(async (config) => {
    setup.setBusy(true); setup.clearError();
    try {
        const { game_id: gameId } = await startGame(config); currentGameId = gameId;
        await socket.connect(`${location.origin.replace(/^http/, "ws")}/ws/${gameId}`);
        log.clear(); actions.disable(); showView("game");
    } catch (error) { setup.showError(`Failed to start game: ${error.message}`); }
    finally { setup.setBusy(false); }
});

actions.onSubmit((action, amount) => {
    actions.setPending(true);
    if (!socket.send({ type: "player_action", action, amount })) {
        actions.setPending(false); status.showError("Action was not sent because the game is disconnected.");
    }
});
```

- [ ] **Step 4: Route every existing WebSocket message**

Use these effects without changing payload names:

```js
socket.on("connection", ({ status: value }) => { store.update({ connection: value }); status.setConnection(value); if (value !== "connected") actions.disable(); });
socket.on("game_state", (message) => { const game = normalizeGameState(message.state); store.update({ game, pendingAction:false }); table.render(game); actions.setPending(false); maxHand = Math.max(maxHand, game.hand_number); });
socket.on("your_turn", (message) => { store.update({ turn:message, pendingAction:false }); actions.setTurn(message, store.getState().game); table.hideThinking(); log.append({ message:"Your turn! Choose an action." }); status.announce("Your turn"); sound.play("turn"); });
socket.on("player_action", (message) => { log.append(message); table.hideThinking(); sound.play("action"); });
socket.on("ai_thinking", (message) => table.showThinking(message.player_name));
socket.on("hand_result", (message) => { log.append(message); table.hideThinking(); actions.disable(); });
socket.on("game_over", (message) => { actions.disable(); table.hideThinking(); currentReplayId = message.replay_id || null; setTimeout(() => { results.render(message,maxHand); showView("results"); },1500); });
socket.on("protocol_error", ({ message }) => status.showError(message));
```

- [ ] **Step 5: Wire play-again and replay**

Play again must close the socket, reset the store, clear log/errors, and show setup. Replay must call `window.open(replayUrl(id), "_blank", "noopener")` only when an ID exists; otherwise show the shared error banner instead of `alert()`.

- [ ] **Step 6: Remove legacy scripts and stale IDs**

Delete `frontend/js/ws.js` and `frontend/js/table.js`. Confirm `index.html` contains only one module script and no inline `onclick`. Search:

Run: `rg -n "SetupView|TableView|ResultsView|WSClient|onclick=|<script src=" frontend`

Expected: no matches.

- [ ] **Step 7: Parse and regression-test**

Run: `node --check frontend/js/app.js`

Run: `node --test frontend/tests/*.test.mjs`

Run: `python test_betting_and_pot.py`

Expected: all commands exit 0.

- [ ] **Step 8: Commit integration**

```powershell
git add frontend/index.html frontend/design-preview.html frontend/js
git commit -m "refactor: integrate modular poker frontend"
```

---

### Task 9: Perform desktop viewport, reconnect, and accessibility acceptance

**Files:**
- Modify if findings require: `frontend/css/game.css`
- Modify if findings require: `frontend/js/app.js`
- Modify if findings require: `frontend/js/game/actions.js`
- Delete: `frontend/css/style.css`
- Create: `docs/frontend-smoke-test.md`

**Interfaces:**
- Consumes the integrated application from Task 8.
- Produces recorded acceptance evidence and removal of the legacy stylesheet.

- [ ] **Step 1: Run all automated checks**

Run: `node --test frontend/tests/*.test.mjs`

Run: `python test_betting_and_pot.py`

Run: `git diff --check`

Expected: JavaScript and Python checks pass; Git reports no whitespace errors.

- [ ] **Step 2: Verify the three target viewports**

At 1024×768, 1366×768, and 1920×1080, start a game and evaluate in DevTools:

```js
({ width: innerWidth, height: innerHeight, horizontal: document.documentElement.scrollWidth > innerWidth, vertical: document.documentElement.scrollHeight > innerHeight, dock: document.querySelector("#action-bar").getBoundingClientRect() })
```

Expected: `horizontal` and `vertical` are `false`; `dock.bottom <= innerHeight`; all player seats, community cards, and enabled actions are visible.

- [ ] **Step 3: Complete interaction and failure smoke tests**

Verify setup validation, game start, check, call, each bet preset, valid raise, invalid raise message, fold, all-in, results, play again, replay, log collapse persistence, sound default-off/persistence, keyboard actions, and reduced motion. Stop the server connection during a turn and confirm “Reconnecting…” appears and all action controls stay disabled until a fresh `game_state` arrives.

- [ ] **Step 4: Record the acceptance evidence**

Create `docs/frontend-smoke-test.md` with this complete structure and fill each result with `PASS` plus the tested browser/version:

```markdown
# Frontend Smoke Test

- Automated: `node --test frontend/tests/*.test.mjs` — PASS
- Backend regression: `python test_betting_and_pot.py` — PASS
- 1024×768 single viewport — PASS
- 1366×768 single viewport — PASS
- 1920×1080 single viewport — PASS
- Setup/game/actions/results flow — PASS
- Reconnect disables actions — PASS
- Keyboard, focus, aria-live, reduced motion — PASS
- Log and sound preferences — PASS
```

- [ ] **Step 5: Remove the legacy stylesheet and check references**

Delete `frontend/css/style.css` and remove its `<link>` from `frontend/index.html` only after every smoke check passes.

Run: `rg -n "style\.css|frontend/js/(ws|table)\.js" . --glob '!docs/superpowers/**'`

Expected: no matches.

- [ ] **Step 6: Commit acceptance cleanup**

```powershell
git add frontend docs/frontend-smoke-test.md
git commit -m "test: verify desktop frontend refactor"
```

- [ ] **Step 7: Final branch review**

Run: `git status --short`

Expected: only the pre-existing untracked `AGENTS.md` may remain.

Run: `git log --oneline --max-count=10`

Expected: the frontend branch contains the design, plan, and focused implementation commits in task order.

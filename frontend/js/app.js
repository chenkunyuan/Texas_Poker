import { startGame, replayUrl } from "./services/api.js";
import { createWebSocketClient } from "./services/websocket.js";
import { createSoundService } from "./services/sound.js";
import { createStore } from "./state/store.js";
import { normalizeGameState } from "./state/game-state.js";
import { loadPreferences, savePreferences } from "./state/preferences.js";
import { createTurnSynchronizer } from "./state/turn-sync.js";
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
const turnSync = createTurnSynchronizer();
let preferences = loadPreferences();
let currentGameId = null;
let currentReplayId = null;
let maxHand = 0;
let resultsTimer = null;

function showView(name) {
    for (const viewName of ["setup", "game", "results"]) {
        document.querySelector(`#${viewName}-view`).hidden = viewName !== name;
    }
}

function renderGameMeta(game) {
    document.querySelector("#hand-number").textContent = String(game.hand_number || 0);
    document.querySelector("#phase-display").textContent = String(game.phase || "Waiting")
        .replaceAll("_", " ");
    const smallBlind = Number(game.small_blind || game.blinds?.small || 0);
    const bigBlind = Number(game.big_blind || game.blinds?.big || 0);
    document.querySelector("#blinds-display").textContent = `${smallBlind} / ${bigBlind}`;
}

function applyTurn(message) {
    store.update({ turn: message, pendingAction: false });
    actions.setTurn(message, store.getState().game);
    table.hideThinking();
    log.append({ message: "Your turn! Choose an action." });
    status.announce("Your turn");
    sound.play("turn");
}

sound.setEnabled(preferences.soundEnabled);
const soundButton = document.querySelector("#btn-sound");
const updateSoundButton = () => {
    soundButton.setAttribute("aria-pressed", String(preferences.soundEnabled));
    soundButton.textContent = preferences.soundEnabled ? "Sound on" : "Sound off";
};
soundButton.addEventListener("click", () => {
    preferences = { ...preferences, soundEnabled: !preferences.soundEnabled };
    sound.setEnabled(preferences.soundEnabled);
    savePreferences(window.localStorage, preferences);
    updateSoundButton();
});

const logButton = document.querySelector("#btn-toggle-log");
const updateLog = () => {
    log.setCollapsed(preferences.logCollapsed);
    logButton.setAttribute("aria-expanded", String(!preferences.logCollapsed));
    logButton.textContent = preferences.logCollapsed ? "Expand" : "Collapse";
};
logButton.addEventListener("click", () => {
    preferences = { ...preferences, logCollapsed: !preferences.logCollapsed };
    savePreferences(window.localStorage, preferences);
    updateLog();
});

setup.onStart(async (config) => {
    turnSync.reset();
    setup.setBusy(true);
    setup.clearError();
    status.clearError();
    currentReplayId = null;
    maxHand = 0;
    try {
        const { game_id: gameId } = await startGame(config);
        currentGameId = gameId;
        await socket.connect(`${location.origin.replace(/^http/, "ws")}/ws/${gameId}`);
        log.clear();
        actions.disable();
        showView("game");
    } catch (error) {
        turnSync.reset();
        currentGameId = null;
        socket.close();
        setup.showError(`Failed to start game: ${error.message}`);
    } finally {
        setup.setBusy(false);
    }
});

actions.onSubmit((action, amount) => {
    actions.setPending(true);
    if (!socket.send({ type: "player_action", action, amount })) {
        actions.setPending(false);
        status.showError("Action was not sent because the game is disconnected.");
    }
});

socket.on("connection", ({ status: value }) => {
    const disconnected = value !== "connected";
    store.update({
        connection: value,
        ...(disconnected ? { turn: null, pendingAction: false } : {}),
    });
    status.setConnection(value);
    turnSync.setConnection(value);
    if (disconnected) {
        actions.disable();
    }
});

socket.on("game_state", (message) => {
    const game = normalizeGameState(message.state);
    const cachedTurn = turnSync.receiveGameState();
    store.update({ game, turn: null, pendingAction: false });
    table.render(game);
    renderGameMeta(game);
    actions.setPending(false);
    maxHand = Math.max(maxHand, game.hand_number);
    if (cachedTurn) applyTurn(cachedTurn);
});

socket.on("your_turn", (message) => {
    const actionableTurn = turnSync.receiveTurn(message);
    if (actionableTurn) applyTurn(actionableTurn);
});

socket.on("player_action", (message) => {
    log.append(message);
    table.hideThinking();
    sound.play("action");
});

socket.on("ai_thinking", (message) => table.showThinking(message.player_name));

socket.on("hand_result", (message) => {
    log.append(message);
    table.hideThinking();
    actions.disable();
});

socket.on("game_over", (message) => {
    actions.disable();
    table.hideThinking();
    currentReplayId = message.replay_id || null;
    if (resultsTimer !== null) clearTimeout(resultsTimer);
    resultsTimer = setTimeout(() => {
        resultsTimer = null;
        results.render(message, maxHand);
        showView("results");
    }, 1500);
});

socket.on("protocol_error", ({ message }) => status.showError(message));

results.onPlayAgain(() => {
    if (resultsTimer !== null) {
        clearTimeout(resultsTimer);
        resultsTimer = null;
    }
    socket.close();
    turnSync.reset();
    store.reset();
    log.clear();
    status.clearError();
    status.setConnection("disconnected");
    table.hideThinking();
    actions.disable();
    setup.reset();
    currentGameId = null;
    currentReplayId = null;
    maxHand = 0;
    showView("setup");
});

results.onViewReplay((replayId) => {
    const id = replayId || currentReplayId;
    if (!id) {
        status.showError("No replay is available for this game.");
        return;
    }
    window.open(replayUrl(id), "_blank", "noopener");
});

updateSoundButton();
updateLog();
status.setConnection("disconnected");
actions.disable();
showView("setup");

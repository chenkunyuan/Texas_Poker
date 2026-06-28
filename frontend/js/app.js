/**
 * Texas Hold'em Poker — Application Controller
 *
 * Wires together the SetupView, TableView, ResultsView, and WSClient.
 * Manages view switching, WebSocket message routing, and game lifecycle.
 *
 * Exported global: ``App``
 *
 * Initialised automatically on ``DOMContentLoaded``.
 */
var App = (function () {
    "use strict";

    // ------------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------------

    /** @type {string|null} Current game ID (from POST /api/game/start). */
    var _gameId = null;

    /** @type {string|null} Replay ID from the game_over message. */
    var _replayId = null;

    /** @type {number} Tracks the highest hand_number seen across state updates. */
    var _maxHandNumber = 0;

    /** @type {string} The base protocol+host for API calls. */
    var _baseUrl = "";

    /** @type {WSClient} */
    var _ws = null;

    // DOM refs for the three views
    var _setupViewEl;
    var _gameViewEl;
    var _resultsViewEl;

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    /**
     * Bootstrap the application.
     * Called on DOMContentLoaded.
     */
    function init() {
        // Determine base URL for API calls
        _baseUrl = window.location.origin;

        // Cache view elements
        _setupViewEl = document.getElementById("setup-view");
        _gameViewEl = document.getElementById("game-view");
        _resultsViewEl = document.getElementById("results-view");

        // Initialise sub-views
        SetupView.init();
        TableView.init();
        ResultsView.init();

        // Initialise WebSocket client
        _ws = new WSClient();

        // Wire SetupView → start game
        SetupView.onStart(function (config) {
            _startGame(config);
        });

        // Wire TableView → submit action
        TableView.onSubmitAction(function (action, amount) {
            _submitPlayerAction(action, amount);
        });

        // Wire ResultsView → play again / view replay
        ResultsView.onPlayAgain(function () {
            _goToSetup();
        });
        ResultsView.onViewReplay(function () {
            _viewReplay();
        });

        // Register WebSocket message handlers
        _wireWSEvents();

        // Show the setup view on launch
        _showView("setup");
    }

    // ------------------------------------------------------------------
    // View switching
    // ------------------------------------------------------------------

    /**
     * @param {"setup"|"game"|"results"} name
     */
    function _showView(name) {
        _setupViewEl.style.display = name === "setup" ? "" : "none";
        _gameViewEl.style.display = name === "game" ? "" : "none";
        _resultsViewEl.style.display = name === "results" ? "" : "none";
    }

    function _goToSetup() {
        // Close any existing WS connection
        if (_ws && _ws.isConnected()) {
            _ws.close();
        }
        _gameId = null;
        _replayId = null;
        _maxHandNumber = 0;
        TableView.clearActionLog();
        TableView.disableAllButtons();
        TableView.hideThinking();
        SetupView.clearError();
        _showView("setup");
    }

    function _goToGame() {
        _showView("game");
    }

    function _goToResults() {
        _showView("results");
    }

    // ------------------------------------------------------------------
    // Game start flow
    // ------------------------------------------------------------------

    /**
     * POST /api/game/start with the configuration, then connect via WebSocket.
     *
     * @param {object} config — GameConfig-compatible object.
     */
    async function _startGame(config) {
        SetupView.clearError();

        // Show loading state on the button
        var startBtn = document.getElementById("btn-start-game");
        var originalText = startBtn.innerHTML;
        startBtn.innerHTML = '<span class="btn-icon">♠</span> Starting...';
        startBtn.disabled = true;

        try {
            var resp = await fetch(_baseUrl + "/api/game/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(config),
            });

            if (!resp.ok) {
                var errData = null;
                try { errData = await resp.json(); } catch (e) { /* ignore */ }
                throw new Error(
                    (errData && errData.detail) || "Server returned " + resp.status
                );
            }

            var data = await resp.json();
            _gameId = data.game_id;
            _maxHandNumber = 0;

            console.log("[App] Game started:", _gameId);

            // Connect WebSocket
            var wsUrl = _baseUrl.replace(/^http/, "ws") + "/ws/" + _gameId;
            await _ws.connect(wsUrl);

            // Switch to game view
            _goToGame();
            TableView.clearActionLog();
            TableView.disableAllButtons();

        } catch (err) {
            console.error("[App] Failed to start game:", err);
            SetupView.showError("Failed to start game: " + err.message);
        } finally {
            startBtn.innerHTML = originalText;
            startBtn.disabled = false;
        }
    }

    // ------------------------------------------------------------------
    // Player action submission
    // ------------------------------------------------------------------

    /**
     * Send a player action via WebSocket.
     *
     * @param {string} action — "FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"
     * @param {number} amount
     */
    function _submitPlayerAction(action, amount) {
        if (!_ws || !_ws.isConnected()) {
            console.warn("[App] Cannot submit action — not connected.");
            return;
        }

        _ws.send({
            type: "player_action",
            action: action,
            amount: amount,
        });

        console.log("[App] Action sent:", action, amount);
    }

    // ------------------------------------------------------------------
    // WebSocket event routing
    // ------------------------------------------------------------------

    function _wireWSEvents() {
        // game_state — full table update
        _ws.on("game_state", function (msg) {
            if (msg.state) {
                // Track max hand number for results
                if (msg.state.hand_number > _maxHandNumber) {
                    _maxHandNumber = msg.state.hand_number;
                }
                TableView.updateFromState(msg);
            }
        });

        // your_turn — enable action buttons
        _ws.on("your_turn", function (msg) {
            // Append a log entry indicating it's your turn
            TableView.appendActionLog({
                type: "system",
                action: "",
                message: "Your turn! Choose an action.",
            });
            TableView.updateYourTurn(msg);
            TableView.hideThinking();
        });

        // player_action — log it
        _ws.on("player_action", function (msg) {
            TableView.appendActionLog(msg);
            TableView.hideThinking();
        });

        // ai_thinking — show thinking indicator
        _ws.on("ai_thinking", function (msg) {
            TableView.showThinking(msg.player_name);
        });

        // hand_result — log winners
        _ws.on("hand_result", function (msg) {
            TableView.appendActionLog(msg);
            TableView.hideThinking();
            TableView.disableAllButtons();
        });

        // game_over — switch to results view
        _ws.on("game_over", function (msg) {
            _replayId = msg.replay_id || null;
            TableView.hideThinking();
            TableView.disableAllButtons();

            // Brief delay so the player sees the final table state
            setTimeout(function () {
                _goToResults();
                ResultsView.showResults(msg, _maxHandNumber);
            }, 1500);
        });
    }

    // ------------------------------------------------------------------
    // Replay
    // ------------------------------------------------------------------

    /**
     * Navigate to the replay viewer.  Opens a new window/tab or
     * redirects to a replay endpoint (future feature).
     */
    function _viewReplay() {
        if (_replayId) {
            // Open replay in a new tab via the API
            window.open(_baseUrl + "/api/replay/" + _replayId, "_blank");
        } else if (_gameId) {
            window.open(_baseUrl + "/api/replay/" + _gameId, "_blank");
        } else {
            alert("No replay available for this game.");
        }
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    return {
        init: init,
    };
})();

// ----------------------------------------------------------------------
// Auto-initialise when the DOM is fully loaded
// ----------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", function () {
    App.init();
});

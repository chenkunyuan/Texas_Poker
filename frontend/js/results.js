/**
 * Texas Hold'em Poker — Results View Controller
 *
 * Renders the final game-over rankings, statistics, and provides
 * action buttons for "Play Again" and "View Replay".
 *
 * Exported global: ``ResultsView``
 */
var ResultsView = (function () {
    "use strict";

    // DOM refs
    var _viewEl;
    var _rankingsList;
    var _statsContainer;
    var _totalHandsEl;
    var _btnPlayAgain;
    var _btnViewReplay;

    /** @type {object|null} Latest game_over message. */
    var _gameOverMsg = null;

    /** @type {number|null} Total hands from game state tracking. */
    var _totalHands = 0;

    /** @type {Function|null} */
    var _onPlayAgain = null;

    /** @type {Function|null} */
    var _onViewReplay = null;

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    function init() {
        _viewEl = document.getElementById("results-view");
        _rankingsList = document.getElementById("rankings-list");
        _statsContainer = document.getElementById("stats-container");
        _totalHandsEl = document.getElementById("total-hands");
        _btnPlayAgain = document.getElementById("btn-play-again");
        _btnViewReplay = document.getElementById("btn-view-replay");

        _btnPlayAgain.addEventListener("click", function () {
            if (_onPlayAgain) _onPlayAgain();
        });

        _btnViewReplay.addEventListener("click", function () {
            if (_onViewReplay) _onViewReplay(_gameOverMsg);
        });
    }

    // ------------------------------------------------------------------
    // Show / hide
    // ------------------------------------------------------------------

    function show() {
        _viewEl.style.display = "";
    }

    function hide() {
        _viewEl.style.display = "none";
    }

    // ------------------------------------------------------------------
    // Callbacks
    // ------------------------------------------------------------------

    /**
     * Register a handler for the "Play Again" button.
     * @param {Function} fn
     */
    function onPlayAgain(fn) {
        _onPlayAgain = fn;
    }

    /**
     * Register a handler for the "View Replay" button.
     * @param {Function} fn — Receives the game_over message object.
     */
    function onViewReplay(fn) {
        _onViewReplay = fn;
    }

    // ------------------------------------------------------------------
    // Render
    // ------------------------------------------------------------------

    /**
     * Populate the results view from a ``game_over`` WebSocket message.
     *
     * @param {object} msg — {type: "game_over", rankings: [...], stats: {...}, replay_id: "..."}
     * @param {number} [totalHands] — Total hands played.
     */
    function showResults(msg, totalHands) {
        _gameOverMsg = msg;
        _totalHands = totalHands || 0;
        _totalHandsEl.textContent = String(_totalHands);

        _renderRankings(msg.rankings || []);
        _renderStats(msg.stats || {});
    }

    // ------------------------------------------------------------------
    // Rankings
    // ------------------------------------------------------------------

    function _renderRankings(rankings) {
        _rankingsList.innerHTML = "";

        if (rankings.length === 0) {
            var empty = document.createElement("div");
            empty.className = "ranking-item";
            empty.innerHTML = '<span class="rank-info"><span class="rank-name">No results available</span></span>';
            _rankingsList.appendChild(empty);
            return;
        }

        // Medal icons for top 3
        var medals = ["🥇", "🥈", "🥉"];

        for (var i = 0; i < rankings.length; i++) {
            var r = rankings[i];
            var item = document.createElement("div");
            item.className = "ranking-item fade-in";

            // Busted players get special styling
            if (r.chips <= 0) {
                item.classList.add("busted");
            }
            // Human player highlighted
            if (r.is_human) {
                item.classList.add("human");
            }

            var icon = document.createElement("span");
            icon.className = "rank-icon";
            icon.textContent = i < medals.length ? medals[i] : "#" + (i + 1);

            var info = document.createElement("span");
            info.className = "rank-info";

            var nameEl = document.createElement("span");
            nameEl.className = "rank-name";
            nameEl.textContent = (r.player_name || r.player_id || "Unknown");

            if (r.chips <= 0) {
                var bustedTag = document.createElement("span");
                bustedTag.style.cssText = "color:#b71c1c;font-size:0.7rem;margin-left:0.4rem;";
                bustedTag.textContent = "(BUSTED)";
                nameEl.appendChild(bustedTag);
            }

            var chipsEl = document.createElement("span");
            chipsEl.className = "rank-chips";
            chipsEl.textContent = " " + _fmtChips(r.chips) + " chips";

            info.appendChild(nameEl);
            info.appendChild(chipsEl);
            item.appendChild(icon);
            item.appendChild(info);
            _rankingsList.appendChild(item);
        }
    }

    // ------------------------------------------------------------------
    // Statistics
    // ------------------------------------------------------------------

    function _renderStats(stats) {
        _statsContainer.innerHTML = "";

        if (Object.keys(stats).length === 0) {
            var empty = document.createElement("div");
            empty.className = "stat-row";
            empty.innerHTML = '<span class="stat-label">No statistics available</span>';
            _statsContainer.appendChild(empty);
            return;
        }

        // Build aggregate stats
        var humanId = null;
        var totalStartChips = 0;
        var totalFinalChips = 0;
        var playerCount = 0;

        var keys = Object.keys(stats);
        for (var i = 0; i < keys.length; i++) {
            var s = stats[keys[i]];
            if (!s) continue;
            playerCount++;
            totalStartChips += s.starting_chips || 0;
            totalFinalChips += s.final_chips || 0;
        }

        // Find human stats
        for (var j = 0; j < keys.length; j++) {
            var p = stats[keys[j]];
            // The human player's id is always "human"
            if (keys[j] === "human") {
                humanId = keys[j];
                break;
            }
        }

        // Render general stats
        _addStatRow("Total Players", String(playerCount));
        _addStatRow("Total Hands", String(_totalHands));
        _addStatRow("Total Chips in Play", _fmtChips(totalStartChips));

        // Render human player stats if available
        var humanStats = stats["human"];
        if (humanStats) {
            _addStatRow("---", "---");
            _addStatRow("Your Final Chips", _fmtChips(humanStats.final_chips || 0));
            _addStatRow("Your Starting Chips", _fmtChips(humanStats.starting_chips || 0));

            var net = humanStats.net || 0;
            var netLabel = net >= 0 ? "+" + _fmtChips(net) : _fmtChips(net);
            _addStatRow("Your Net Result", netLabel);
        }

        // Per-player breakdown
        _addStatRow("", "");
        for (var k = 0; k < keys.length; k++) {
            var st = stats[keys[k]];
            if (!st) continue;
            var displayName = keys[k] === "human" ? "You" : (keys[k] || "Player " + (k + 1));
            var net2 = st.net || 0;
            var net2Label = net2 >= 0 ? "+" + _fmtChips(net2) : _fmtChips(net2);
            _addStatRow(displayName + " Net", net2Label);
        }
    }

    function _addStatRow(label, value) {
        var row = document.createElement("div");
        row.className = "stat-row";

        var labelEl = document.createElement("span");
        labelEl.className = "stat-label";
        labelEl.textContent = label;

        var valueEl = document.createElement("span");
        valueEl.className = "stat-value";
        valueEl.textContent = value;

        row.appendChild(labelEl);
        row.appendChild(valueEl);
        _statsContainer.appendChild(row);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    function _fmtChips(n) {
        if (n === undefined || n === null) return "0";
        return n.toLocaleString();
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    return {
        init: init,
        show: show,
        hide: hide,
        showResults: showResults,
        onPlayAgain: onPlayAgain,
        onViewReplay: onViewReplay,
    };
})();

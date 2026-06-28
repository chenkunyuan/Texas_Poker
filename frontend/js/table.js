/**
 * Texas Hold'em Poker — Table View Controller
 *
 * Renders the poker table with community cards, player spots, action log,
 * and manages the bottom action bar for human input.  Receives game-state
 * snapshots from the server and translates them into DOM updates.
 *
 * Exported global: ``TableView``
 */
var TableView = (function () {
    "use strict";

    // ------------------------------------------------------------------
    // Suit display helpers
    // ------------------------------------------------------------------

    /** Map server suit strings to Unicode symbols. */
    var SUIT_SYMBOLS = {
        HEARTS: "♥",   // ♥
        DIAMONDS: "♦", // ♦
        CLUBS: "♣",    // ♣
        SPADES: "♠",   // ♠
    };

    /** Suits that should be displayed in red. */
    var RED_SUITS = { HEARTS: true, DIAMONDS: true };

    /**
     * Determine the CSS class for a card's suit colour.
     * @param {string} suit — e.g. "HEARTS"
     * @returns {string} "suit-red" or "suit-black"
     */
    function _suitClass(suit) {
        return RED_SUITS[suit] ? "suit-red" : "suit-black";
    }

    // ------------------------------------------------------------------
    // Player position presets (percentages on the oval table)
    // ------------------------------------------------------------------

    /**
     * Pre-computed (x, y) positions as percentages of the table felt.
     * Index 0 is always the human player at the bottom.
     * Keys are the total number of players.
     */
    var PLAYER_POSITIONS = {
        2: [
            { x: 50, y: 80 },
            { x: 50, y: 20 },
        ],
        3: [
            { x: 50, y: 82 },
            { x: 15, y: 25 },
            { x: 85, y: 25 },
        ],
        4: [
            { x: 50, y: 82 },
            { x: 10, y: 30 },
            { x: 90, y: 30 },
            { x: 50, y: 18 },
        ],
        5: [
            { x: 50, y: 84 },
            { x: 8, y: 35 },
            { x: 92, y: 35 },
            { x: 30, y: 16 },
            { x: 70, y: 16 },
        ],
        6: [
            { x: 50, y: 84 },
            { x: 5, y: 35 },
            { x: 95, y: 35 },
            { x: 20, y: 14 },
            { x: 80, y: 14 },
            { x: 50, y: 14 },
        ],
        7: [
            { x: 50, y: 85 },
            { x: 5, y: 35 },
            { x: 95, y: 35 },
            { x: 12, y: 14 },
            { x: 88, y: 14 },
            { x: 35, y: 10 },
            { x: 65, y: 10 },
        ],
        8: [
            { x: 50, y: 85 },
            { x: 5, y: 35 },
            { x: 95, y: 35 },
            { x: 8, y: 14 },
            { x: 92, y: 14 },
            { x: 25, y: 9 },
            { x: 75, y: 9 },
            { x: 50, y: 9 },
        ],
        9: [
            { x: 50, y: 86 },
            { x: 5, y: 38 },
            { x: 95, y: 38 },
            { x: 7, y: 16 },
            { x: 93, y: 16 },
            { x: 18, y: 8 },
            { x: 82, y: 8 },
            { x: 38, y: 7 },
            { x: 62, y: 7 },
        ],
    };

    // ------------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------------

    /** @type {object|null} Latest game state snapshot. */
    var _state = null;

    /** @type {object|null} Latest your_turn payload. */
    var _turnData = null;

    /** @type {Function|null} Callback for submitting an action. */
    var _submitCb = null;

    /** @type {string|null} CSS class of the view that was active before game. */
    var _previousView = null;

    // DOM refs
    var _viewEl;
    var _tableFelt;
    var _playerSpots;
    var _communityCards;
    var _potLabel;
    var _actionLog;
    var _thinkingIndicator;
    var _thinkingText;

    // Sidebar refs
    var _yourCardsEl;
    var _yourPositionEl;
    var _yourChipsEl;
    var _potDisplayEl;
    var _currentBetDisplayEl;

    // Top bar refs
    var _handNumberEl;
    var _phaseDisplayEl;
    var _blindsDisplayEl;
    var _variantDisplayEl;

    // Action bar refs
    var _btnFold, _btnCheck, _btnCall, _btnRaise, _btnAllin;
    var _callAmountEl, _raiseDisplayEl, _allinAmountEl;
    var _raiseSlider, _raiseInput;

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    /**
     * Cache DOM references and bind events. Call once after DOM is ready.
     */
    function init() {
        _viewEl = document.getElementById("game-view");

        // Center table
        _tableFelt = _viewEl.querySelector(".table-felt");
        _playerSpots = document.getElementById("player-spots");
        _communityCards = document.getElementById("community-cards");
        _potLabel = document.getElementById("pot-label");
        _thinkingIndicator = document.getElementById("thinking-indicator");
        _thinkingText = document.getElementById("thinking-text");

        // Left sidebar
        _yourCardsEl = document.getElementById("your-cards");
        _yourPositionEl = document.getElementById("your-position");
        _yourChipsEl = document.getElementById("your-chips");
        _potDisplayEl = document.getElementById("pot-display");
        _currentBetDisplayEl = document.getElementById("current-bet-display");

        // Top bar
        _handNumberEl = document.getElementById("hand-number");
        _phaseDisplayEl = document.getElementById("phase-display");
        _blindsDisplayEl = document.getElementById("blinds-display");
        _variantDisplayEl = document.getElementById("variant-display");

        // Action log
        _actionLog = document.getElementById("action-log");

        // Action buttons
        _btnFold = document.getElementById("btn-fold");
        _btnCheck = document.getElementById("btn-check");
        _btnCall = document.getElementById("btn-call");
        _btnRaise = document.getElementById("btn-raise");
        _btnAllin = document.getElementById("btn-allin");
        _callAmountEl = document.getElementById("call-amount");
        _raiseDisplayEl = document.getElementById("raise-display");
        _allinAmountEl = document.getElementById("allin-amount");
        _raiseSlider = document.getElementById("raise-slider");
        _raiseInput = document.getElementById("raise-amount");

        _bindActionButtons();
        _bindKeyboardShortcuts();
        _bindRaiseControls();
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
    // Action submission callback
    // ------------------------------------------------------------------

    /**
     * Register the function to call when the human player clicks an action.
     *
     * @param {Function} cb — Receives (action: string, amount: number).
     */
    function onSubmitAction(cb) {
        _submitCb = cb;
    }

    // ------------------------------------------------------------------
    // Full render from game_state message
    // ------------------------------------------------------------------

    /**
     * Update the entire table view from a ``game_state`` message.
     *
     * @param {object} msg — The parsed WebSocket message.
     *     ``msg.state`` contains the GameState object.
     */
    function updateFromState(msg) {
        _state = msg.state;
        if (!_state) return;
        render();
    }

    // ------------------------------------------------------------------
    // Update action buttons from your_turn message
    // ------------------------------------------------------------------

    /**
     * Enable / disable action buttons based on valid actions.
     *
     * @param {object} msg — The parsed ``your_turn`` message.
     */
    function updateYourTurn(msg) {
        _turnData = msg;
        _updateActionButtons(msg);
    }

    // ------------------------------------------------------------------
    // Render helpers (called by render())
    // ------------------------------------------------------------------

    /**
     * Full re-render of the table, sidebars, and top bar from ``_state``.
     */
    function render() {
        var s = _state;
        if (!s) return;

        // Top bar
        _handNumberEl.textContent = String(s.hand_number || 1);
        _phaseDisplayEl.textContent = _formatPhase(s.phase);
        if (s.blinds) {
            _blindsDisplayEl.textContent = s.blinds.small + "/" + s.blinds.big;
        }
        if (s.config) {
            _variantDisplayEl.textContent =
                s.config.variant === "pot_limit" ? "Pot-Limit" : "No-Limit";
        }

        // Sidebar — human player info
        var human = _findHuman(s);
        if (human) {
            _renderCards(_yourCardsEl, human.hole_cards || [], false);
            _yourPositionEl.textContent = human.position || "--";
            _yourChipsEl.textContent = _fmtChips(human.chips);
        } else {
            _yourCardsEl.innerHTML =
                '<div class="card-placeholder">?</div><div class="card-placeholder">?</div>';
            _yourPositionEl.textContent = "--";
            _yourChipsEl.textContent = "0";
        }

        // Pot / current bet
        _potDisplayEl.textContent = _fmtChips(s.pot || 0);
        _potLabel.textContent = "Pot: " + _fmtChips(s.pot || 0);
        _currentBetDisplayEl.textContent = _fmtChips(s.current_bet || 0);

        // Community cards
        _renderCommunityCards(s.community_cards || []);

        // Players on the table
        _renderPlayers(s.players || [], s.dealer_index || 0, s.current_player_index);

        // Set the action badges (last action per player from history)
        _renderActionBadges(s);

        // Disable buttons when it is not the human's turn
        if (!_turnData) {
            _disableAllButtons();
        }
    }

    /**
     * Render community cards in the table center.
     * @param {Array} cards — Array of {rank, suit} objects.
     */
    function _renderCommunityCards(cards) {
        var slots = _communityCards.querySelectorAll(".card-slot");
        for (var i = 0; i < slots.length; i++) {
            if (i < cards.length) {
                var card = cards[i];
                slots[i].innerHTML = "";
                slots[i].className = "card-slot";
                var cardEl = _createCardElement(card, true);
                slots[i].appendChild(cardEl);
            } else {
                slots[i].innerHTML = "";
                slots[i].className = "card-slot empty";
            }
        }
    }

    /**
     * Render player spots around the oval table.
     *
     * @param {Array} players — Array of Player objects.
     * @param {number} dealerIndex — Index of the dealer button.
     * @param {number|null} currentPlayerIndex — Index of player whose turn it is.
     */
    function _renderPlayers(players, dealerIndex, currentPlayerIndex) {
        var count = players.length;
        var positions = PLAYER_POSITIONS[count];
        if (!positions) {
            // Fallback: generate positions in a circle
            positions = _generatePositions(count);
        }

        _playerSpots.innerHTML = "";

        for (var i = 0; i < count; i++) {
            var player = players[i];
            var pos = positions[i];
            if (!pos) continue;

            var isHuman = player.is_human;
            var isFolded = !player.is_active;
            var isActiveTurn = currentPlayerIndex === i;
            var isDealer = dealerIndex === i;

            var spot = _createPlayerSpot(
                player,
                pos,
                isHuman,
                isFolded,
                isActiveTurn,
                isDealer
            );
            _playerSpots.appendChild(spot);
        }
    }

    /**
     * Create a single player spot element.
     */
    function _createPlayerSpot(player, pos, isHuman, isFolded, isActiveTurn, isDealer) {
        var div = document.createElement("div");
        div.className = "player-spot";
        if (isHuman) div.classList.add("human");
        if (isFolded) div.classList.add("folded");
        if (isActiveTurn) div.classList.add("active-turn");

        div.style.left = pos.x + "%";
        div.style.top = pos.y + "%";
        div.setAttribute("data-player-id", player.id);

        // Avatar
        var avatar = document.createElement("div");
        avatar.className = "player-avatar";
        avatar.textContent = isHuman ? "Y" : (player.name || "?").charAt(0).toUpperCase();

        // Dealer button
        if (isDealer) {
            var dBtn = document.createElement("div");
            dBtn.className = "dealer-btn";
            dBtn.textContent = "D";
            avatar.appendChild(dBtn);
        }

        // Name
        var nameEl = document.createElement("span");
        nameEl.className = "player-name";
        nameEl.textContent = isHuman ? "You" : (player.name || "AI");
        nameEl.title = player.name || "";

        // Chips
        var chipsEl = document.createElement("span");
        chipsEl.className = "player-chips";
        chipsEl.textContent = _fmtChips(player.chips);

        div.appendChild(avatar);
        div.appendChild(nameEl);
        div.appendChild(chipsEl);

        return div;
    }

    /**
     * Attach action badges to player spots showing their last action.
     */
    function _renderActionBadges(state) {
        var history = state.action_history || [];
        if (history.length === 0) return;

        // Build a map of player_id -> last action
        var lastActions = {};
        for (var i = 0; i < history.length; i++) {
            lastActions[history[i].player_id] = history[i];
        }

        var spots = _playerSpots.querySelectorAll(".player-spot");
        for (var j = 0; j < spots.length; j++) {
            var spot = spots[j];
            var pid = spot.getAttribute("data-player-id");
            var action = lastActions[pid];
            // Remove any existing badge
            var existingBadge = spot.querySelector(".player-action-badge");
            if (existingBadge) existingBadge.remove();

            if (action) {
                var badge = document.createElement("span");
                badge.className = "player-action-badge " + _actionCssClass(action.action);
                badge.textContent = _actionLabel(action);
                spot.appendChild(badge);
            }
        }
    }

    // ------------------------------------------------------------------
    // Card rendering
    // ------------------------------------------------------------------

    /**
     * Render an array of cards into a container element.
     *
     * @param {HTMLElement} container
     * @param {Array} cards — Array of {rank, suit} objects.
     * @param {boolean} faceUp — If false, cards render face-down.
     */
    function _renderCards(container, cards, faceUp) {
        container.innerHTML = "";
        if (!cards || cards.length === 0) {
            if (faceUp === undefined) {
                // Hole cards — show placeholders
                container.innerHTML =
                    '<div class="card-placeholder">?</div><div class="card-placeholder">?</div>';
            }
            return;
        }

        for (var i = 0; i < cards.length; i++) {
            var el;
            if (faceUp) {
                el = _createCardElement(cards[i], true);
            } else {
                el = _createCardElement(cards[i], false);
            }
            container.appendChild(el);
        }
    }

    /**
     * Create a single card div element.
     *
     * @param {object} card — {rank: "A", suit: "HEARTS"}
     * @param {boolean} faceUp
     * @returns {HTMLElement}
     */
    function _createCardElement(card, faceUp) {
        var el = document.createElement("div");
        el.className = "card";

        if (!faceUp) {
            el.classList.add("face-down");
            return el;
        }

        var suitClass = _suitClass(card.suit);
        el.classList.add(suitClass);

        var rankEl = document.createElement("span");
        rankEl.className = "card-rank";
        rankEl.textContent = card.rank;

        var suitEl = document.createElement("span");
        suitEl.className = "card-suit";
        suitEl.textContent = SUIT_SYMBOLS[card.suit] || card.suit;

        el.appendChild(rankEl);
        el.appendChild(suitEl);

        return el;
    }

    // ------------------------------------------------------------------
    // Action log
    // ------------------------------------------------------------------

    /**
     * Append an entry to the action log in the right sidebar.
     *
     * @param {object} msg — Parsed WebSocket message (player_action, hand_result, etc.)
     */
    function appendActionLog(msg) {
        var entry = document.createElement("div");
        entry.className = "log-entry " + _actionCssClass(msg.action || "");

        var type = msg.type;

        if (type === "player_action") {
            // "PlayerName FOLD" or "PlayerName RAISE to 200"
            var nameSpan = document.createElement("span");
            nameSpan.className = "player-name-log";
            nameSpan.textContent = (msg.player_name || msg.player_id) + " ";

            var actionSpan = document.createElement("span");
            actionSpan.className = "action-type";
            actionSpan.textContent = _actionLabel(msg);

            entry.appendChild(nameSpan);
            entry.appendChild(actionSpan);

            if (msg.amount > 0 && (msg.action === "RAISE" || msg.action === "ALL_IN" || msg.action === "CALL")) {
                var amountSpan = document.createElement("span");
                amountSpan.className = "action-amount";
                amountSpan.textContent = " " + _fmtChips(msg.amount);
                entry.appendChild(amountSpan);
            }
        } else if (type === "ai_thinking") {
            entry.classList.add("system");
            entry.textContent = (msg.player_name || "AI") + " is thinking...";
        } else if (type === "hand_result") {
            entry.classList.add("hand_result");
            var winners = msg.winners || [];
            var names = [];
            for (var i = 0; i < winners.length; i++) {
                names.push(winners[i].player_name || winners[i].player_id);
            }
            entry.textContent = "Winner: " + names.join(", ");
        } else {
            entry.textContent = JSON.stringify(msg);
        }

        _actionLog.appendChild(entry);
        _actionLog.scrollTop = _actionLog.scrollHeight;

        // Limit log entries
        while (_actionLog.children.length > 100) {
            _actionLog.removeChild(_actionLog.firstChild);
        }
    }

    function clearActionLog() {
        _actionLog.innerHTML =
            '<div class="log-entry system">Waiting for first hand...</div>';
    }

    // ------------------------------------------------------------------
    // AI Thinking indicator
    // ------------------------------------------------------------------

    function showThinking(playerName) {
        _thinkingText.textContent = (playerName || "AI") + " is thinking...";
        _thinkingIndicator.style.display = "";
    }

    function hideThinking() {
        _thinkingIndicator.style.display = "none";
    }

    // ------------------------------------------------------------------
    // Action bar logic
    // ------------------------------------------------------------------

    function _bindActionButtons() {
        _btnFold.addEventListener("click", function () {
            _doAction("FOLD", 0);
        });
        _btnCheck.addEventListener("click", function () {
            _doAction("CHECK", 0);
        });
        _btnCall.addEventListener("click", function () {
            var amt = _turnData ? (_turnData.call_amount || 0) : 0;
            _doAction("CALL", amt);
        });
        _btnRaise.addEventListener("click", function () {
            var amt = parseInt(_raiseInput.value, 10) || 0;
            _doAction("RAISE", amt);
        });
        _btnAllin.addEventListener("click", function () {
            var amt = _state ? (_findHuman(_state) || {}).chips || 0 : 0;
            _doAction("ALL_IN", amt);
        });
    }

    function _doAction(action, amount) {
        if (_submitCb) {
            _submitCb(action, amount);
        }
        // Disable buttons immediately to prevent double-clicks
        _disableAllButtons();
        _turnData = null;
    }

    /**
     * Enable / disable action buttons based on the valid_actions map.
     *
     * @param {object} turnData — The ``your_turn`` message payload.
     */
    function _updateActionButtons(turnData) {
        var valid = turnData.valid_actions || {};

        // Fold
        _setButtonEnabled(_btnFold, !!valid.FOLD);
        // Check
        _setButtonEnabled(_btnCheck, !!valid.CHECK);
        // Call
        var hasCall = !!valid.CALL;
        _setButtonEnabled(_btnCall, hasCall);
        if (hasCall) {
            var callAmt = turnData.call_amount || 0;
            _callAmountEl.textContent = callAmt > 0 ? _fmtChips(callAmt) : "";
        }

        // Raise
        var hasRaise = !!valid.RAISE;
        _setButtonEnabled(_btnRaise, hasRaise);
        _raiseSlider.disabled = !hasRaise;
        _raiseInput.disabled = !hasRaise;

        if (hasRaise) {
            var minRaise = turnData.min_raise || 0;
            var maxRaise = turnData.max_raise || minRaise;
            _raiseSlider.min = String(minRaise);
            _raiseSlider.max = String(maxRaise);
            _raiseSlider.value = String(minRaise);
            _raiseInput.min = String(minRaise);
            _raiseInput.max = String(maxRaise);
            _raiseInput.value = String(minRaise);
            _raiseDisplayEl.textContent = _fmtChips(minRaise);
        } else {
            _raiseDisplayEl.textContent = "0";
        }

        // All-in
        var hasAllIn = !!valid.ALL_IN;
        _setButtonEnabled(_btnAllin, hasAllIn);
        if (hasAllIn && _state) {
            var human = _findHuman(_state);
            if (human) {
                _allinAmountEl.textContent = _fmtChips(human.chips);
            }
        }
    }

    function _setButtonEnabled(btn, enabled) {
        btn.disabled = !enabled;
    }

    function _disableAllButtons() {
        _btnFold.disabled = true;
        _btnCheck.disabled = true;
        _btnCall.disabled = true;
        _btnRaise.disabled = true;
        _btnAllin.disabled = true;
        _raiseSlider.disabled = true;
        _raiseInput.disabled = true;
        _callAmountEl.textContent = "";
        _raiseDisplayEl.textContent = "0";
        _allinAmountEl.textContent = "";
    }

    // ------------------------------------------------------------------
    // Raise slider / input sync
    // ------------------------------------------------------------------

    function _bindRaiseControls() {
        _raiseSlider.addEventListener("input", function () {
            var val = parseInt(_raiseSlider.value, 10);
            _raiseInput.value = String(val);
            _raiseDisplayEl.textContent = _fmtChips(val);
        });

        _raiseInput.addEventListener("input", function () {
            var val = parseInt(_raiseInput.value, 10);
            if (!isNaN(val)) {
                var min = parseInt(_raiseSlider.min, 10) || 0;
                var max = parseInt(_raiseSlider.max, 10) || val;
                if (val < min) val = min;
                if (val > max) val = max;
                _raiseSlider.value = String(val);
                _raiseDisplayEl.textContent = _fmtChips(val);
            }
        });
    }

    // ------------------------------------------------------------------
    // Keyboard shortcuts
    // ------------------------------------------------------------------

    function _bindKeyboardShortcuts() {
        document.addEventListener("keydown", function (e) {
            // Only process if game view is visible
            if (_viewEl.style.display === "none") return;
            // Ignore if user is typing in an input
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;

            switch (e.key.toUpperCase()) {
                case "F":
                    if (!_btnFold.disabled) { e.preventDefault(); _btnFold.click(); }
                    break;
                case "C":
                    if (!_btnCheck.disabled) { e.preventDefault(); _btnCheck.click(); }
                    break;
                case "A":
                    if (!_btnCall.disabled) { e.preventDefault(); _btnCall.click(); }
                    break;
                case "R":
                    if (!_btnRaise.disabled) { e.preventDefault(); _btnRaise.click(); }
                    break;
                case "I":
                    if (!_btnAllin.disabled) { e.preventDefault(); _btnAllin.click(); }
                    break;
            }
        });
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    /**
     * Find the human player in the state's player list.
     * @param {object} state
     * @returns {object|null}
     */
    function _findHuman(state) {
        var players = state.players || [];
        for (var i = 0; i < players.length; i++) {
            if (players[i].is_human) return players[i];
        }
        return null;
    }

    /**
     * Format a chip amount with commas.
     * @param {number} n
     * @returns {string}
     */
    function _fmtChips(n) {
        if (n === undefined || n === null) return "0";
        return n.toLocaleString();
    }

    /**
     * Convert a server phase string to a display label.
     * @param {string} phase
     * @returns {string}
     */
    function _formatPhase(phase) {
        var labels = {
            SETUP: "Setup",
            PRE_FLOP: "Pre-Flop",
            FLOP: "Flop",
            TURN: "Turn",
            RIVER: "River",
            SHOWDOWN: "Showdown",
            HAND_END: "Hand End",
            GAME_OVER: "Game Over",
        };
        return labels[phase] || phase;
    }

    /**
     * Map an action string to a CSS-friendly class name.
     * @param {string} action — "FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"
     * @returns {string}
     */
    function _actionCssClass(action) {
        var a = (action || "").toLowerCase();
        var map = {
            fold: "fold",
            check: "check",
            call: "call",
            raise: "raise",
            all_in: "all_in",
        };
        return map[a] || "";
    }

    /**
     * Generate a short label for an action object {action, amount}.
     * @param {object} actionObj
     * @returns {string}
     */
    function _actionLabel(actionObj) {
        var a = actionObj.action || "";
        var amt = actionObj.amount || 0;
        switch (a) {
            case "FOLD": return "fold";
            case "CHECK": return "check";
            case "CALL": return amt > 0 ? "call " + _fmtChips(amt) : "call";
            case "RAISE": return "raise to " + _fmtChips(amt);
            case "ALL_IN": return "all-in " + _fmtChips(amt);
            default: return a;
        }
    }

    /**
     * Fallback: generate N positions in an approximate circle on the table.
     * Used when there are no pre-computed positions for this player count.
     * @param {number} count
     * @returns {Array}
     */
    function _generatePositions(count) {
        var positions = [];
        // Place the human at the bottom
        positions.push({ x: 50, y: 84 });

        // Distribute remaining players around the upper arc
        var remaining = count - 1;
        for (var i = 0; i < remaining; i++) {
            var frac = (i + 1) / (remaining + 1);
            var x = 5 + frac * 90;
            var y = 14 + Math.sin(frac * Math.PI) * 24;
            positions.push({ x: Math.round(x), y: Math.round(y) });
        }
        return positions;
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    return {
        init: init,
        show: show,
        hide: hide,
        updateFromState: updateFromState,
        updateYourTurn: updateYourTurn,
        render: render,
        appendActionLog: appendActionLog,
        clearActionLog: clearActionLog,
        showThinking: showThinking,
        hideThinking: hideThinking,
        onSubmitAction: onSubmitAction,
        disableAllButtons: _disableAllButtons,
    };
})();

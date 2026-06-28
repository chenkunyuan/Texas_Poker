/**
 * Texas Hold'em Poker — Setup View Controller
 *
 * Manages the pre-game configuration form: variant toggles, AI count
 * stepper, chip/blinds inputs, personality and LLM settings.  Reads the
 * form state as a GameConfig payload and submits it to ``POST /api/game/start``.
 *
 * Exported global: ``SetupView``
 */
var SetupView = (function () {
    "use strict";

    // ------------------------------------------------------------------
    // Internal state
    // ------------------------------------------------------------------

    /** @type {Object<string, string>} — field name -> selected value */
    var _toggles = {
        variant: "no_limit",
        blinds_mode: "fixed",
        personality_mode: "random",
    };

    /** @type {number} */
    var _aiCount = 5;

    /** @type {number} */
    var _aiCountMin = 1;
    var _aiCountMax = 8;

    // DOM references (cached on init)
    var _viewEl;
    var _btnStart;
    var _errorEl;
    var _stepperValueEl;

    // ------------------------------------------------------------------
    // Initialisation
    // ------------------------------------------------------------------

    /**
     * Bind all UI event listeners inside the setup view.
     * Call once after the DOM is ready.
     */
    function init() {
        _viewEl = document.getElementById("setup-view");
        _btnStart = document.getElementById("btn-start-game");
        _errorEl = document.getElementById("setup-error");
        _stepperValueEl = _viewEl.querySelector(".stepper-value");

        _bindToggles();
        _bindStepper();
        _bindBlindsToggle();
        _bindStartButton();
    }

    // ------------------------------------------------------------------
    // Show / hide
    // ------------------------------------------------------------------

    /** Show the setup view (hide others). */
    function show() {
        _viewEl.style.display = "";
        _errorEl.style.display = "none";
    }

    /** Hide the setup view. */
    function hide() {
        _viewEl.style.display = "none";
    }

    // ------------------------------------------------------------------
    // Toggle groups (variant, blinds_mode, personality_mode)
    // ------------------------------------------------------------------

    function _bindToggles() {
        var groups = _viewEl.querySelectorAll(".toggle-group");
        for (var i = 0; i < groups.length; i++) {
            var group = groups[i];
            var field = group.getAttribute("data-field");
            if (!field) continue;

            var buttons = group.querySelectorAll(".toggle-btn");
            for (var j = 0; j < buttons.length; j++) {
                (function (btn, fld) {
                    btn.addEventListener("click", function () {
                        // Deactivate siblings
                        var siblings = btn.parentElement.querySelectorAll(".toggle-btn");
                        for (var k = 0; k < siblings.length; k++) {
                            siblings[k].classList.remove("active");
                        }
                        btn.classList.add("active");
                        _toggles[fld] = btn.getAttribute("data-value");

                        // Special case: blinds mode toggles visibility of sub-forms
                        if (fld === "blinds_mode") {
                            _updateBlindsForm();
                        }
                    });
                })(buttons[j], field);
            }
        }
    }

    // ------------------------------------------------------------------
    // AI Count Stepper
    // ------------------------------------------------------------------

    function _bindStepper() {
        var stepper = _viewEl.querySelector(".stepper");
        if (!stepper) return;

        var buttons = stepper.querySelectorAll(".stepper-btn");
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].addEventListener("click", function () {
                var action = this.getAttribute("data-action");
                if (action === "up" && _aiCount < _aiCountMax) {
                    _aiCount++;
                } else if (action === "down" && _aiCount > _aiCountMin) {
                    _aiCount--;
                }
                _stepperValueEl.textContent = String(_aiCount);
            });
        }
    }

    // ------------------------------------------------------------------
    // Blinds mode sub-form visibility
    // ------------------------------------------------------------------

    function _bindBlindsToggle() {
        // Initial state
        _updateBlindsForm();
    }

    function _updateBlindsForm() {
        var fixedGroup = document.getElementById("blinds-fixed-group");
        var incGroup = document.getElementById("blinds-increasing-group");
        var mode = _toggles.blinds_mode;

        if (fixedGroup) fixedGroup.style.display = mode === "fixed" ? "" : "none";
        if (incGroup) incGroup.style.display = mode === "increasing" ? "" : "none";
    }

    // ------------------------------------------------------------------
    // Start button
    // ------------------------------------------------------------------

    function _bindStartButton() {
        _btnStart.addEventListener("click", function () {
            var config = getConfig();
            var error = validateConfig(config);
            if (error) {
                showError(error);
                return;
            }
            _errorEl.style.display = "none";

            // Fire the async start logic — App wires this up.
            if (typeof _onStart === "function") {
                _onStart(config);
            }
        });
    }

    /** @type {Function|null} — set by App to handle the start action. */
    var _onStart = null;

    /**
     * Register a callback invoked when the player clicks "Start Game".
     *
     * @param {Function} fn — Receives the GameConfig object.
     */
    function onStart(fn) {
        _onStart = fn;
    }

    // ------------------------------------------------------------------
    // Configuration builder
    // ------------------------------------------------------------------

    /**
     * Read all form values and return a GameConfig-compatible object.
     *
     * @returns {object}
     */
    function getConfig() {
        var blindsMode = _toggles.blinds_mode;
        var blinds = {
            mode: blindsMode,
        };

        if (blindsMode === "fixed") {
            blinds.small = _readInt("sb-value", 5);
            blinds.big = _readInt("bb-value", 10);
        } else {
            blinds.small = _readInt("inc-sb", 5);
            blinds.big = _readInt("inc-bb", 10);
            blinds.increase_interval = _readInt("inc-interval", 10);
            blinds.increase_multiplier = _readFloat("inc-multiplier", 2.0);
        }

        return {
            variant: _toggles.variant,
            ai_player_count: _aiCount,
            starting_chips: _readInt("starting-chips", 1000),
            blinds: blinds,
            personality_mode: _toggles.personality_mode,
            llm_provider: _readSelect("llm-provider", "anthropic"),
        };
    }

    // ------------------------------------------------------------------
    // Validation
    // ------------------------------------------------------------------

    /**
     * @param {object} config
     * @returns {string|null} Error message or null if valid.
     */
    function validateConfig(config) {
        if (config.starting_chips < 10) {
            return "Starting chips must be at least 10.";
        }
        if (config.blinds.big <= config.blinds.small) {
            return "Big Blind must be greater than Small Blind.";
        }
        if (config.blinds.small <= 0 || config.blinds.big <= 0) {
            return "Blind values must be positive.";
        }
        if (config.ai_player_count < 1 || config.ai_player_count > 8) {
            return "AI player count must be between 1 and 8.";
        }
        return null;
    }

    // ------------------------------------------------------------------
    // Error display
    // ------------------------------------------------------------------

    function showError(msg) {
        _errorEl.textContent = msg;
        _errorEl.style.display = "";
    }

    function clearError() {
        _errorEl.style.display = "none";
        _errorEl.textContent = "";
    }

    // ------------------------------------------------------------------
    // Helpers: read form values
    // ------------------------------------------------------------------

    function _readInt(id, fallback) {
        var el = document.getElementById(id);
        if (!el) return fallback;
        var val = parseInt(el.value, 10);
        return isNaN(val) ? fallback : val;
    }

    function _readFloat(id, fallback) {
        var el = document.getElementById(id);
        if (!el) return fallback;
        var val = parseFloat(el.value);
        return isNaN(val) ? fallback : val;
    }

    function _readSelect(id, fallback) {
        var el = document.getElementById(id);
        if (!el) return fallback;
        return el.value || fallback;
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    return {
        init: init,
        show: show,
        hide: hide,
        getConfig: getConfig,
        onStart: onStart,
        showError: showError,
        clearError: clearError,
    };
})();

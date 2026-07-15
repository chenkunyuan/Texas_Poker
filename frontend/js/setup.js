/**
 * Read the setup form as the GameConfig payload expected by the server.
 *
 * @param {Document|Element} root
 * @param {object} toggles
 * @param {number} aiCount
 * @returns {object}
 */
function readConfig(root, toggles, aiCount) {
    const readInt = (selector, fallback) => {
        const element = root.querySelector(selector);
        if (!element) return fallback;
        const value = Number.parseInt(element.value, 10);
        return Number.isNaN(value) ? fallback : value;
    };
    const readFloat = (selector, fallback) => {
        const element = root.querySelector(selector);
        if (!element) return fallback;
        const value = Number.parseFloat(element.value);
        return Number.isNaN(value) ? fallback : value;
    };

    const blinds = { mode: toggles.blinds_mode };
    if (toggles.blinds_mode === "fixed") {
        blinds.small = readInt("#sb-value", 5);
        blinds.big = readInt("#bb-value", 10);
    } else {
        blinds.small = readInt("#inc-sb", 5);
        blinds.big = readInt("#inc-bb", 10);
        blinds.increase_interval = readInt("#inc-interval", 10);
        blinds.increase_multiplier = readFloat("#inc-multiplier", 2.0);
    }

    return {
        variant: toggles.variant,
        ai_player_count: aiCount,
        starting_chips: readInt("#starting-chips", 1000),
        blinds,
        personality_mode: toggles.personality_mode,
    };
}

/**
 * @param {object} config
 * @returns {string|null}
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

/**
 * Create the pre-game configuration view.
 *
 * @param {Document|Element} root
 * @returns {{onStart: Function, setBusy: Function, showError: Function, clearError: Function, reset: Function}}
 */
export function createSetupView(root = document) {
    const view = root.querySelector("#setup-view");
    const button = root.querySelector("#btn-start-game");
    const error = root.querySelector("#setup-error");
    const stepperValue = view.querySelector(".stepper-value");
    const toggles = {
        variant: "no_limit",
        blinds_mode: "fixed",
        personality_mode: "random",
    };
    let aiCount = 5;
    let onStart = () => {};

    const updateBlindsForm = () => {
        const fixedGroup = root.querySelector("#blinds-fixed-group");
        const increasingGroup = root.querySelector("#blinds-increasing-group");
        if (fixedGroup) fixedGroup.style.display = toggles.blinds_mode === "fixed" ? "" : "none";
        if (increasingGroup) increasingGroup.style.display = toggles.blinds_mode === "increasing" ? "" : "none";
    };

    const showError = (message) => {
        error.textContent = message;
        error.style.display = "";
        error.hidden = false;
    };
    const clearError = () => {
        error.textContent = "";
        error.hidden = true;
    };

    view.querySelectorAll(".toggle-group").forEach((group) => {
        const field = group.dataset.field;
        if (!field) return;
        group.querySelectorAll(".toggle-btn").forEach((toggleButton) => {
            toggleButton.addEventListener("click", () => {
                group.querySelectorAll(".toggle-btn").forEach((sibling) => sibling.classList.remove("active"));
                toggleButton.classList.add("active");
                toggles[field] = toggleButton.dataset.value;
                if (field === "blinds_mode") updateBlindsForm();
            });
        });
    });

    view.querySelectorAll(".stepper-btn").forEach((stepperButton) => {
        stepperButton.addEventListener("click", () => {
            if (stepperButton.dataset.action === "up" && aiCount < 8) aiCount += 1;
            if (stepperButton.dataset.action === "down" && aiCount > 1) aiCount -= 1;
            stepperValue.textContent = String(aiCount);
        });
    });

    button.addEventListener("click", () => {
        const config = readConfig(root, toggles, aiCount);
        const message = validateConfig(config);
        if (message) {
            showError(message);
            return;
        }
        clearError();
        onStart(config);
    });

    updateBlindsForm();
    clearError();

    return {
        onStart(fn) {
            onStart = fn;
        },
        showError,
        clearError,
        setBusy(busy) {
            button.disabled = busy;
            const label = button.querySelector(".btn-label");
            if (label) label.textContent = busy ? "Starting…" : "Start game";
        },
        reset() {
            clearError();
        },
    };
}

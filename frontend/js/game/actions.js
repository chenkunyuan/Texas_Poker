import { getBetPreset, validateRaise } from "./betting.js";
import { findHuman } from "../state/game-state.js";

const ACTIONS = ["FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"];
const SHORTCUTS = Object.freeze({ F: "FOLD", C: "CHECK", A: "CALL", R: "RAISE", I: "ALL_IN" });
const FORM_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function requireElement(root, selector) {
    const element = root.querySelector(selector);
    if (!element) throw new Error(`Action controls require ${selector}.`);
    return element;
}

export function createActionControls(root = document) {
    const buttons = Object.fromEntries(ACTIONS.map((action) => [
        action,
        requireElement(root, `[data-action="${action}"]`),
    ]));
    const input = requireElement(root, "#raise-amount");
    const error = requireElement(root, "#raise-error");
    const callAmount = root.querySelector("#call-amount");
    const allInAmount = root.querySelector("#allin-amount");
    const presets = [...root.querySelectorAll("[data-fraction]")];
    const keyTarget = root.ownerDocument || root;

    let turn = null;
    let pot = 0;
    let humanChips = 0;
    let submit = () => {};
    let pending = false;

    const isLegal = (action) => Boolean(turn?.valid_actions?.[action]);

    const showRaiseError = () => {
        const message = turn && isLegal("RAISE")
            ? validateRaise(Number(input.value), Number(turn.min_raise || 0), Number(turn.max_raise || 0))
            : null;
        error.textContent = message || "";
        error.hidden = !message;
        input.setAttribute?.("aria-invalid", String(Boolean(message)));
        return message;
    };

    const renderAvailability = () => {
        for (const [action, button] of Object.entries(buttons)) {
            button.disabled = pending || !isLegal(action);
        }
        input.disabled = pending || !isLegal("RAISE");
        for (const preset of presets) preset.disabled = input.disabled;
    };

    const disable = () => {
        for (const button of Object.values(buttons)) button.disabled = true;
        input.disabled = true;
        for (const preset of presets) preset.disabled = true;
    };

    const act = (action) => {
        if (pending || !isLegal(action)) return;

        let amount = 0;
        if (action === "RAISE") {
            amount = Number(input.value);
            if (showRaiseError()) return;
        } else if (action === "CALL") {
            amount = Number(turn.call_amount || 0);
        } else if (action === "ALL_IN") {
            amount = humanChips;
        }

        error.hidden = true;
        pending = true;
        disable();
        submit(action, amount);
    };

    for (const [action, button] of Object.entries(buttons)) {
        button.addEventListener("click", () => act(action));
    }

    for (const preset of presets) {
        preset.addEventListener("click", () => {
            if (pending || !turn || !isLegal("RAISE")) return;
            input.value = String(getBetPreset(
                Number(preset.dataset.fraction),
                pot,
                Number(turn.min_raise || 0),
                Number(turn.max_raise || 0),
            ));
            showRaiseError();
        });
    }

    input.addEventListener("input", showRaiseError);

    keyTarget.addEventListener("keydown", (event) => {
        if (FORM_TAGS.has(String(event.target?.tagName || "").toUpperCase())) return;
        const action = SHORTCUTS[String(event.key || "").toUpperCase()];
        if (!action || buttons[action].disabled) return;
        event.preventDefault();
        buttons[action].click();
    });

    disable();

    return {
        onSubmit(fn) {
            submit = typeof fn === "function" ? fn : () => {};
        },
        setTurn(nextTurn, state) {
            turn = nextTurn || null;
            pot = Number(state?.pot || 0);
            const safeState = {
                ...state,
                players: Array.isArray(state?.players) ? state.players : [],
            };
            humanChips = Number(findHuman(safeState)?.chips || 0);
            pending = false;

            if (!turn) {
                disable();
                return;
            }

            const minRaise = Number(turn.min_raise || 0);
            const maxRaise = Number(turn.max_raise || minRaise);
            input.min = String(minRaise);
            input.max = String(maxRaise);
            input.value = String(minRaise);
            if (callAmount) callAmount.textContent = String(Number(turn.call_amount || 0));
            if (allInAmount) allInAmount.textContent = String(humanChips);
            error.textContent = "";
            error.hidden = true;
            input.setAttribute?.("aria-invalid", "false");
            renderAvailability();
        },
        setPending(value) {
            pending = Boolean(value);
            if (pending) disable();
        },
        disable,
    };
}

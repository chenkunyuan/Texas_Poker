import test from "node:test";
import assert from "node:assert/strict";

import { createActionControls } from "../js/game/actions.js";

class FakeElement {
    constructor({ id = "", action = "", fraction = "", tagName = "BUTTON" } = {}) {
        this.id = id;
        this.dataset = { action, fraction };
        this.tagName = tagName;
        this.disabled = false;
        this.hidden = true;
        this.value = "";
        this.textContent = "";
        this.listeners = new Map();
    }

    addEventListener(type, listener) {
        this.listeners.set(type, [...(this.listeners.get(type) || []), listener]);
    }

    dispatch(type, event = {}) {
        for (const listener of this.listeners.get(type) || []) listener({ target: this, ...event });
    }

    click() {
        if (!this.disabled) this.dispatch("click");
    }
}

class FakeDocument extends FakeElement {
    constructor() {
        super({ tagName: "DOCUMENT" });
        this.elements = new Map();
        this.actions = new Map();
        this.presets = [];
        for (const action of ["FOLD", "CHECK", "CALL", "RAISE", "ALL_IN"]) {
            this.actions.set(action, new FakeElement({ action }));
        }
        for (const id of ["raise-amount", "raise-error", "call-amount", "allin-amount"]) {
            this.elements.set(id, new FakeElement({ id, tagName: id === "raise-amount" ? "INPUT" : "SPAN" }));
        }
        for (const fraction of ["0.5", "0.75", "1"]) this.presets.push(new FakeElement({ fraction }));
        this.ownerDocument = this;
    }

    querySelector(selector) {
        const action = selector.match(/^\[data-action="(.+)"\]$/)?.[1];
        if (action) return this.actions.get(action) || null;
        if (selector.startsWith("#")) return this.elements.get(selector.slice(1)) || null;
        return null;
    }

    querySelectorAll(selector) {
        return selector === "[data-fraction]" ? this.presets : [];
    }

    keydown(key, target = new FakeElement({ tagName: "DIV" })) {
        let prevented = false;
        this.dispatch("keydown", { key, target, preventDefault() { prevented = true; } });
        return prevented;
    }
}

function createHarness() {
    const root = new FakeDocument();
    const controls = createActionControls(root);
    return { root, controls };
}

const gameState = {
    pot: 400,
    players: [{ id: "human", is_human: true, chips: 725 }],
};

const turn = {
    valid_actions: { FOLD: {}, CALL: {}, RAISE: {}, ALL_IN: {} },
    call_amount: 80,
    min_raise: 160,
    max_raise: 725,
};

test("setTurn enables only legal actions and fills action amounts", () => {
    const { root, controls } = createHarness();
    controls.setTurn(turn, gameState);

    assert.equal(root.actions.get("FOLD").disabled, false);
    assert.equal(root.actions.get("CHECK").disabled, true);
    assert.equal(root.actions.get("RAISE").disabled, false);
    assert.equal(root.elements.get("raise-amount").value, "160");
    assert.equal(root.elements.get("call-amount").textContent, "80");
    assert.equal(root.elements.get("allin-amount").textContent, "725");
});

test("pending state prevents rapid duplicate submissions", () => {
    const { root, controls } = createHarness();
    const submitted = [];
    controls.onSubmit((...args) => submitted.push(args));
    controls.setTurn(turn, gameState);

    root.actions.get("CALL").click();
    root.actions.get("CALL").click();

    assert.deepEqual(submitted, [["CALL", 80]]);
    assert.equal(root.actions.get("CALL").disabled, true);
});

test("clearing pending keeps the previous turn disabled until a new turn arrives", () => {
    const { root, controls } = createHarness();
    controls.setTurn(turn, gameState);
    root.actions.get("CALL").click();

    controls.setPending(false);

    for (const button of root.actions.values()) assert.equal(button.disabled, true);
    assert.equal(root.elements.get("raise-amount").disabled, true);
    assert.equal(root.presets.every((preset) => preset.disabled), true);

    controls.setTurn({ ...turn, valid_actions: { CHECK: {} } }, gameState);
    assert.equal(root.actions.get("CHECK").disabled, false);
    assert.equal(root.actions.get("CALL").disabled, true);
});

test("clearing the authoritative turn disables every action", () => {
    const { root, controls } = createHarness();
    controls.setTurn(turn, gameState);

    controls.setTurn(null, gameState);

    for (const button of root.actions.values()) assert.equal(button.disabled, true);
    assert.equal(root.elements.get("raise-amount").disabled, true);
    assert.equal(root.presets.every((preset) => preset.disabled), true);
});

test("raise presets clamp pot fractions and invalid raises stay inline", () => {
    const { root, controls } = createHarness();
    const submitted = [];
    controls.onSubmit((...args) => submitted.push(args));
    controls.setTurn(turn, gameState);

    root.presets[0].click();
    assert.equal(root.elements.get("raise-amount").value, "200");
    root.presets[1].click();
    assert.equal(root.elements.get("raise-amount").value, "300");
    root.presets[2].click();
    assert.equal(root.elements.get("raise-amount").value, "400");

    const input = root.elements.get("raise-amount");
    input.value = "100";
    input.dispatch("input");
    assert.equal(root.elements.get("raise-error").textContent, "Minimum raise is 160.");
    assert.equal(root.elements.get("raise-error").hidden, false);
    root.actions.get("RAISE").click();
    assert.deepEqual(submitted, []);

    input.value = "320";
    input.dispatch("input");
    root.actions.get("RAISE").click();
    assert.deepEqual(submitted, [["RAISE", 320]]);
});

test("fractional raises are rejected without submitting", () => {
    const { root, controls } = createHarness();
    const submitted = [];
    controls.onSubmit((...args) => submitted.push(args));
    controls.setTurn(turn, gameState);

    const input = root.elements.get("raise-amount");
    input.value = "320.5";
    input.dispatch("input");
    root.actions.get("RAISE").click();

    assert.equal(root.elements.get("raise-error").textContent, "Enter a whole-chip raise amount.");
    assert.equal(root.elements.get("raise-error").hidden, false);
    assert.deepEqual(submitted, []);
});

test("F/C/A/R/I shortcuts submit enabled actions with the correct amount", () => {
    const cases = [
        ["f", "FOLD", 0],
        ["c", "CHECK", 0],
        ["a", "CALL", 80],
        ["r", "RAISE", 160],
        ["i", "ALL_IN", 725],
    ];

    for (const [key, action, amount] of cases) {
        const { root, controls } = createHarness();
        const submitted = [];
        controls.onSubmit((...args) => submitted.push(args));
        controls.setTurn({
            ...turn,
            valid_actions: { ...turn.valid_actions, CHECK: {} },
        }, gameState);

        assert.equal(root.keydown(key), true);
        assert.deepEqual(submitted, [[action, amount]]);
    }
});

test("shortcuts ignore form focus and disabled actions", () => {
    const { root, controls } = createHarness();
    const submitted = [];
    controls.onSubmit((...args) => submitted.push(args));
    controls.setTurn(turn, gameState);

    assert.equal(root.keydown("f", root.elements.get("raise-amount")), false);
    assert.equal(root.keydown("c"), false);
    assert.deepEqual(submitted, []);
});

test("shortcuts ignore control, command, and alt key combinations", () => {
    for (const modifiers of [{ ctrlKey: true }, { metaKey: true }, { altKey: true }]) {
        const { root, controls } = createHarness();
        const submitted = [];
        controls.onSubmit((...args) => submitted.push(args));
        controls.setTurn({ ...turn, valid_actions: { ...turn.valid_actions, CHECK: {} } }, gameState);

        root.dispatch("keydown", {
            key: modifiers.metaKey ? "r" : "a",
            target: new FakeElement({ tagName: "DIV" }),
            preventDefault() {},
            ...modifiers,
        });
        assert.deepEqual(submitted, []);
    }
});

import test from "node:test";
import assert from "node:assert/strict";
import { loadPreferences, savePreferences } from "../js/state/preferences.js";

test("preferences default to sound off and expanded log", () => {
    const storage = { getItem: () => null, setItem() {} };
    assert.deepEqual(loadPreferences(storage), { soundEnabled: false, logCollapsed: false });
});

test("preferences round-trip through injected storage", () => {
    const values = new Map();
    const storage = {
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
    };
    savePreferences(storage, { soundEnabled: true, logCollapsed: true });
    assert.deepEqual(loadPreferences(storage), { soundEnabled: true, logCollapsed: true });
});

test("preferences fall back to defaults when storage access throws", () => {
    const storage = { getItem() { throw new Error("blocked"); } };
    assert.deepEqual(loadPreferences(storage), { soundEnabled: false, logCollapsed: false });
});

test("preferences fall back when the default localStorage getter throws", () => {
    const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
    Object.defineProperty(globalThis, "window", {
        configurable: true,
        get() { throw new Error("blocked"); },
    });
    try {
        assert.deepEqual(loadPreferences(), { soundEnabled: false, logCollapsed: false });
    } finally {
        if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
        else delete globalThis.window;
    }
});

test("saving preferences reports storage failures without throwing", () => {
    const storage = { setItem() { throw new Error("quota exceeded"); } };
    assert.equal(savePreferences(storage, { soundEnabled: true, logCollapsed: false }), false);
});

test("saving preferences reports success", () => {
    const storage = { setItem() {} };
    assert.equal(savePreferences(storage, { soundEnabled: true, logCollapsed: false }), true);
});

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

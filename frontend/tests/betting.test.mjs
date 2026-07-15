import test from "node:test";
import assert from "node:assert/strict";
import { getBetPreset, validateRaise } from "../js/game/betting.js";

test("getBetPreset rounds the pot fraction and clamps it", () => {
    assert.equal(getBetPreset(0.5, 480, 100, 1000), 240);
    assert.equal(getBetPreset(0.5, 100, 80, 1000), 80);
    assert.equal(getBetPreset(1, 2000, 80, 900), 900);
});

test("validateRaise explains invalid targets", () => {
    assert.equal(validateRaise(79, 80, 900), "Minimum raise is 80.");
    assert.equal(validateRaise(901, 80, 900), "Maximum raise is 900.");
    assert.equal(validateRaise(320.5, 80, 900), "Enter a whole-chip raise amount.");
    assert.equal(validateRaise(320, 80, 900), null);
});

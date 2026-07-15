import test from "node:test";
import assert from "node:assert/strict";
import { findHuman, normalizeGameState } from "../js/state/game-state.js";

test("normalizeGameState supplies render-safe defaults", () => {
    const state = normalizeGameState({ hand_number: 3, players: [{ id: "human", is_human: true }] });
    assert.equal(state.hand_number, 3);
    assert.deepEqual(state.community_cards, []);
    assert.deepEqual(state.action_history, []);
    assert.equal(findHuman(state).id, "human");
});

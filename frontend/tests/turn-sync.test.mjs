import test from "node:test";
import assert from "node:assert/strict";
import { createTurnSynchronizer } from "../js/state/turn-sync.js";

test("turns wait for a fresh game state before becoming actionable", () => {
    const sync = createTurnSynchronizer();
    const turn = { valid_actions: { CHECK: true } };

    sync.setConnection("connected");
    assert.equal(sync.receiveTurn(turn), null);
    assert.equal(sync.isSynchronized(), false);
    assert.equal(sync.receiveGameState(), turn);
    assert.equal(sync.isSynchronized(), true);
});

test("disconnect clears stale turns and caches only the latest reconnect turn", () => {
    const sync = createTurnSynchronizer();
    const staleTurn = { id: "stale" };
    const firstReconnectTurn = { id: "first" };
    const latestReconnectTurn = { id: "latest" };

    sync.receiveGameState();
    assert.equal(sync.receiveTurn(staleTurn), staleTurn);

    sync.setConnection("disconnected");
    assert.equal(sync.receiveTurn(firstReconnectTurn), null);
    assert.equal(sync.receiveTurn(latestReconnectTurn), null);
    assert.equal(sync.receiveGameState(), latestReconnectTurn);
});

test("reset drops a cached turn and requires another fresh game state", () => {
    const sync = createTurnSynchronizer();

    sync.receiveTurn({ id: "cached" });
    sync.reset();

    assert.equal(sync.receiveGameState(), null);
    assert.equal(sync.isSynchronized(), true);
});

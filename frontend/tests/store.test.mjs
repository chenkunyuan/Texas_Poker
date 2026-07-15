import test from "node:test";
import assert from "node:assert/strict";
import { createStore } from "../js/state/store.js";

test("store publishes immutable top-level updates", () => {
    const store = createStore();
    let published;
    store.subscribe((state) => { published = state; });
    store.update({ connection: "connected", pendingAction: true });
    assert.equal(published.connection, "connected");
    assert.equal(published.pendingAction, true);
});

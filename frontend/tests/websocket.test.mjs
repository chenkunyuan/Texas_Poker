import test from "node:test";
import assert from "node:assert/strict";
import { createWebSocketClient } from "../js/services/websocket.js";

class FakeWebSocket {
    static OPEN = 1;
    static instances = [];

    constructor(url) {
        this.url = url;
        this.readyState = 0;
        this.sent = [];
        FakeWebSocket.instances.push(this);
    }

    open() {
        this.readyState = FakeWebSocket.OPEN;
        this.onopen?.();
    }

    send(message) {
        this.sent.push(message);
    }

    close() {
        this.readyState = 3;
        if (!this.deferClose) this.onclose?.();
    }

    flushClose() {
        this.onclose?.();
    }
}

function resetSockets() {
    FakeWebSocket.instances = [];
}

function withTimeout(promise, milliseconds = 50) {
    return Promise.race([
        promise,
        new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error("Timed out waiting for connection.")), milliseconds);
        }),
    ]);
}

test("websocket client publishes connection states", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 1 });
    const states = [];
    client.on("connection", ({ status }) => states.push(status));

    const connected = client.connect("ws://example.test/game");
    assert.deepEqual(states, ["connecting"]);
    FakeWebSocket.instances[0].open();
    await withTimeout(connected);

    assert.equal(client.isConnected(), true);
    assert.deepEqual(states, ["connecting", "connected"]);
});

test("websocket client sends only while connected", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 1 });
    const connected = client.connect("ws://example.test/game");

    assert.equal(client.send({ type: "before_open" }), false);
    FakeWebSocket.instances[0].open();
    await connected;
    assert.equal(client.send({ type: "player_action", action: "CHECK" }), true);
    assert.deepEqual(FakeWebSocket.instances[0].sent, [
        JSON.stringify({ type: "player_action", action: "CHECK" }),
    ]);
});

test("manual close does not reconnect", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 1 });
    const connected = client.connect("ws://example.test/game");
    FakeWebSocket.instances[0].open();
    await connected;

    client.close();
    await new Promise((resolve) => setTimeout(resolve, 10));

    assert.equal(client.isConnected(), false);
    assert.equal(FakeWebSocket.instances.length, 1);
});

test("manual close cancels a reconnect already scheduled after disconnect", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 5 });
    const connected = client.connect("ws://example.test/game");
    FakeWebSocket.instances[0].open();
    await connected;

    FakeWebSocket.instances[0].close();
    client.close();
    await new Promise((resolve) => setTimeout(resolve, 20));

    assert.equal(FakeWebSocket.instances.length, 1);
});

test("the original connect promise resolves after a retry succeeds", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, maxRetries: 1, retryDelay: 1 });
    const connected = client.connect("ws://example.test/game");

    FakeWebSocket.instances[0].close();
    await new Promise((resolve) => setTimeout(resolve, 10));
    FakeWebSocket.instances[1].open();

    await withTimeout(connected);
    assert.equal(client.isConnected(), true);
});

test("connect rejects after retries are exhausted", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, maxRetries: 1, retryDelay: 1 });
    const connected = client.connect("ws://example.test/game");

    FakeWebSocket.instances[0].close();
    await new Promise((resolve) => setTimeout(resolve, 10));
    FakeWebSocket.instances[1].close();

    await assert.rejects(withTimeout(connected), /failed after 2 attempts/i);
});

test("a stale close cannot replace a newer connection", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 1 });
    const firstConnection = client.connect("ws://example.test/first");
    const oldSocket = FakeWebSocket.instances[0];
    oldSocket.open();
    await firstConnection;

    oldSocket.deferClose = true;
    client.close();
    const secondConnection = client.connect("ws://example.test/second");
    const newSocket = FakeWebSocket.instances[1];
    newSocket.open();
    await secondConnection;
    oldSocket.flushClose();
    await new Promise((resolve) => setTimeout(resolve, 10));

    assert.equal(FakeWebSocket.instances.length, 2);
    assert.equal(client.isConnected(), true);
    assert.equal(client.send({ type: "current" }), true);
    assert.deepEqual(newSocket.sent, [JSON.stringify({ type: "current" })]);
});

test("closing from a connecting handler does not create a ghost socket", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 1 });
    client.on("connection", ({ status }) => {
        if (status === "connecting") client.close();
    });

    const connected = client.connect("ws://example.test/game");

    await assert.rejects(connected, /closed/i);
    assert.equal(FakeWebSocket.instances.length, 0);
    assert.equal(client.isConnected(), false);
});

test("a throwing connection handler does not block connection or later handlers", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket });
    let laterHandlerCalls = 0;
    client.on("connection", ({ status }) => {
        if (status === "connected") throw new Error("handler failed");
    });
    client.on("connection", ({ status }) => {
        if (status === "connected") laterHandlerCalls += 1;
    });
    const originalConsoleError = console.error;
    console.error = () => {};
    try {
        const connected = client.connect("ws://example.test/game");
        assert.doesNotThrow(() => FakeWebSocket.instances[0].open());
        await withTimeout(connected);
    } finally {
        console.error = originalConsoleError;
    }

    assert.equal(laterHandlerCalls, 1);
    assert.equal(client.isConnected(), true);
});

test("a throwing message handler does not become a protocol error or block peers", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket });
    let laterHandlerCalls = 0;
    let protocolErrors = 0;
    client.on("game_state", () => { throw new Error("handler failed"); });
    client.on("game_state", () => { laterHandlerCalls += 1; });
    client.on("protocol_error", () => { protocolErrors += 1; });
    const connected = client.connect("ws://example.test/game");
    FakeWebSocket.instances[0].open();
    await connected;

    const originalConsoleError = console.error;
    console.error = () => {};
    try {
        FakeWebSocket.instances[0].onmessage({ data: JSON.stringify({ type: "game_state" }) });
    } finally {
        console.error = originalConsoleError;
    }

    assert.equal(laterHandlerCalls, 1);
    assert.equal(protocolErrors, 0);
});

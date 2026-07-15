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
        this.onclose?.();
    }
}

function resetSockets() {
    FakeWebSocket.instances = [];
}

test("websocket client publishes connection states", async () => {
    resetSockets();
    const client = createWebSocketClient({ WebSocketImpl: FakeWebSocket, retryDelay: 1 });
    const states = [];
    client.on("connection", ({ status }) => states.push(status));

    const connected = client.connect("ws://example.test/game");
    assert.deepEqual(states, ["connecting"]);
    FakeWebSocket.instances[0].open();
    await connected;

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

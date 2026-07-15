import test from "node:test";
import assert from "node:assert/strict";

import { createActionLog } from "../js/game/action-log.js";
import { createStatusView } from "../js/game/status.js";

class FakeClassList {
    constructor() {
        this.values = new Set();
    }

    toggle(name, force) {
        if (force) this.values.add(name);
        else this.values.delete(name);
    }

    contains(name) {
        return this.values.has(name);
    }
}

class FakeElement {
    constructor(ownerDocument) {
        this.ownerDocument = ownerDocument;
        this.children = [];
        this.className = "";
        this.classList = new FakeClassList();
        this.dataset = {};
        this.hidden = false;
        this.listeners = new Map();
        this.scrollHeight = 0;
        this.scrollTop = 0;
        this.textContent = "";
    }

    appendChild(child) {
        child.parentElement = this;
        this.children.push(child);
        this.scrollHeight = this.children.length;
        return child;
    }

    get firstElementChild() {
        return this.children[0] || null;
    }

    remove() {
        const index = this.parentElement.children.indexOf(this);
        this.parentElement.children.splice(index, 1);
    }

    replaceChildren(...children) {
        this.children = [...children];
    }

    addEventListener(type, listener) {
        this.listeners.set(type, listener);
    }

    click() {
        this.listeners.get("click")?.();
    }
}

class FakeDocument {
    constructor(ids) {
        this.elements = new Map(ids.map((id) => [id, new FakeElement(this)]));
    }

    createElement() {
        return new FakeElement(this);
    }

    querySelector(selector) {
        return this.elements.get(selector.slice(1)) || null;
    }
}

function createLogHarness() {
    const root = new FakeDocument(["action-log", "action-log-panel"]);
    return { root, log: createActionLog(root), list: root.elements.get("action-log") };
}

function createStatusHarness() {
    const root = new FakeDocument([
        "connection-status", "error-banner", "error-message", "live-announcer", "btn-dismiss-error",
    ]);
    const frames = [];
    return { root, frames, status: createStatusView(root, (callback) => frames.push(callback)) };
}

test("action log renders player, result, and system text without interpreting markup", () => {
    const { log, list } = createLogHarness();

    log.append({ type: "player_action", player_name: "<img src=x>", action: "RAISE", amount: 1200 });
    log.append({ type: "hand_result", winners: [{ player_name: "<b>Alice</b>" }] });
    log.append({ message: "<script>alert(1)</script>" });

    assert.deepEqual(list.children.map((entry) => entry.textContent), [
        "<img src=x> raise 1,200",
        "Winner: <b>Alice</b>",
        "<script>alert(1)</script>",
    ]);
    assert.deepEqual(list.children.map((entry) => entry.children.length), [0, 0, 0]);
});

test("action log retains only the latest 100 entries", () => {
    const { log, list } = createLogHarness();
    for (let index = 0; index < 105; index += 1) log.append({ message: `Update ${index}` });

    assert.equal(list.children.length, 100);
    assert.equal(list.firstElementChild.textContent, "Update 5");
    assert.equal(list.scrollTop, list.scrollHeight);
});

test("collapse toggles only the panel state", () => {
    const { root, log, list } = createLogHarness();
    log.append({ message: "Visible history" });

    log.setCollapsed(true);
    assert.equal(root.elements.get("action-log-panel").classList.contains("is-collapsed"), true);
    assert.equal(list.children.length, 1);

    log.setCollapsed(false);
    assert.equal(root.elements.get("action-log-panel").classList.contains("is-collapsed"), false);
});

test("connection statuses provide text and data-status", () => {
    const { root, status } = createStatusHarness();
    const connection = root.elements.get("connection-status");
    const expected = {
        connected: "Connected",
        connecting: "Connecting…",
        reconnecting: "Reconnecting…",
        disconnected: "Disconnected",
        error: "Connection error",
    };

    for (const [value, label] of Object.entries(expected)) {
        status.setConnection(value);
        assert.equal(connection.dataset.status, value);
        assert.equal(connection.textContent, label);
    }
});

test("errors can be shown, cleared, and dismissed", () => {
    const { root, status } = createStatusHarness();
    const banner = root.elements.get("error-banner");
    const message = root.elements.get("error-message");

    status.showError("<strong>Disconnected</strong>");
    assert.equal(message.textContent, "<strong>Disconnected</strong>");
    assert.equal(banner.hidden, false);

    root.elements.get("btn-dismiss-error").click();
    assert.equal(banner.hidden, true);

    status.clearError();
    assert.equal(message.textContent, "");
    assert.equal(banner.hidden, true);
});

test("announcements clear immediately and update on the next frame", () => {
    const { root, frames, status } = createStatusHarness();
    const announcer = root.elements.get("live-announcer");
    announcer.textContent = "Previous action";

    status.announce("Your turn");
    assert.equal(announcer.textContent, "");
    assert.equal(frames.length, 1);

    frames.shift()();
    assert.equal(announcer.textContent, "Your turn");
});

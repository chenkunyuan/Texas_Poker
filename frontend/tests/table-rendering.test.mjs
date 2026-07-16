import test from "node:test";
import assert from "node:assert/strict";

import { renderCards } from "../js/game/cards.js";
import { renderPlayers } from "../js/game/players.js";
import { createTableView } from "../js/game/table.js";

class FakeElement {
    constructor(ownerDocument, tagName = "div") {
        this.ownerDocument = ownerDocument;
        this.tagName = tagName.toUpperCase();
        this.children = [];
        this.attributes = new Map();
        this.className = "";
        this.hidden = false;
        this.style = {};
        this._textContent = "";
    }

    appendChild(child) {
        this.children.push(child);
        return child;
    }

    replaceChildren(...children) {
        this.children = [...children];
        this._textContent = "";
    }

    setAttribute(name, value) {
        this.attributes.set(name, String(value));
    }

    getAttribute(name) {
        return this.attributes.get(name) ?? null;
    }

    set textContent(value) {
        this._textContent = String(value);
        this.children = [];
    }

    get textContent() {
        return this._textContent + this.children.map((child) => child.textContent).join("");
    }
}

class FakeDocument {
    createElement(tagName) {
        return new FakeElement(this, tagName);
    }
}

function findByClass(element, className) {
    if (element.className.split(/\s+/).includes(className)) return element;
    for (const child of element.children) {
        const match = findByClass(child, className);
        if (match) return match;
    }
    return null;
}

test("renderCards creates safe card faces and empty slots", () => {
    const document = new FakeDocument();
    const container = document.createElement("div");

    renderCards(container, [{ rank: "<img src=x>", suit: "hearts" }], { placeholders: 2 });

    assert.equal(container.children.length, 2);
    assert.equal(container.children[0].className, "card suit-red");
    assert.equal(findByClass(container.children[0], "card-rank").textContent, "<img src=x>");
    assert.equal(findByClass(container.children[0], "card-suit").textContent, "♥");
    assert.equal(container.children[1].className, "card-slot empty");
});

test("renderCards supports face-down cards", () => {
    const document = new FakeDocument();
    const container = document.createElement("div");

    renderCards(container, [{ rank: "A", suit: "SPADES" }], { faceDown: true });

    assert.equal(container.children[0].className, "card face-down");
    assert.equal(container.children[0].children.length, 0);
});

test("renderPlayers marks seat state and shows only the latest action", () => {
    const document = new FakeDocument();
    const container = document.createElement("div");
    const state = {
        players: [
            { id: "human", name: "<b>Alice</b>", is_human: true, is_active: true, chips: 1840, total_bet_this_round: 1250 },
            { id: "bot", name: "Nova", is_active: false, chips: 940 },
        ],
        dealer_index: 0,
        current_player_index: 0,
        action_history: [
            { player_id: "human", action: "check", amount: 0 },
            { player_id: "human", action: "raise", amount: 160 },
            { player_id: "bot", action: "fold", amount: 0 },
        ],
    };

    renderPlayers(container, state);

    assert.equal(container.children.length, 2);
    assert.equal(container.children[0].getAttribute("data-player-id"), "human");
    assert.equal(container.children[0].style.left, "50%");
    assert.equal(container.children[0].style.top, "86%");
    assert.match(container.children[0].className, /is-active/);
    assert.match(container.children[1].className, /is-folded/);
    assert.match(container.children[0].textContent, /<b>Alice<\/b>/);
    assert.match(container.children[0].textContent, /1,840 chips/);
    assert.equal(findByClass(container.children[0], "seat-contribution").textContent, "Hand in 1,250");
    assert.equal(findByClass(container.children[1], "seat-contribution").textContent, "Hand in 0");
    assert.match(container.children[0].textContent, /Raise 160/);
    assert.doesNotMatch(container.children[0].textContent, /Check/);
    assert.equal(findByClass(container.children[0], "dealer-marker").textContent, "D");
});

test("renderPlayers normalizes invalid hand contributions", () => {
    const document = new FakeDocument();
    const container = document.createElement("div");

    renderPlayers(container, {
        players: [
            { id: "text", name: "Text", chips: 100, total_bet_this_round: "not-a-number" },
            { id: "infinite", name: "Infinite", chips: 100, total_bet_this_round: Infinity },
            { id: "negative", name: "Negative", chips: 100, total_bet_this_round: -25 },
        ],
    });

    assert.equal(findByClass(container.children[0], "seat-contribution").textContent, "Hand in 0");
    assert.equal(findByClass(container.children[1], "seat-contribution").textContent, "Hand in 0");
    assert.equal(findByClass(container.children[2], "seat-contribution").textContent, "Hand in 0");
});

test("createTableView renders normalized regions and thinking state", () => {
    const document = new FakeDocument();
    const elements = Object.fromEntries([
        "community-cards", "player-spots", "hand-panel", "pot-label",
        "thinking-indicator", "thinking-text",
    ].map((id) => [`#${id}`, document.createElement("div")]));
    const root = { querySelector: (selector) => elements[selector] };
    const table = createTableView(root);

    table.render({
        community_cards: [{ rank: "A", suit: "diamonds" }],
        players: [{ id: "human", name: "Player", is_human: true, is_active: true, chips: 1000, hole_cards: [{ rank: "K", suit: "clubs" }] }],
        action_history: [],
        dealer_index: 0,
        current_player_index: null,
        pot: 1234,
    });
    table.showThinking("<script>alert(1)</script>");

    assert.equal(elements["#community-cards"].children.length, 5);
    assert.equal(elements["#pot-label"].textContent, "Pot 1,234");
    assert.equal(elements["#hand-panel"].children[0].textContent, "Your hand");
    assert.equal(findByClass(elements["#hand-panel"], "hole-cards").children.length, 2);
    assert.equal(elements["#thinking-text"].textContent, "<script>alert(1)</script> is thinking…");
    assert.equal(elements["#thinking-indicator"].hidden, false);

    table.hideThinking();
    assert.equal(elements["#thinking-indicator"].hidden, true);
});

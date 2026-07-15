import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const index = readFileSync(new URL("../index.html", import.meta.url), "utf8");

function actionDock(html) {
    return html.match(/<footer id="action-bar"[\s\S]*?<\/footer>/)?.[0].replace(/\s+/g, " ").trim();
}

function ids(html) {
    return [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
}

test("the application includes the complete action dock", () => {
    for (const selector of [
        'data-action="FOLD"', 'data-action="CHECK"', 'data-action="CALL"',
        'data-action="RAISE"', 'data-action="ALL_IN"', 'id="raise-amount"',
        'id="raise-error"', 'data-fraction="0.5"', 'data-fraction="0.75"',
        'data-fraction="1"', 'id="call-amount"', 'id="allin-amount"',
    ]) assert.match(actionDock(index), new RegExp(selector.replace(".", "\\.")));
});

test("the application markup has unique ids and one module entry point", () => {
    const allIds = ids(index);
    assert.equal(new Set(allIds).size, allIds.length);
    assert.equal((index.match(/<script\b/g) || []).length, 1);
    assert.match(index, /<script type="module" src="\/static\/js\/app\.js"><\/script>/);
});

test("the shared error banner is outside every hidden application view", () => {
    const bannerPosition = index.indexOf('id="error-banner"');
    const firstViewPosition = Math.min(
        index.indexOf('id="setup-view"'),
        index.indexOf('id="game-view"'),
        index.indexOf('id="results-view"'),
    );

    assert.notEqual(bannerPosition, -1);
    assert.ok(bannerPosition < firstViewPosition);
});

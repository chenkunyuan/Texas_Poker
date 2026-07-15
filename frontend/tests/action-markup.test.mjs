import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const index = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const preview = readFileSync(new URL("../design-preview.html", import.meta.url), "utf8");

function actionDock(html) {
    return html.match(/<footer id="action-bar"[\s\S]*?<\/footer>/)?.[0].replace(/\s+/g, " ").trim();
}

function ids(html) {
    return [...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]);
}

test("the preview and application use the same complete action dock", () => {
    assert.equal(actionDock(preview), actionDock(index));
    for (const selector of [
        'data-action="FOLD"', 'data-action="CHECK"', 'data-action="CALL"',
        'data-action="RAISE"', 'data-action="ALL_IN"', 'id="raise-amount"',
        'id="raise-error"', 'data-fraction="0.5"', 'data-fraction="0.75"',
        'data-fraction="1"', 'id="call-amount"', 'id="allin-amount"',
    ]) assert.match(actionDock(preview), new RegExp(selector.replace(".", "\\.")));
});

test("the preview and application markup have unique ids", () => {
    for (const html of [index, preview]) {
        const allIds = ids(html);
        assert.equal(new Set(allIds).size, allIds.length);
    }
});

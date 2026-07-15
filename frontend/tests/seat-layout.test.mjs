import test from "node:test";
import assert from "node:assert/strict";
import { getSeatPositions } from "../js/game/seat-layout.js";

test("the human seat remains centered at the bottom", () => {
    for (const count of [2, 6, 9]) {
        const positions = getSeatPositions(count);
        assert.equal(positions.length, count);
        assert.deepEqual(positions[0], { x: 50, y: 86 });
    }
});

import test from "node:test";
import assert from "node:assert/strict";

import { createSoundService } from "../js/services/sound.js";

class FakeAudioContext {
    static instances = [];
    static rejectResume = false;
    static rejectClose = false;

    constructor() {
        this.currentTime = 10;
        this.destination = {};
        this.events = [];
        this.state = "suspended";
        this.resumeCalls = 0;
        this.closeCalls = 0;
        this.oscillatorCount = 0;
        FakeAudioContext.instances.push(this);
    }

    resume() {
        this.resumeCalls += 1;
        if (FakeAudioContext.rejectResume) return Promise.reject(new Error("resume blocked"));
        this.state = "running";
        return Promise.resolve();
    }

    close() {
        this.closeCalls += 1;
        if (FakeAudioContext.rejectClose) return Promise.reject(new Error("close blocked"));
        this.state = "closed";
        return Promise.resolve();
    }

    createOscillator() {
        const context = this;
        this.oscillatorCount += 1;
        const oscillator = {
            frequency: { value: 0 },
            connect(node) { context.oscillatorTarget = node; return node; },
            start() { context.events.push(["start"]); },
            stop(time) { context.events.push(["stop", time]); },
        };
        context.oscillator = oscillator;
        return oscillator;
    }

    createGain() {
        const context = this;
        return {
            gain: {
                setValueAtTime(value, time) { context.events.push(["gain", value, time]); },
                exponentialRampToValueAtTime(value, time) { context.events.push(["ramp", value, time]); },
            },
            connect(destination) { context.gainTarget = destination; return destination; },
        };
    }
}

test("sound defaults off and does not allocate audio until enabled", () => {
    FakeAudioContext.instances.length = 0;
    const sound = createSoundService(FakeAudioContext);

    assert.equal(sound.isEnabled(), false);
    sound.play("turn");
    assert.equal(FakeAudioContext.instances.length, 0);
});

test("sound plays a short Web Audio cue with the requested frequency", () => {
    FakeAudioContext.instances.length = 0;
    const sound = createSoundService(FakeAudioContext);
    sound.setEnabled(true);

    assert.equal(FakeAudioContext.instances.length, 1);
    assert.equal(FakeAudioContext.instances[0].resumeCalls, 1);
    sound.play("turn");

    const context = FakeAudioContext.instances[0];
    assert.equal(context.resumeCalls, 1);
    assert.equal(context.oscillator.frequency.value, 660);
    assert.equal(context.oscillatorTarget !== undefined, true);
    assert.deepEqual(context.events.at(-1), ["stop", 10.12]);
    assert.deepEqual(context.events[0], ["gain", 0.04, 10]);
});

test("sound reuses one context and closes it when disabled", () => {
    FakeAudioContext.instances.length = 0;
    const sound = createSoundService(FakeAudioContext);
    sound.setEnabled(true);

    sound.play("turn");
    sound.play("action");

    assert.equal(FakeAudioContext.instances.length, 1);
    assert.equal(FakeAudioContext.instances[0].oscillatorCount, 2);
    sound.setEnabled(false);
    assert.equal(FakeAudioContext.instances[0].closeCalls, 1);

    sound.setEnabled(true);
    sound.play("turn");
    assert.equal(FakeAudioContext.instances.length, 2);
});

test("sound handles rejected resume and close promises without leaking rejections", async () => {
    FakeAudioContext.instances.length = 0;
    FakeAudioContext.rejectResume = true;
    FakeAudioContext.rejectClose = true;
    const unhandled = [];
    const onUnhandled = (error) => unhandled.push(error);
    process.on("unhandledRejection", onUnhandled);

    try {
        const sound = createSoundService(FakeAudioContext);
        assert.doesNotThrow(() => sound.setEnabled(true));
        assert.equal(FakeAudioContext.instances.length, 1);
        assert.equal(FakeAudioContext.instances[0].resumeCalls, 1);

        sound.play("turn");
        assert.equal(FakeAudioContext.instances[0].resumeCalls, 2);
        assert.doesNotThrow(() => sound.setEnabled(false));
        await new Promise((resolve) => setTimeout(resolve, 0));

        assert.deepEqual(unhandled, []);
    } finally {
        process.off("unhandledRejection", onUnhandled);
        FakeAudioContext.rejectResume = false;
        FakeAudioContext.rejectClose = false;
    }
});

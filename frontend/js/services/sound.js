export function createSoundService(
    AudioContextImpl = globalThis.AudioContext || globalThis.webkitAudioContext,
) {
    let enabled = false;

    return {
        setEnabled(value) {
            enabled = Boolean(value);
        },
        isEnabled() {
            return enabled;
        },
        play(kind) {
            if (!enabled || !AudioContextImpl) return;

            const context = new AudioContextImpl();
            const oscillator = context.createOscillator();
            const gain = context.createGain();
            const duration = 0.12;

            oscillator.frequency.value = kind === "turn" ? 660 : 440;
            gain.gain.setValueAtTime(0.04, context.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + duration);
            oscillator.connect(gain).connect(context.destination);
            oscillator.start();
            oscillator.stop(context.currentTime + duration);
        },
    };
}

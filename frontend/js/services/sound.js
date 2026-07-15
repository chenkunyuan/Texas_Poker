export function createSoundService(
    AudioContextImpl = globalThis.AudioContext || globalThis.webkitAudioContext,
) {
    let enabled = false;
    let context = null;

    return {
        setEnabled(value) {
            enabled = Boolean(value);
            if (!enabled && context) {
                context.close?.();
                context = null;
            }
        },
        isEnabled() {
            return enabled;
        },
        play(kind) {
            if (!enabled || !AudioContextImpl) return;

            if (!context || context.state === "closed") context = new AudioContextImpl();
            if (context.state === "suspended") context.resume?.();
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

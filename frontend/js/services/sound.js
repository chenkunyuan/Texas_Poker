export function createSoundService(
    AudioContextImpl = globalThis.AudioContext || globalThis.webkitAudioContext,
) {
    let enabled = false;
    let context = null;

    const ignoreRejection = (result) => result?.catch?.(() => {});
    const resumeContext = () => {
        if (context?.state !== "suspended") return;
        try {
            ignoreRejection(context.resume?.());
        } catch {
            // Browsers may reject audio unlock outside an accepted gesture.
        }
    };
    const getContext = () => {
        if (!AudioContextImpl) return null;
        if (!context || context.state === "closed") context = new AudioContextImpl();
        resumeContext();
        return context;
    };

    return {
        setEnabled(value) {
            enabled = Boolean(value);
            if (enabled) {
                getContext();
            } else if (context) {
                const previousContext = context;
                context = null;
                try {
                    ignoreRejection(previousContext.close?.());
                } catch {
                    // The preference is still disabled even if cleanup fails.
                }
            }
        },
        isEnabled() {
            return enabled;
        },
        play(kind) {
            if (!enabled || !AudioContextImpl) return;

            const activeContext = getContext();
            if (!activeContext) return;
            const oscillator = activeContext.createOscillator();
            const gain = activeContext.createGain();
            const duration = 0.12;

            oscillator.frequency.value = kind === "turn" ? 660 : 440;
            gain.gain.setValueAtTime(0.04, activeContext.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, activeContext.currentTime + duration);
            oscillator.connect(gain).connect(activeContext.destination);
            oscillator.start();
            oscillator.stop(activeContext.currentTime + duration);
        },
    };
}

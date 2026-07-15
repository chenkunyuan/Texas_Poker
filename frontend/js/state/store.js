const INITIAL = Object.freeze({
    game: null,
    turn: null,
    connection: "disconnected",
    pendingAction: false,
    error: null,
    thinkingPlayer: null,
});

export function createStore() {
    let state = { ...INITIAL };
    const listeners = new Set();

    return {
        getState: () => state,
        update(patch) {
            state = Object.freeze({ ...state, ...patch });
            listeners.forEach((fn) => fn(state));
        },
        subscribe(fn) {
            listeners.add(fn);
            return () => listeners.delete(fn);
        },
        reset() {
            state = { ...INITIAL };
            listeners.forEach((fn) => fn(state));
        },
    };
}

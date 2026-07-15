export function createTurnSynchronizer() {
    let synchronized = false;
    let cachedTurn = null;

    const markUnsynchronized = () => {
        synchronized = false;
        cachedTurn = null;
    };

    return {
        isSynchronized: () => synchronized,
        setConnection(status) {
            if (status !== "connected") markUnsynchronized();
        },
        receiveTurn(turn) {
            if (synchronized) return turn;
            cachedTurn = turn;
            return null;
        },
        receiveGameState() {
            synchronized = true;
            const turn = cachedTurn;
            cachedTurn = null;
            return turn;
        },
        reset: markUnsynchronized,
    };
}

export function createWebSocketClient({
    WebSocketImpl = WebSocket,
    maxRetries = 5,
    retryDelay = 2000,
} = {}) {
    const handlers = new Map();
    let socket = null;
    let manualClose = false;
    let attempts = 0;
    let reconnectTimer = null;
    let generation = 0;
    let connectionRequest = null;

    const emit = (type, payload = {}) => {
        (handlers.get(type) || []).forEach((fn) => {
            try {
                fn(payload);
            } catch (error) {
                console.error(`WebSocket handler failed for ${type}.`, error);
            }
        });
    };
    const on = (type, fn) => {
        handlers.set(type, [...(handlers.get(type) || []), fn]);
    };
    const clearReconnectTimer = () => {
        if (reconnectTimer === null) return;
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    };
    const resolveConnection = (currentGeneration) => {
        if (connectionRequest?.generation !== currentGeneration) return;
        const { resolve } = connectionRequest;
        connectionRequest = null;
        resolve();
    };
    const rejectConnection = (currentGeneration, error) => {
        if (connectionRequest?.generation !== currentGeneration) return;
        const { reject } = connectionRequest;
        connectionRequest = null;
        reject(error);
    };
    const openSocket = (currentGeneration, targetUrl) => {
        if (currentGeneration !== generation || manualClose) return;
        emit("connection", { status: attempts ? "reconnecting" : "connecting" });
        if (currentGeneration !== generation || manualClose) return;
        let candidate;
        try {
            candidate = new WebSocketImpl(targetUrl);
            socket = candidate;
        } catch (error) {
            rejectConnection(currentGeneration, error);
            return;
        }
        const isCurrent = () => (
            currentGeneration === generation
            && candidate === socket
            && !manualClose
        );
        candidate.onopen = () => {
            if (!isCurrent()) return;
            attempts = 0;
            emit("connection", { status: "connected" });
            resolveConnection(currentGeneration);
        };
        candidate.onmessage = (event) => {
            if (!isCurrent()) return;
            let message;
            try {
                message = JSON.parse(event.data);
            } catch {
                emit("protocol_error", { message: "Invalid server message." });
                return;
            }
            emit(message.type || "_unknown", message);
        };
        candidate.onerror = () => {
            if (isCurrent()) emit("connection", { status: "error" });
        };
        candidate.onclose = () => {
            if (!isCurrent()) return;
            socket = null;
            emit("connection", { status: "disconnected" });
            if (!manualClose && attempts < maxRetries) {
                attempts += 1;
                reconnectTimer = setTimeout(() => {
                    reconnectTimer = null;
                    if (currentGeneration === generation && !manualClose) {
                        openSocket(currentGeneration, targetUrl);
                    }
                }, retryDelay);
            } else {
                rejectConnection(
                    currentGeneration,
                    new Error(`WebSocket connection failed after ${attempts + 1} attempts.`),
                );
            }
        };
    };
    const connect = (nextUrl) => {
        clearReconnectTimer();
        generation += 1;
        const currentGeneration = generation;
        const previousSocket = socket;
        socket = null;
        if (connectionRequest) {
            connectionRequest.reject(new Error("WebSocket connection was superseded."));
            connectionRequest = null;
        }
        previousSocket?.close();
        manualClose = false;
        attempts = 0;
        return new Promise((resolve, reject) => {
            connectionRequest = { generation: currentGeneration, resolve, reject };
            openSocket(currentGeneration, nextUrl);
        });
    };

    return {
        connect,
        on,
        send(message) {
            if (!socket || socket.readyState !== WebSocketImpl.OPEN) return false;
            socket.send(JSON.stringify(message));
            return true;
        },
        close() {
            manualClose = true;
            generation += 1;
            clearReconnectTimer();
            if (connectionRequest) {
                connectionRequest.reject(new Error("WebSocket connection was closed."));
                connectionRequest = null;
            }
            const currentSocket = socket;
            socket = null;
            currentSocket?.close();
        },
        isConnected: () => socket?.readyState === WebSocketImpl.OPEN,
    };
}

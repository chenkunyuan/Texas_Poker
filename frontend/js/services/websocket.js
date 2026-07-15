export function createWebSocketClient({
    WebSocketImpl = WebSocket,
    maxRetries = 5,
    retryDelay = 2000,
} = {}) {
    const handlers = new Map();
    let socket = null;
    let url = "";
    let manualClose = false;
    let attempts = 0;
    let reconnectTimer = null;

    const emit = (type, payload = {}) => {
        (handlers.get(type) || []).forEach((fn) => fn(payload));
    };
    const on = (type, fn) => {
        handlers.set(type, [...(handlers.get(type) || []), fn]);
    };
    const connect = (nextUrl) => new Promise((resolve, reject) => {
        url = nextUrl;
        manualClose = false;
        emit("connection", { status: attempts ? "reconnecting" : "connecting" });
        try {
            socket = new WebSocketImpl(url);
        } catch (error) {
            reject(error);
            return;
        }
        socket.onopen = () => {
            attempts = 0;
            emit("connection", { status: "connected" });
            resolve();
        };
        socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                emit(message.type || "_unknown", message);
            } catch {
                emit("protocol_error", { message: "Invalid server message." });
            }
        };
        socket.onerror = () => emit("connection", { status: "error" });
        socket.onclose = () => {
            emit("connection", { status: "disconnected" });
            if (!manualClose && attempts < maxRetries) {
                attempts += 1;
                reconnectTimer = setTimeout(() => {
                    reconnectTimer = null;
                    if (!manualClose) connect(url).catch(() => {});
                }, retryDelay);
            }
        };
    });

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
            if (reconnectTimer !== null) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            socket?.close();
            socket = null;
        },
        isConnected: () => socket?.readyState === WebSocketImpl.OPEN,
    };
}

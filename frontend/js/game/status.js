const CONNECTION_LABELS = {
    connected: "Connected",
    connecting: "Connecting…",
    reconnecting: "Reconnecting…",
    disconnected: "Disconnected",
    error: "Connection error",
};

export function createStatusView(root = document, scheduleFrame = globalThis.requestAnimationFrame) {
    const connection = root.querySelector("#connection-status");
    const banner = root.querySelector("#error-banner");
    const message = root.querySelector("#error-message");
    const announcer = root.querySelector("#live-announcer");

    root.querySelector("#btn-dismiss-error").addEventListener("click", () => {
        banner.hidden = true;
    });

    return {
        setConnection(status) {
            connection.dataset.status = status;
            connection.textContent = CONNECTION_LABELS[status] || status;
        },
        showError(text) {
            message.textContent = text;
            banner.hidden = false;
        },
        clearError() {
            message.textContent = "";
            banner.hidden = true;
        },
        announce(text) {
            announcer.textContent = "";
            scheduleFrame(() => {
                announcer.textContent = text;
            });
        },
    };
}

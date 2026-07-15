const ACTION_LABELS = {
    FOLD: "fold",
    CHECK: "check",
    CALL: "call",
    RAISE: "raise to",
    ALL_IN: "all-in",
};

function getActionLabel(action) {
    const key = String(action || "").toUpperCase();
    return ACTION_LABELS[key] || String(action || "action").toLowerCase().replace(/_+/g, " ");
}

export function createActionLog(root = document) {
    const list = root.querySelector("#action-log");
    const panel = root.querySelector("#action-log-panel");
    const ownerDocument = list.ownerDocument || root;

    function append(message = {}) {
        const entry = ownerDocument.createElement("p");
        const actionKey = String(message.action || "system").toLowerCase();
        const actionClass = actionKey.replace(/[^a-z0-9_-]+/g, "-") || "system";
        entry.className = `log-entry action-${actionClass}`;

        if (message.type === "player_action") {
            const player = message.player_name || message.player_id || "Player";
            const amount = message.amount ? ` ${Number(message.amount).toLocaleString()}` : "";
            entry.textContent = `${player} ${getActionLabel(message.action)}${amount}`;
        } else if (message.type === "hand_result") {
            const winners = (message.winners || [])
                .map((winner) => winner.player_name || winner.player_id)
                .filter(Boolean);
            if (winners.length === 0) entry.textContent = "No winner";
            else entry.textContent = `${winners.length === 1 ? "Winner" : "Winners"}: ${winners.join(", ")}`;
        } else {
            entry.textContent = message.message || "Game update";
        }

        list.appendChild(entry);
        while (list.children.length > 100) list.firstElementChild.remove();
        list.scrollTop = list.scrollHeight;
    }

    return {
        append,
        clear() {
            list.replaceChildren();
            append({ message: "Waiting for first hand…" });
        },
        setCollapsed(value) {
            panel.classList.toggle("is-collapsed", value);
        },
    };
}

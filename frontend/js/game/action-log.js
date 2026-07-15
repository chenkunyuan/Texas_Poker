export function createActionLog(root = document) {
    const list = root.querySelector("#action-log");
    const panel = root.querySelector("#action-log-panel");
    const ownerDocument = list.ownerDocument || root;

    function append(message = {}) {
        const entry = ownerDocument.createElement("p");
        const action = String(message.action || "system").toLowerCase();
        entry.className = `log-entry action-${action}`;

        if (message.type === "player_action") {
            const player = message.player_name || message.player_id || "Player";
            const amount = message.amount ? ` ${Number(message.amount).toLocaleString()}` : "";
            entry.textContent = `${player} ${action}${amount}`;
        } else if (message.type === "hand_result") {
            const winners = (message.winners || [])
                .map((winner) => winner.player_name || winner.player_id)
                .filter(Boolean)
                .join(", ");
            entry.textContent = `Winner: ${winners}`;
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

import { getSeatPositions } from "./seat-layout.js";

const ACTION_LABELS = Object.freeze({
    FOLD: "Fold",
    CHECK: "Check",
    CALL: "Call",
    RAISE: "Raise",
    ALL_IN: "All in",
});

function formatAction(action) {
    if (!action) return "";
    const key = String(action.action || "").toUpperCase();
    const label = ACTION_LABELS[key] || "Action";
    const amount = Number(action.amount || 0);
    return amount > 0 ? `${label} ${amount.toLocaleString()}` : label;
}

function createPlayerSeat(document, player, position, { dealer, active, action }) {
    const folded = player.is_active === false;
    const classes = ["player-seat"];
    if (player.is_human) classes.push("is-human");
    if (folded) classes.push("is-folded");
    if (active) classes.push("is-active");

    const seat = document.createElement("article");
    seat.className = classes.join(" ");
    seat.style.left = `${position.x}%`;
    seat.style.top = `${position.y}%`;
    seat.setAttribute("data-player-id", player.id ?? "");
    if (active) seat.setAttribute("aria-current", "true");

    const heading = document.createElement("div");
    heading.className = "seat-heading";

    const name = document.createElement("strong");
    name.textContent = player.name || (player.is_human ? "You" : "AI");
    heading.appendChild(name);

    if (dealer) {
        const marker = document.createElement("span");
        marker.className = "dealer-marker";
        marker.textContent = "D";
        marker.setAttribute("aria-label", "Dealer");
        heading.appendChild(marker);
    }

    const chips = document.createElement("span");
    chips.className = "seat-chips";
    chips.textContent = `${Number(player.chips || 0).toLocaleString()} chips`;

    const contribution = document.createElement("span");
    contribution.className = "seat-contribution";
    const handContribution = Math.max(0, Number(player.total_bet_this_round) || 0);
    contribution.textContent = `Hand in ${handContribution.toLocaleString()}`;

    const status = document.createElement("span");
    status.className = "seat-state";
    const actionLabel = formatAction(action);
    const playerState = active ? (player.is_human ? "Your turn" : "Acting")
        : folded ? "Folded"
            : player.is_all_in ? "All in"
                : "Waiting";
    status.textContent = actionLabel ? `${playerState} · ${actionLabel}` : playerState;

    seat.appendChild(heading);
    seat.appendChild(chips);
    seat.appendChild(contribution);
    seat.appendChild(status);
    return seat;
}

export function renderPlayers(container, state) {
    const players = Array.isArray(state?.players) ? state.players : [];
    const positions = getSeatPositions(players.length);
    const history = Array.isArray(state?.action_history) ? state.action_history : [];
    const lastActions = new Map(history.map((action) => [action.player_id, action]));
    container.replaceChildren();

    players.forEach((player, index) => {
        const position = positions[index] || { x: 50, y: 86 };
        container.appendChild(createPlayerSeat(container.ownerDocument, player, position, {
            dealer: index === state?.dealer_index,
            active: index === state?.current_player_index,
            action: lastActions.get(player.id),
        }));
    });
}

function formatChips(value) {
    if (value === undefined || value === null) return "0";
    return value.toLocaleString();
}

function appendStatRow(container, label, value) {
    const documentRef = container.ownerDocument;
    const row = documentRef.createElement("div");
    row.className = "stat-row";

    const labelElement = documentRef.createElement("span");
    labelElement.className = "stat-label";
    labelElement.textContent = label;

    const valueElement = documentRef.createElement("span");
    valueElement.className = "stat-value";
    valueElement.textContent = value;

    row.append(labelElement, valueElement);
    container.appendChild(row);
}

function renderRankings(container, rankings) {
    const documentRef = container.ownerDocument;
    container.replaceChildren();

    if (rankings.length === 0) {
        const empty = documentRef.createElement("div");
        empty.className = "ranking-item";
        const label = documentRef.createElement("span");
        label.className = "rank-name";
        label.textContent = "No results available";
        empty.appendChild(label);
        container.appendChild(empty);
        return;
    }

    const medals = ["🥇", "🥈", "🥉"];
    rankings.forEach((ranking, index) => {
        const item = documentRef.createElement("div");
        item.className = "ranking-item fade-in";
        if (ranking.chips <= 0) item.classList.add("busted");
        if (ranking.is_human) item.classList.add("human");

        const icon = documentRef.createElement("span");
        icon.className = "rank-icon";
        icon.textContent = medals[index] || `#${index + 1}`;

        const info = documentRef.createElement("span");
        info.className = "rank-info";
        const name = documentRef.createElement("span");
        name.className = "rank-name";
        name.textContent = ranking.player_name || ranking.player_id || "Unknown";
        if (ranking.chips <= 0) {
            const busted = documentRef.createElement("span");
            busted.className = "busted-label";
            busted.textContent = "(BUSTED)";
            name.appendChild(busted);
        }

        const chips = documentRef.createElement("span");
        chips.className = "rank-chips";
        chips.textContent = ` ${formatChips(ranking.chips)} chips`;
        info.append(name, chips);
        item.append(icon, info);
        container.appendChild(item);
    });
}

function renderStats(container, stats, handCount) {
    container.replaceChildren();
    const keys = Object.keys(stats);
    if (keys.length === 0) {
        appendStatRow(container, "No statistics available", "");
        return;
    }

    let totalStartingChips = 0;
    let playerCount = 0;
    keys.forEach((key) => {
        const playerStats = stats[key];
        if (!playerStats) return;
        playerCount += 1;
        totalStartingChips += playerStats.starting_chips || 0;
    });

    appendStatRow(container, "Total Players", String(playerCount));
    appendStatRow(container, "Total Hands", String(handCount));
    appendStatRow(container, "Total Chips in Play", formatChips(totalStartingChips));

    const humanStats = stats.human;
    if (humanStats) {
        appendStatRow(container, "---", "---");
        appendStatRow(container, "Your Final Chips", formatChips(humanStats.final_chips || 0));
        appendStatRow(container, "Your Starting Chips", formatChips(humanStats.starting_chips || 0));
        const net = humanStats.net || 0;
        appendStatRow(container, "Your Net Result", net >= 0 ? `+${formatChips(net)}` : formatChips(net));
    }

    appendStatRow(container, "", "");
    keys.forEach((key, index) => {
        const playerStats = stats[key];
        if (!playerStats) return;
        const displayName = key === "human" ? "You" : (key || `Player ${index + 1}`);
        const net = playerStats.net || 0;
        appendStatRow(container, `${displayName} Net`, net >= 0 ? `+${formatChips(net)}` : formatChips(net));
    });
}

/**
 * Create the game-over results view.
 *
 * @param {Document|Element} root
 * @returns {{onPlayAgain: Function, onViewReplay: Function, render: Function}}
 */
export function createResultsView(root = document) {
    const rankings = root.querySelector("#rankings-list");
    const stats = root.querySelector("#stats-container");
    const totalHands = root.querySelector("#total-hands");
    let replayId = null;
    let playAgain = () => {};
    let viewReplay = () => {};

    root.querySelector("#btn-play-again").addEventListener("click", () => playAgain());
    root.querySelector("#btn-view-replay").addEventListener("click", () => viewReplay(replayId));

    return {
        onPlayAgain(fn) {
            playAgain = fn;
        },
        onViewReplay(fn) {
            viewReplay = fn;
        },
        render(message, handCount) {
            replayId = message.replay_id || null;
            totalHands.textContent = String(handCount);
            renderRankings(rankings, message.rankings || []);
            renderStats(stats, message.stats || {}, handCount);
        },
    };
}

import { findHuman } from "../state/game-state.js";
import { renderCards } from "./cards.js";
import { renderPlayers } from "./players.js";

export function createTableView(root = document) {
    const community = root.querySelector("#community-cards");
    const players = root.querySelector("#player-spots");
    const hand = root.querySelector("#hand-panel");
    const pot = root.querySelector("#pot-label");
    const thinking = root.querySelector("#thinking-indicator");
    const thinkingText = root.querySelector("#thinking-text");
    const document = hand.ownerDocument;

    return {
        render(state) {
            renderCards(community, state.community_cards, { placeholders: 5 });
            renderPlayers(players, state);

            const human = findHuman(state);
            pot.textContent = `Pot ${Number(state.pot || 0).toLocaleString()}`;
            hand.replaceChildren();

            const title = document.createElement("h2");
            title.textContent = "Your hand";
            hand.appendChild(title);

            const cards = document.createElement("div");
            cards.className = "hole-cards";
            cards.setAttribute("aria-label", "Your hole cards");
            hand.appendChild(cards);
            renderCards(cards, human?.hole_cards || [], { placeholders: 2 });
        },
        showThinking(name) {
            thinkingText.textContent = `${name || "AI"} is thinking…`;
            thinking.hidden = false;
        },
        hideThinking() {
            thinking.hidden = true;
        },
    };
}

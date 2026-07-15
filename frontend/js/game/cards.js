const SUITS = Object.freeze({
    HEARTS: "♥",
    DIAMONDS: "♦",
    CLUBS: "♣",
    SPADES: "♠",
});

const RED_SUITS = new Set(["HEARTS", "DIAMONDS"]);

function normalizeSuit(suit) {
    return String(suit || "").toUpperCase();
}

export function renderCards(container, cards = [], { placeholders = 0, faceDown = false } = {}) {
    const document = container.ownerDocument;
    const safeCards = Array.isArray(cards) ? cards : [];
    container.replaceChildren();

    for (const card of safeCards) {
        const suit = normalizeSuit(card?.suit);
        const element = document.createElement("div");
        element.className = `card ${faceDown ? "face-down" : RED_SUITS.has(suit) ? "suit-red" : "suit-black"}`;

        if (faceDown) {
            element.setAttribute("aria-label", "Face-down card");
        } else {
            const rank = document.createElement("span");
            rank.className = "card-rank";
            rank.textContent = card?.rank ?? "";

            const suitMark = document.createElement("span");
            suitMark.className = "card-suit";
            suitMark.textContent = SUITS[suit] || card?.suit || "";

            element.setAttribute("aria-label", `${card?.rank ?? ""} of ${suit.toLowerCase() || "unknown suit"}`);
            element.appendChild(rank);
            element.appendChild(suitMark);
        }

        container.appendChild(element);
    }

    const slotCount = Math.max(0, Number(placeholders) || 0);
    for (let index = safeCards.length; index < slotCount; index += 1) {
        const slot = document.createElement("div");
        slot.className = "card-slot empty";
        slot.setAttribute("aria-hidden", "true");
        container.appendChild(slot);
    }
}

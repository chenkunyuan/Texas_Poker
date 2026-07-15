export function normalizeGameState(raw = {}) {
    return {
        ...raw,
        players: Array.isArray(raw.players) ? raw.players : [],
        community_cards: Array.isArray(raw.community_cards) ? raw.community_cards : [],
        action_history: Array.isArray(raw.action_history) ? raw.action_history : [],
        pots: Array.isArray(raw.pots) ? raw.pots : [],
        pot: Number(raw.pot || raw.total_pot || 0),
        hand_number: Number(raw.hand_number || 0),
    };
}

export function findHuman(state) {
    return state.players.find((player) => player.is_human) || null;
}

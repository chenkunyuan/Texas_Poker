"""Card and Deck classes for Texas Hold'em."""

import random
from server.models.schemas import Card, Suit, Rank


RANK_ORDER: dict[Rank, int] = {
    Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 4, Rank.FIVE: 5,
    Rank.SIX: 6, Rank.SEVEN: 7, Rank.EIGHT: 8, Rank.NINE: 9,
    Rank.TEN: 10, Rank.JACK: 11, Rank.QUEEN: 12, Rank.KING: 13, Rank.ACE: 14,
}


class Deck:
    """Standard 52-card deck with Fisher-Yates shuffle."""

    def __init__(self):
        self.cards: list[Card] = []
        self._build()

    def _build(self):
        """Build a fresh 52-card deck."""
        self.cards = [
            Card(suit=suit, rank=rank)
            for suit in Suit
            for rank in Rank
        ]

    def shuffle(self):
        """Fisher-Yates shuffle."""
        for i in range(len(self.cards) - 1, 0, -1):
            j = random.randint(0, i)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]

    def deal(self, count: int = 1) -> list[Card]:
        """Deal `count` cards from top of deck."""
        if count > len(self.cards):
            raise ValueError(f"Not enough cards: {len(self.cards)} < {count}")
        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt

    def burn(self):
        """Burn one card (discard from top)."""
        self.deal(1)

    def reset(self):
        """Rebuild and reshuffle deck."""
        self._build()
        self.shuffle()

    def __len__(self) -> int:
        return len(self.cards)

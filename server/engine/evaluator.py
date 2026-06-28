"""Texas Hold'em hand evaluator — best 5-card hand from 7 cards."""

from itertools import combinations
from typing import List, Tuple

from server.models.schemas import Card, Rank
from server.engine.deck import RANK_ORDER


HAND_RANKS: dict[str, int] = {
    "high_card": 0,
    "one_pair": 1,
    "two_pair": 2,
    "three_of_a_kind": 3,
    "straight": 4,
    "flush": 5,
    "full_house": 6,
    "four_of_a_kind": 7,
    "straight_flush": 8,
    "royal_flush": 9,
}


def _get_rank_val(card: Card) -> int:
    """Return the numeric rank value (2-14) for a card."""
    return RANK_ORDER[card.rank]


def _evaluate_5_cards(cards: List[Card]) -> Tuple[int, List[int]]:
    """Evaluate exactly 5 cards.

    Returns (hand_rank_value, kickers_list).
    The kickers list is sorted from most significant to least,
    for use in tie-breaking comparisons.
    """
    ranks = sorted([_get_rank_val(c) for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    # Flush detection
    is_flush = len(set(suits)) == 1

    # Straight detection
    is_straight = False
    straight_high = 0

    unique_ranks_sorted = sorted(set(ranks), reverse=True)
    if len(unique_ranks_sorted) == 5:
        if unique_ranks_sorted[0] - unique_ranks_sorted[4] == 4:
            is_straight = True
            straight_high = unique_ranks_sorted[0]
        # Ace-low straight: A-2-3-4-5 (ranks: 14,5,4,3,2)
        elif set(unique_ranks_sorted) == {14, 2, 3, 4, 5}:
            is_straight = True
            straight_high = 5  # 5-high straight, Ace acts as low

    # Rank frequency counts
    rank_counts: dict[int, int] = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)

    # 1. Royal Flush / Straight Flush
    if is_flush and is_straight:
        if straight_high == 14:
            return (HAND_RANKS["royal_flush"], [14])
        return (HAND_RANKS["straight_flush"], [straight_high])

    # 2. Four of a Kind
    if counts == [4, 1]:
        quad_rank = next(r for r, c in rank_counts.items() if c == 4)
        kicker = next(r for r, c in rank_counts.items() if c == 1)
        return (HAND_RANKS["four_of_a_kind"], [quad_rank, kicker])

    # 3. Full House
    if counts == [3, 2]:
        trips_rank = next(r for r, c in rank_counts.items() if c == 3)
        pair_rank = next(r for r, c in rank_counts.items() if c == 2)
        return (HAND_RANKS["full_house"], [trips_rank, pair_rank])

    # 4. Flush
    if is_flush:
        return (HAND_RANKS["flush"], ranks)

    # 5. Straight
    if is_straight:
        return (HAND_RANKS["straight"], [straight_high])

    # 6. Three of a Kind
    if counts == [3, 1, 1]:
        trips_rank = next(r for r, c in rank_counts.items() if c == 3)
        kickers = sorted(
            [r for r, c in rank_counts.items() if c == 1], reverse=True
        )
        return (HAND_RANKS["three_of_a_kind"], [trips_rank] + kickers)

    # 7. Two Pair
    if counts == [2, 2, 1]:
        pair_ranks = sorted(
            [r for r, c in rank_counts.items() if c == 2], reverse=True
        )
        kicker = next(r for r, c in rank_counts.items() if c == 1)
        return (HAND_RANKS["two_pair"], pair_ranks + [kicker])

    # 8. One Pair
    if counts == [2, 1, 1, 1]:
        pair_rank = next(r for r, c in rank_counts.items() if c == 2)
        kickers = sorted(
            [r for r, c in rank_counts.items() if c == 1], reverse=True
        )
        return (HAND_RANKS["one_pair"], [pair_rank] + kickers)

    # 9. High Card
    return (HAND_RANKS["high_card"], ranks)


def evaluate_hand(
    hole_cards: List[Card], community_cards: List[Card]
) -> Tuple[int, List[int], str]:
    """Evaluate the best 5-card hand from 2 hole + up to 5 community cards.

    Tries all C(n, 5) combinations and returns the best hand found.

    Args:
        hole_cards: Player's 2 private cards.
        community_cards: 0-5 shared community cards.

    Returns:
        (hand_rank_value, kickers_list, hand_name_string)
        hand_rank_value: 0 (high_card) through 9 (royal_flush)
        kickers_list: ordered kicker values for tie-breaking
        hand_name_string: e.g. "one_pair", "flush", etc.
    """
    all_cards = list(hole_cards) + list(community_cards)
    best_rank = -1
    best_kickers: List[int] = []
    best_hand_name = ""

    # Build a reverse lookup for name from rank value
    rank_to_name: dict[int, str] = {v: k for k, v in HAND_RANKS.items()}

    for combo in combinations(all_cards, 5):
        rank_val, kickers = _evaluate_5_cards(list(combo))
        if rank_val > best_rank or (rank_val == best_rank and kickers > best_kickers):
            best_rank = rank_val
            best_kickers = kickers
            best_hand_name = rank_to_name[rank_val]

    return best_rank, best_kickers, best_hand_name


def compare_hands(
    hole1: List[Card], hole2: List[Card], community: List[Card]
) -> int:
    """Compare two players' best hands against the same community cards.

    Args:
        hole1: First player's 2 hole cards.
        hole2: Second player's 2 hole cards.
        community: The 0-5 community cards.

    Returns:
        1  if player 1 wins,
        -1 if player 2 wins,
        0  if the hands are tied (chopped pot).
    """
    r1, k1, _ = evaluate_hand(hole1, community)
    r2, k2, _ = evaluate_hand(hole2, community)

    # Compare hand rank first
    if r1 > r2:
        return 1
    if r2 > r1:
        return -1

    # Hand ranks are equal — compare kickers in order
    for a, b in zip(k1, k2):
        if a > b:
            return 1
        if b > a:
            return -1

    return 0

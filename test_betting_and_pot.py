"""
Test script for BettingRound and PotCalculator.

Creates realistic scenarios and verifies correctness.
"""

import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.models.schemas import (
    BlindsConfig,
    Card,
    GameState,
    Player,
    PlayerAction,
    Rank,
    Suit,
)
from server.engine.betting import BettingRound
from server.engine.pot import PotCalculator


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def make_player(
    player_id: str,
    name: str,
    chips: int = 1000,
    is_active: bool = True,
    is_all_in: bool = False,
    current_bet: int = 0,
    total_bet_this_round: int = 0,
) -> Player:
    return Player(
        id=player_id,
        name=name,
        chips=chips,
        is_active=is_active,
        is_all_in=is_all_in,
        current_bet=current_bet,
        total_bet_this_round=total_bet_this_round,
    )


def make_state(players, current_bet=0, pot=0, big_blind=10):
    return GameState(
        players=players,
        current_bet=current_bet,
        pot=pot,
        blinds=BlindsConfig(big=big_blind, small=big_blind // 2),
        variant="no_limit",
    )


# ---------------------------------------------------------------------------
# Dummy hand evaluator for distribute_pots testing
# ---------------------------------------------------------------------------

def dummy_evaluator(hole_cards, community_cards):
    """Return sum of rank numeric values — higher = better."""
    total = sum(c.rank.numeric for c in hole_cards)
    total += sum(c.rank.numeric for c in community_cards)
    return total


# ---------------------------------------------------------------------------
# Tests: BettingRound
# ---------------------------------------------------------------------------

def test_betting_round_check_fold():
    """Player A can check (no bets yet), Player B folds."""
    pA = make_player("A", "Alice")
    pB = make_player("B", "Bob")
    state = make_state([pA, pB])

    br = BettingRound(state, "no_limit")

    # A checks
    actions_A = br.get_valid_actions(pA)
    assert "CHECK" in actions_A, "A should be able to check"
    assert "FOLD" in actions_A, "A should be able to fold"

    br.apply_action(pA, PlayerAction.CHECK, 0)
    assert pA.has_acted_this_round
    assert pA.is_active

    # B folds
    br.apply_action(pB, PlayerAction.FOLD, 0)
    assert not pB.is_active

    assert br.is_round_complete()
    print("  PASS test_betting_round_check_fold")


def test_betting_round_call_and_raise():
    """Pre-flop scenario: SB=5, BB=10.  UTG raises to 30, BTN calls."""
    p1 = make_player("1", "SB", chips=995, current_bet=5, total_bet_this_round=5)
    p1.has_acted_this_round = True  # SB already posted
    p2 = make_player("2", "BB", chips=990, current_bet=10, total_bet_this_round=10)
    p3 = make_player("3", "UTG", chips=1000)
    p4 = make_player("4", "BTN", chips=1000)

    state = make_state([p1, p2, p3, p4], current_bet=10, pot=15, big_blind=10)
    br = BettingRound(state, "no_limit")

    # UTG raises to 30
    actions = br.get_valid_actions(p3)
    assert "RAISE" in actions
    assert actions["RAISE"]["min"] >= 20  # at least current_bet + BB
    assert "CALL" in actions

    br.apply_action(p3, PlayerAction.RAISE, 30)
    assert state.current_bet == 30
    assert p3.chips == 970
    assert p3.current_bet == 30

    # After a raise, BB and SB should have has_acted reset
    assert not p1.has_acted_this_round
    assert not p2.has_acted_this_round

    # Others fold
    br.apply_action(p1, PlayerAction.FOLD, 0)
    br.apply_action(p2, PlayerAction.FOLD, 0)

    # BTN calls 30
    actions = br.get_valid_actions(p4)
    assert "CALL" in actions
    br.apply_action(p4, PlayerAction.CALL, 30)
    assert p4.chips == 970
    assert p4.current_bet == 30

    assert br.is_round_complete()
    print("  PASS test_betting_round_call_and_raise")


def test_betting_round_all_in_raise():
    """Player goes all-in which acts as a raise."""
    pA = make_player("A", "Alice", chips=500)
    pB = make_player("B", "Bob", chips=1000)
    state = make_state([pA, pB], big_blind=10)
    br = BettingRound(state, "no_limit")

    # A goes all-in for 500 — this is an opening bet > 0, so it's a raise
    br.apply_action(pA, PlayerAction.ALL_IN, 500)
    assert pA.chips == 0
    assert pA.is_all_in
    assert pA.current_bet == 500
    assert state.current_bet == 500

    # B's has_acted should be reset
    assert not pB.has_acted_this_round

    # B can call
    actions = br.get_valid_actions(pB)
    assert "CALL" in actions
    br.apply_action(pB, PlayerAction.CALL, 500)
    assert pB.current_bet == 500
    assert br.is_round_complete()

    print("  PASS test_betting_round_all_in_raise")


def test_betting_round_forced_all_in():
    """Player can't afford call — forced all-in."""
    pA = make_player("A", "Alice", chips=1000, current_bet=20)
    pB = make_player("B", "Bob", chips=10, current_bet=0)
    state = make_state([pA, pB], current_bet=20, pot=20, big_blind=10)
    br = BettingRound(state, "no_limit")

    actions = br.get_valid_actions(pB)
    assert "CALL" not in actions  # can't afford full call
    assert "ALL_IN" in actions

    br.apply_action(pB, PlayerAction.ALL_IN, 10)
    assert pB.chips == 0
    assert pB.is_all_in
    assert pB.current_bet == 10  # less than current_bet — NOT a raise
    assert state.current_bet == 20  # unchanged

    print("  PASS test_betting_round_forced_all_in")


def test_betting_round_min_raise():
    """Min raise after an opening bet."""
    pA = make_player("A", "Alice", chips=1000, current_bet=20)
    pB = make_player("B", "Bob", chips=1000)
    state = make_state([pA, pB], current_bet=20, pot=20, big_blind=10)
    br = BettingRound(state, "no_limit")

    actions = br.get_valid_actions(pB)
    # Min raise should be current_bet + BB = 30
    assert actions["RAISE"]["min"] == 30

    br.apply_action(pB, PlayerAction.RAISE, 30)
    assert state.current_bet == 30

    # Now A's min raise should be 30 + 10 = 40 (the raise was 10, BB is 10)
    actions_A = br.get_valid_actions(pA)
    assert actions_A["RAISE"]["min"] == 40

    print("  PASS test_betting_round_min_raise")


# ---------------------------------------------------------------------------
# Tests: PotCalculator — calculate_side_pots
# ---------------------------------------------------------------------------

def test_side_pots_simple():
    """Three players, two all-ins at different levels."""
    pA = make_player("A", "Alice", chips=0, is_all_in=True, total_bet_this_round=100)
    pB = make_player("B", "Bob", chips=0, is_all_in=True, total_bet_this_round=200)
    pC = make_player("C", "Charlie", chips=800, is_active=True, total_bet_this_round=200)

    pots = PotCalculator.calculate_side_pots([pA, pB, pC])

    assert len(pots) == 2, f"Expected 2 pots, got {len(pots)}"

    # Pot 1: 100 * 3 = 300, eligible: A, B, C
    assert pots[0]["amount"] == 300
    assert set(pots[0]["eligible_players"]) == {"A", "B", "C"}

    # Pot 2: (200-100) * 2 = 200, eligible: B, C
    assert pots[1]["amount"] == 200
    assert set(pots[1]["eligible_players"]) == {"B", "C"}

    # Total matches sum of individual contributions
    total_in_pots = sum(p["amount"] for p in pots)
    total_contrib = sum(p.total_bet_this_round for p in [pA, pB, pC])
    assert total_in_pots == total_contrib, f"{total_in_pots} != {total_contrib}"

    print("  PASS test_side_pots_simple")


def test_side_pots_with_folded_player():
    """Folded player's money stays in the pot but they are not eligible."""
    pA = make_player("A", "Alice", chips=0, is_all_in=True, total_bet_this_round=50)
    pB = make_player("B", "Bob", chips=0, is_active=False, total_bet_this_round=100)  # folded
    pC = make_player("C", "Charlie", chips=900, is_active=True, total_bet_this_round=100)

    pots = PotCalculator.calculate_side_pots([pA, pB, pC])

    assert len(pots) == 2

    # Pot 1: 50 * 3 = 150, eligible: A, C (B folded)
    assert pots[0]["amount"] == 150
    assert set(pots[0]["eligible_players"]) == {"A", "C"}

    # Pot 2: (100-50) * 2 = 100, eligible: C only
    assert pots[1]["amount"] == 100
    assert set(pots[1]["eligible_players"]) == {"C"}

    total_in_pots = sum(p["amount"] for p in pots)
    total_contrib = sum(p.total_bet_this_round for p in [pA, pB, pC])
    assert total_in_pots == total_contrib

    print("  PASS test_side_pots_with_folded_player")


def test_side_pots_four_players():
    """Four players at three levels."""
    pA = make_player("A", "Alice", chips=0, is_all_in=True, total_bet_this_round=100)
    pB = make_player("B", "Bob", chips=0, is_all_in=True, total_bet_this_round=200)
    pC = make_player("C", "Charlie", chips=0, is_active=True, total_bet_this_round=200)
    pD = make_player("D", "Diana", chips=700, is_active=True, total_bet_this_round=300)

    pots = PotCalculator.calculate_side_pots([pA, pB, pC, pD])

    assert len(pots) == 3

    # Pot 1: 100 * 4 = 400
    assert pots[0]["amount"] == 400
    assert set(pots[0]["eligible_players"]) == {"A", "B", "C", "D"}

    # Pot 2: (200-100) * 3 = 300
    assert pots[1]["amount"] == 300
    assert set(pots[1]["eligible_players"]) == {"B", "C", "D"}

    # Pot 3: (300-200) * 1 = 100
    assert pots[2]["amount"] == 100
    assert set(pots[2]["eligible_players"]) == {"D"}

    total_in_pots = sum(p["amount"] for p in pots)
    total_contrib = sum(p.total_bet_this_round for p in [pA, pB, pC, pD])
    assert total_in_pots == total_contrib

    print("  PASS test_side_pots_four_players")


def test_side_pots_no_bets():
    """No one has bet — empty result."""
    pA = make_player("A", "Alice", total_bet_this_round=0)
    pB = make_player("B", "Bob", total_bet_this_round=0)

    pots = PotCalculator.calculate_side_pots([pA, pB])
    assert len(pots) == 0

    print("  PASS test_side_pots_no_bets")


# ---------------------------------------------------------------------------
# Tests: PotCalculator — distribute_pots
# ---------------------------------------------------------------------------

def test_distribute_pots():
    """Distribute side pots using a simple hand evaluator."""
    pA = make_player("A", "Alice", chips=0, is_all_in=True, total_bet_this_round=100)
    pA.hole_cards = [Card(rank=Rank.ACE, suit=Suit.SPADES), Card(rank=Rank.KING, suit=Suit.SPADES)]

    pB = make_player("B", "Bob", chips=0, is_all_in=True, total_bet_this_round=200)
    pB.hole_cards = [Card(rank=Rank.QUEEN, suit=Suit.HEARTS), Card(rank=Rank.JACK, suit=Suit.HEARTS)]

    pC = make_player("C", "Charlie", chips=800, is_active=True, total_bet_this_round=200)
    pC.hole_cards = [Card(rank=Rank.TWO, suit=Suit.CLUBS), Card(rank=Rank.THREE, suit=Suit.DIAMONDS)]

    community = [Card(rank=Rank.FOUR, suit=Suit.CLUBS),
                 Card(rank=Rank.FIVE, suit=Suit.HEARTS),
                 Card(rank=Rank.SIX, suit=Suit.SPADES),
                 Card(rank=Rank.SEVEN, suit=Suit.DIAMONDS),
                 Card(rank=Rank.EIGHT, suit=Suit.CLUBS)]

    pots = PotCalculator.calculate_side_pots([pA, pB, pC])

    # Record chips before distribution
    chips_before = {p.id: p.chips for p in [pA, pB, pC]}

    distributions = PotCalculator.distribute_pots(
        pots, [pA, pB, pC], community, dummy_evaluator
    )

    assert len(distributions) == 2

    # In our dummy evaluator, higher cards = better hand.
    # A has A+K = 14+13=27, B has Q+J=11+10=21, C has 2+3=5
    # So A wins everything they're eligible for.

    # Pot 1: A wins (eligible: A, B, C) — gets 300
    assert distributions[0]["winners"] == ["A"]
    assert pA.chips == chips_before["A"] + 300

    # Pot 2: B wins (eligible: B, C, A not eligible) — gets 200
    assert distributions[1]["winners"] == ["B"]
    assert pB.chips == chips_before["B"] + 200

    # C wins nothing
    assert pC.chips == chips_before["C"]

    print("  PASS test_distribute_pots")


def test_distribute_pots_tie():
    """Two players tie — pot is split."""
    pA = make_player("A", "Alice", chips=0, is_active=True, total_bet_this_round=100)
    pA.hole_cards = [Card(rank=Rank.ACE, suit=Suit.SPADES), Card(rank=Rank.KING, suit=Suit.SPADES)]

    pB = make_player("B", "Bob", chips=0, is_active=True, total_bet_this_round=100)
    pB.hole_cards = [Card(rank=Rank.ACE, suit=Suit.HEARTS), Card(rank=Rank.KING, suit=Suit.HEARTS)]

    community = [Card(rank=Rank.TWO, suit=Suit.CLUBS),
                 Card(rank=Rank.THREE, suit=Suit.DIAMONDS),
                 Card(rank=Rank.FOUR, suit=Suit.HEARTS),
                 Card(rank=Rank.FIVE, suit=Suit.SPADES),
                 Card(rank=Rank.SIX, suit=Suit.CLUBS)]

    pots = PotCalculator.calculate_side_pots([pA, pB])

    chips_before = {p.id: p.chips for p in [pA, pB]}

    distributions = PotCalculator.distribute_pots(
        pots, [pA, pB], community, dummy_evaluator
    )

    # Both have A+K = 27 → tie, split 200 → 100 each
    assert len(distributions[0]["winners"]) == 2
    assert pA.chips == chips_before["A"] + 100
    assert pB.chips == chips_before["B"] + 100

    print("  PASS test_distribute_pots_tie")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== BettingRound Tests ===")
    test_betting_round_check_fold()
    test_betting_round_call_and_raise()
    test_betting_round_all_in_raise()
    test_betting_round_forced_all_in()
    test_betting_round_min_raise()

    print("\n=== PotCalculator Tests ===")
    test_side_pots_simple()
    test_side_pots_with_folded_player()
    test_side_pots_four_players()
    test_side_pots_no_bets()
    test_distribute_pots()
    test_distribute_pots_tie()

    print("\nAll tests passed!")


if __name__ == "__main__":
    main()

"""
Texas Hold'em Poker — Pot Calculator.

Handles side-pot creation and pot distribution at showdown.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from server.models.schemas import Card, Player


class PotCalculator:
    """Static utility class for side-pot arithmetic and showdown distribution.

    All methods are stateless — they take data in and return results.
    """

    # ------------------------------------------------------------------
    # Side-pot calculation
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_side_pots(players: List[Player]) -> List[dict]:
        """Partition the round's total contributions into side-pots.

        The algorithm sorts every player by ``total_bet_this_round``
        ascending.  Each distinct contribution level beyond the previous one
        creates a side pot.  Folded players contribute to the maths but are
        **not** listed as eligible recipients.

        Args:
            players: All players who were dealt into the hand.

        Returns:
            A list of side-pot dicts, each containing:
            - ``amount``  — total chips in this side-pot
            - ``eligible_players`` — list of player IDs who may win this pot
        """
        # Consider all players for contribution counting (folded money stays in
        # the pot), but only non-folded players can win.
        all_players = [p for p in players if p.total_bet_this_round > 0]
        if not all_players:
            return []

        non_folded = [p for p in players if p.is_active or p.is_all_in]

        # Unique contribution levels sorted ascending
        levels: List[int] = sorted(
            set(p.total_bet_this_round for p in all_players)
        )

        pots: List[dict] = []
        prev_level: int = 0

        for level in levels:
            if level <= 0:
                continue

            increment = level - prev_level
            if increment <= 0:
                continue

            # How many players contributed **at least** this level?
            contributor_count = sum(
                1 for p in all_players if p.total_bet_this_round >= level
            )

            # Which non-folded players are eligible for this chunk?
            eligible_ids = [
                p.id
                for p in non_folded
                if p.total_bet_this_round >= level
            ]

            pot_amount = increment * contributor_count

            if pot_amount > 0 and eligible_ids:
                pots.append(
                    {
                        "amount": pot_amount,
                        "eligible_players": eligible_ids,
                    }
                )

            prev_level = level

        return pots

    # ------------------------------------------------------------------
    # Pot distribution
    # ------------------------------------------------------------------

    @staticmethod
    def distribute_pots(
        pots: List[dict],
        players: List[Player],
        community_cards: List[Card],
        evaluator_func: Callable[[List[Card], List[Card]], int],
    ) -> List[dict]:
        """Distribute side-pots to the player(s) with the best hand in each.

        Args:
            pots: The side-pots returned by :meth:`calculate_side_pots`.
            players: All players in the hand (used to look up hole cards).
            community_cards: The five community cards.
            evaluator_func: A callable ``(hole_cards, community_cards) -> int``
                that returns a hand-strength score (higher = better).  The
                caller is expected to provide a hand-evaluator from the engine.

        Returns:
            A list of distribution dicts, one per side-pot:
            - ``pot_amount``  — the total chips in this pot
            - ``winners``     — list of winning player IDs
            - ``winning_score`` — the best hand score
            - ``split_amount``  — how much each winner receives (integer
              division; any remainder goes to the first winner)
        """
        # Build a quick lookup
        player_map: dict[str, Player] = {p.id: p for p in players}

        distributions: List[dict] = []

        for pot in pots:
            eligible = [
                player_map[pid]
                for pid in pot["eligible_players"]
                if pid in player_map
            ]

            if not eligible:
                # All eligible players have disappeared (should not happen).
                distributions.append(
                    {
                        "pot_amount": pot["amount"],
                        "winners": [],
                        "winning_score": 0,
                        "split_amount": 0,
                    }
                )
                continue

            # Evaluate every eligible player's hand and find the best
            best_score: Optional[int] = None
            winners: List[Player] = []

            for player in eligible:
                # Players without hole cards (should not happen) are skipped.
                if not player.hole_cards:
                    continue

                score = evaluator_func(player.hole_cards, community_cards)

                if best_score is None or score > best_score:
                    best_score = score
                    winners = [player]
                elif score == best_score:
                    winners.append(player)

            if not winners:
                distributions.append(
                    {
                        "pot_amount": pot["amount"],
                        "winners": [],
                        "winning_score": 0,
                        "split_amount": 0,
                    }
                )
                continue

            # Split the pot equally; any odd chip goes to the first winner
            split_amount = pot["amount"] // len(winners)
            remainder = pot["amount"] % len(winners)

            for i, winner in enumerate(winners):
                winner.chips += split_amount + (1 if i == 0 else 0) * remainder

            distributions.append(
                {
                    "pot_amount": pot["amount"],
                    "winners": [w.id for w in winners],
                    "winning_score": best_score,
                    "split_amount": split_amount,
                }
            )

        return distributions

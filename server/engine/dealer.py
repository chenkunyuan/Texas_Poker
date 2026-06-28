"""
Texas Hold'em Poker — Dealer.

Manages button rotation, position assignment, blind posting, blind increases,
hole-card dealing, community-card dealing, and action-order determination.
"""

from __future__ import annotations

from typing import List, Optional

from server.models.schemas import (
    Card,
    GamePhase,
    GameState,
    Player,
    Position,
)
from server.engine.deck import Deck


class Dealer:
    """Orchestrates the mechanical aspects of a Texas Hold'em hand.

    Responsibilities
    ----------------
    * Rotate the dealer button clockwise each hand.
    * Assign table positions (SB, BB, UTG, MP, CO, BTN) to active players.
    * Post small-blind and big-blind chips from players to the pot.
    * Increase blinds periodically when ``mode == "increasing"``.
    * Shuffle the deck and deal hole cards (2 per active player).
    * Burn and deal community cards (flop, turn, river).
    * Determine the action order for the current betting round.

    The ``Dealer`` owns the deck lifecycle and mutates the shared
    ``GameState``.  Betting logic lives in :class:`BettingRound` — the
    dealer only handles the mechanical dealing operations.
    """

    # Canonical position order for a 6-max table, ordered by action
    # sequence clockwise from the small blind.
    POSITION_ORDER: List[Position] = [
        Position.SB,
        Position.BB,
        Position.UTG,
        Position.MP,
        Position.CO,
        Position.BTN,
    ]

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, state: GameState) -> None:
        """Create a dealer for *state*.

        A fresh ``Deck`` is built on construction and re-shuffled at the
        start of every hand via :meth:`start_new_hand`.
        """
        self.state = state
        self.deck = Deck()

    # ------------------------------------------------------------------
    # Public API — hand lifecycle
    # ------------------------------------------------------------------

    def start_new_hand(self) -> None:
        """Begin a new hand.

        1. Reset per-hand player state for every player.
        2. Rotate the dealer button clockwise (skipped on the very first
           hand so the configured ``dealer_index`` is honoured).
        3. Increment the hand counter.
        4. Maybe increase blinds (see :meth:`_update_blinds`).
        5. Assign positions relative to the button.
        6. Post small-blind and big-blind chips.
        7. Clear community cards, side-pots, and action history.
        8. Shuffle the deck and deal 2 hole cards to each active player.
        9. Set the game phase to ``PRE_FLOP``.
        """
        state = self.state

        # 1. Reset per-hand state for every player --------------------------
        for p in state.players:
            p.reset_for_new_hand()

        # 2. Rotate button (skip hand 0 — first hand respects initial
        #    dealer_index).  Only rotate among players who have chips. -----
        if state.hand_number > 0:
            self._rotate_button()

        # 3. Increment hand counter -----------------------------------------
        state.hand_number += 1

        # 4. Maybe increase blinds ------------------------------------------
        self._update_blinds()

        # 5. Reset round-level state ----------------------------------------
        state.community_cards = []
        state.pot = 0
        state.current_bet = 0
        state.action_history = []
        state.side_pots = []
        state.current_player_index = None

        # 6. Assign positions -----------------------------------------------
        self._assign_positions()

        # 7. Post blinds (adds to pot / sets current_bet) -------------------
        self._post_blinds()

        # 8. Shuffle & deal hole cards --------------------------------------
        self.deck.reset()
        self._deal_hole_cards()

        # 9. Set phase ------------------------------------------------------
        state.phase = GamePhase.PRE_FLOP

    def deal_community(self, count: int) -> List[Card]:
        """Burn one card and deal *count* community cards.

        The dealt cards are appended to ``state.community_cards`` and also
        returned as a list for convenience.

        Args:
            count: Number of community cards to deal (3 for flop, 1 each for
                   turn and river).

        Returns:
            The list of newly-dealt community cards.
        """
        self.deck.burn()
        cards = self.deck.deal(count)
        self.state.community_cards.extend(cards)
        return cards

    def get_action_order(self) -> List[Player]:
        """Return the ordered list of players who must act this round.

        *Pre-flop*: the player immediately after the big blind acts first,
        and the big blind acts last.

        *Post-flop*: the player immediately after the dealer button (the
        small blind) acts first, and the button acts last.

        Only active players are included.  All-in players are included —
        they are simply skipped during the betting loop.

        Returns:
            Players in clockwise action order, starting from the correct
            first-to-act position.
        """
        ordered = self._get_ordered_players()
        active = [p for p in ordered if p.is_active]

        if not active:
            return []

        if self.state.phase == GamePhase.PRE_FLOP:
            # Pre-flop: start after the big blind (UTG or equivalent).
            # Find the BB and rotate so BB is last.
            bb_idx = next(
                (i for i, p in enumerate(active) if p.position == Position.BB),
                None,
            )
            if bb_idx is not None:
                start = (bb_idx + 1) % len(active)
                return active[start:] + active[:start]
            # Fallback: if no BB, use order as-is.
            return active
        else:
            # Post-flop: the ordered list already starts from SB (dealer's
            # left), which is the correct first-to-act position.
            return active

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assign_positions(self) -> None:
        """Assign ``Position`` values to every active player.

        Positions are distributed clockwise starting from the player
        immediately left of the dealer button.  The button receives the
        *last* (best) position for the current player count.

        * 6 players — SB, BB, UTG, MP, CO, BTN  (all positions)
        * 5 players — SB, BB, UTG, MP, BTN
        * 4 players — SB, BB, UTG, BTN
        * 3 players — SB, BB, BTN
        * 2 players — SB, BB  (heads-up: dealer **is** the small blind)
        """
        # Clear all positions first.
        for p in self.state.players:
            p.position = None

        active = [p for p in self.state.players if p.is_active]
        n_active = len(active)

        if n_active < 2:
            return

        # Build the position list for this player count.
        if n_active == 2:
            # Heads-up: dealer is SB, other is BB.
            positions: List[Position] = [Position.SB, Position.BB]
        else:
            # Always start with SB and BB.
            positions = [Position.SB, Position.BB]
            # Fill middle positions (UTG, MP, CO) as player count grows.
            middle = [Position.UTG, Position.MP, Position.CO]
            for i in range(max(0, n_active - 3)):
                positions.append(middle[i])
            # Dealer gets BTN for 3+ players.
            positions.append(Position.BTN)

        # Get players in clockwise order starting from dealer's left (SB).
        ordered = self._get_ordered_players()
        ordered_active = [p for p in ordered if p.is_active]

        if n_active == 2:
            # Heads-up: dealer is SB, other (dealer+1) is BB.
            dealer = self.state.players[self.state.dealer_index]
            dealer.position = Position.SB
            other_idx = (self.state.dealer_index + 1) % len(self.state.players)
            self.state.players[other_idx].position = Position.BB
        else:
            for i, player in enumerate(ordered_active):
                player.position = positions[i]

    def _update_blinds(self) -> None:
        """Increase blinds when the increasing-blinds schedule fires.

        Blind increases only apply when:

        * ``mode`` is ``"increasing"``.
        * ``increase_interval`` is not ``None`` and ``> 0`` (checked before
          any division to avoid ``ZeroDivisionError``).
        * The current hand number is a positive multiple of the interval.

        Both blinds are multiplied by ``increase_multiplier`` and truncated
        to integers.
        """
        if self.state.blinds is None:
            return

        blinds = self.state.blinds

        if blinds.mode != "increasing":
            return

        if blinds.increase_interval is None or blinds.increase_interval <= 0:
            return

        if self.state.hand_number > 0 and self.state.hand_number % blinds.increase_interval == 0:
            blinds.small = int(blinds.small * blinds.increase_multiplier)
            blinds.big = int(blinds.big * blinds.increase_multiplier)

    def _post_blinds(self) -> None:
        """Collect small-blind and big-blind chips and add them to the pot.

        A player who cannot cover the full blind posts their remaining chips
        and is marked all-in.  The big blind sets the table's ``current_bet``.
        """
        sb_player: Optional[Player] = None
        bb_player: Optional[Player] = None

        for p in self.state.players:
            if p.position == Position.SB:
                sb_player = p
            elif p.position == Position.BB:
                bb_player = p

        if sb_player is None or bb_player is None:
            return

        small_blind = self.state.blinds.small if self.state.blinds else 5
        big_blind = self.state.blinds.big if self.state.blinds else 10

        # --- Small blind ---
        if sb_player.chips > 0:
            sb_amount = min(small_blind, sb_player.chips)
            sb_player.chips -= sb_amount
            sb_player.current_bet = sb_amount
            sb_player.total_bet_this_round = sb_amount
            self.state.pot += sb_amount
            if sb_player.chips == 0:
                sb_player.is_all_in = True

        # --- Big blind (also sets the table's current_bet) ---
        if bb_player.chips > 0:
            bb_amount = min(big_blind, bb_player.chips)
            bb_player.chips -= bb_amount
            bb_player.current_bet = bb_amount
            bb_player.total_bet_this_round = bb_amount
            self.state.pot += bb_amount
            self.state.current_bet = bb_amount
            if bb_player.chips == 0:
                bb_player.is_all_in = True

    def _deal_hole_cards(self) -> None:
        """Deal two hole cards to each active player.

        Cards are drawn from the top of the deck in standard order: one card
        to each active player (starting left of the button and moving
        clockwise), then a second card to each.
        """
        active = [p for p in self.state.players if p.is_active]
        if len(active) < 2:
            return

        # Deal one card per active player per pass, starting left of button.
        ordered = self._get_ordered_players()
        for _ in range(2):
            for player in ordered:
                if player.is_active:
                    card = self.deck.deal(1)[0]
                    player.hole_cards.append(card)

    def _rotate_button(self) -> None:
        """Advance the dealer button to the next player who has chips.

        Skips players who are out of chips (busted).  If no player has
        chips the button stays where it is — the game is effectively over.
        """
        n = len(self.state.players)
        if n == 0:
            return
        for _ in range(n):
            self.state.dealer_index = (self.state.dealer_index + 1) % n
            if self.state.players[self.state.dealer_index].chips > 0:
                return

    def _get_ordered_players(self) -> List[Player]:
        """Return all players in clockwise order starting from the dealer's left.

        This mirrors ``POSITION_ORDER``: index 0 is SB, index 1 is BB,
        …, index N-1 is BTN (the dealer).
        """
        n = len(self.state.players)
        if n == 0:
            return []
        return [
            self.state.players[(self.state.dealer_index + 1 + i) % n]
            for i in range(n)
        ]

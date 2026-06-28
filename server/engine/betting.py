"""
Texas Hold'em Poker — Betting Round Engine.

Manages a single betting round: valid-action checks, action application,
and round-completion detection.  Supports no_limit and pot_limit variants.
"""

from __future__ import annotations

from typing import Optional

from server.models.schemas import (
    GameState,
    Player,
    PlayerAction,
)


class BettingRound:
    """Manages one complete betting round (pre-flop, flop, turn, or river).

    Tracks the last-raise size so min-raise calculations stay correct.
    Does *not* decide *who* acts next — that is the caller's responsibility.
    """

    def __init__(self, state: GameState, variant: str) -> None:
        """Initialise the round wrapper.

        Args:
            state: The mutable GameState this round operates on.
            variant: Either ``"no_limit"`` or ``"pot_limit"``.
        """
        self.state = state
        self.variant = variant

        # Last-raise size is used for minimum-raise calculations.
        # Initialised to the big-blind so the opening bet is at least the BB
        # and subsequent raises must be at least a BB on top of current_bet.
        big_blind = state.blinds.big if state.blinds else 10
        self._last_raise_size = big_blind

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_valid_actions(self, player: Player) -> dict:
        """Return a dict describing every action the player may take right now.

        Keys are ``PlayerAction`` values (as strings).  Each value is a
        sub-dict with at minimum ``{"action": <PlayerAction>, "amount": int}``.
        For raises the sub-dict also carries ``"min"`` and ``"max"``.

        Returns an empty dict when the player is not allowed to act (already
        folded, already all-in, …).
        """
        # Cannot act if not in the hand
        if not player.is_active or player.is_all_in:
            return {}

        call_amount = self._call_amount(player)
        actions: dict = {}

        # --- FOLD (always allowed) -------------------------------------------
        actions[PlayerAction.FOLD.value] = {
            "action": PlayerAction.FOLD,
            "amount": 0,
        }

        # --- CHECK (only when nothing to call) -------------------------------
        if call_amount == 0:
            actions[PlayerAction.CHECK.value] = {
                "action": PlayerAction.CHECK,
                "amount": 0,
            }

        # --- CALL / ALL-IN (when there *is* something to call) ---------------
        if call_amount > 0:
            if call_amount >= player.chips:
                # Player cannot afford a full call — only all-in is possible.
                actions[PlayerAction.ALL_IN.value] = {
                    "action": PlayerAction.ALL_IN,
                    "amount": player.chips,
                }
            else:
                actions[PlayerAction.CALL.value] = {
                    "action": PlayerAction.CALL,
                    "amount": call_amount,
                }
                # Voluntary all-in is always available as a separate action
                actions[PlayerAction.ALL_IN.value] = {
                    "action": PlayerAction.ALL_IN,
                    "amount": player.chips,
                }

        # --- RAISE -----------------------------------------------------------
        min_total = self._get_min_raise()
        max_total = self._get_max_raise(player)

        # A raise is possible when the player can put in more than the call.
        if max_total > call_amount and player.chips > max(call_amount, 0):
            actions[PlayerAction.RAISE.value] = {
                "action": PlayerAction.RAISE,
                "amount": -1,          # placeholder — player picks the amount
                "min": min_total,
                "max": min(max_total, player.chips),
            }
            # Also expose all-in even when call_amount == 0
            if PlayerAction.ALL_IN.value not in actions:
                actions[PlayerAction.ALL_IN.value] = {
                    "action": PlayerAction.ALL_IN,
                    "amount": player.chips,
                }

        return actions

    def apply_action(
        self, player: Player, action: PlayerAction, amount: int
    ) -> None:
        """Apply *player*'s *action* with the given *amount* to the game state.

        This method assumes the action has already been validated — it does not
        re-check legality.
        """
        if action == PlayerAction.FOLD:
            self._apply_fold(player)

        elif action == PlayerAction.CHECK:
            self._apply_check(player)

        elif action == PlayerAction.CALL:
            self._apply_call(player, amount)

        elif action == PlayerAction.RAISE:
            self._apply_raise(player, amount)

        elif action == PlayerAction.ALL_IN:
            self._apply_all_in(player, amount)

    def is_round_complete(self) -> bool:
        """Return ``True`` when no more betting can happen in this round.

        Conditions (either is sufficient):
        1. At most one active (non-folded, non-all-in) player remains.
        2. Every active non-all-in player has acted this round **and** their
           ``current_bet`` equals the state's ``current_bet``.
        """
        active_players = [
            p for p in self.state.players if p.is_active and not p.is_all_in
        ]

        # One or zero players left who can still act
        if len(active_players) <= 1:
            return True

        # All remaining players have acted and their bets are equalized
        all_acted = all(p.has_acted_this_round for p in active_players)
        all_bets_equal = all(
            p.current_bet == self.state.current_bet for p in active_players
        )
        return all_acted and all_bets_equal

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _call_amount(self, player: Player) -> int:
        """How many chips *player* must add to match the current bet."""
        return max(0, self.state.current_bet - player.current_bet)

    def _get_min_raise(self) -> int:
        """Minimum **total** bet a player must make to count as a raise.

        - When ``current_bet == 0``: the minimum is ``last_raise_size``
          (i.e. at least one big-blind as the opening bet).
        - When ``current_bet > 0``:  ``current_bet + last_raise_size``.
        """
        if self.state.current_bet == 0:
            # Opening bet — must be at least the last raise size (≥ BB)
            return self._last_raise_size
        return self.state.current_bet + self._last_raise_size

    def _get_max_raise(self, player: Player) -> int:
        """Maximum **total** bet *player* can make (variant-aware).

        - *no_limit*: all remaining chips.
        - *pot_limit*: pot-sized raise.  The math:
            max_raise_total = current_bet + pot + call_amount
          … capped at the player's remaining chips.
        """
        if self.variant == "no_limit":
            return player.chips + player.current_bet

        # pot_limit -----------------------------------------------------------
        call_amount = self._call_amount(player)
        # The size of the pot *after* calling is  pot + call_amount.
        # A pot-sized raise means you may raise by that amount *on top* of
        # the call.  So the total bet becomes:
        #   current_bet  +  (pot + call_amount)
        max_total = self.state.current_bet + self.state.pot + call_amount
        # Cannot bet more than you have (including chips already committed)
        return min(max_total, player.chips + player.current_bet)

    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------

    def _apply_fold(self, player: Player) -> None:
        """Fold the player — they are out of the hand."""
        player.is_active = False
        player.has_acted_this_round = True

    def _apply_check(self, player: Player) -> None:
        """Check — pass the action with no additional chips."""
        player.has_acted_this_round = True

    def _apply_call(self, player: Player, amount: int) -> None:
        """Call the current bet — *amount* is ignored; we compute correctly."""
        call_amount = self._call_amount(player)

        # Cap at the player's remaining chips (partial call → all-in)
        actual = min(call_amount, player.chips)

        player.chips -= actual
        player.current_bet += actual
        player.total_bet_this_round += actual
        self.state.pot += actual
        player.has_acted_this_round = True

        if player.chips == 0:
            player.is_all_in = True

    def _apply_raise(self, player: Player, amount: int) -> None:
        """Raise — *amount* is the **total** bet the player wants to make.

        (i.e. the new ``current_bet`` value for the table).
        """
        # Chips the player must add on top of what they already have committed
        chips_to_add = amount - player.current_bet

        if chips_to_add > player.chips:
            # Not enough chips — this becomes an effective all-in.
            # Fall through to all-in handling.
            self._apply_all_in(player, player.chips)
            return

        if chips_to_add <= 0:
            # Invalid raise — treat as check/call depending on call amount.
            call_amount = self._call_amount(player)
            if call_amount > 0:
                self._apply_call(player, call_amount)
            else:
                self._apply_check(player)
            return

        # Record the raise size before updating state
        old_current_bet = self.state.current_bet
        self._last_raise_size = amount - old_current_bet

        player.chips -= chips_to_add
        player.current_bet = amount
        player.total_bet_this_round += chips_to_add
        self.state.pot += chips_to_add
        self.state.current_bet = amount
        player.has_acted_this_round = True

        if player.chips == 0:
            player.is_all_in = True

        # When a raise (or all-in-raise) occurs, every other active,
        # non-all-in player is given a fresh chance to act.
        self._reset_has_acted_except(player)

    def _apply_all_in(self, player: Player, amount: int) -> None:
        """Go all-in — *amount* is ignored; all remaining chips go in."""
        all_in_chips = player.chips
        if all_in_chips <= 0:
            # No chips left — treat as call/check
            call_amount = self._call_amount(player)
            if call_amount > 0:
                self._apply_call(player, call_amount)
            else:
                self._apply_check(player)
            return

        old_current_bet = self.state.current_bet

        player.chips = 0
        player.current_bet += all_in_chips
        player.total_bet_this_round += all_in_chips
        player.is_all_in = True
        self.state.pot += all_in_chips

        # An all-in only counts as a raise when the total bet exceeds the
        # previous current_bet.
        if player.current_bet > old_current_bet:
            self._last_raise_size = player.current_bet - old_current_bet
            self.state.current_bet = player.current_bet
            self._reset_has_acted_except(player)

        player.has_acted_this_round = True

    def _reset_has_acted_except(self, acting_player: Player) -> None:
        """Every active, non-all-in player (except *acting_player*) gets
        ``has_acted_this_round = False`` so they may respond to the raise."""
        for p in self.state.players:
            if (
                p.is_active
                and not p.is_all_in
                and p.id != acting_player.id
            ):
                p.has_acted_this_round = False

"""
Rule-based Texas Hold'em poker AI engine.

Makes personality-driven poker decisions using hand-strength evaluation,
positional awareness, and configurable aggression / bluff parameters.

Used as the primary decision source; the LLM is only consulted when the
rule engine's confidence is below a configured threshold.
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

from server.engine.deck import RANK_ORDER
from server.engine.evaluator import evaluate_hand
from server.models.schemas import (
    Card,
    GamePhase,
    GameState,
    Player,
    PlayerAction,
    Position,
)


class RuleEngine:
    """Personality-driven rule-based poker decision engine.

    Attributes:
        aggression: 0.0 (passive) to 1.0 (aggressive).
        bluff_freq: Probability of running a bluff with a weak hand.
        range_pct: Top X% of preflop hands the player will voluntarily play.
        fold_to_3bet: Probability of folding when facing a 3-bet preflop.
    """

    def __init__(self, personality: dict) -> None:
        self.aggression: float = float(personality.get("aggression", 0.5))
        self.bluff_freq: float = float(personality.get("bluff_frequency", 0.1))
        self.range_pct: float = float(personality.get("preflop_range_pct", 25))
        self.fold_to_3bet: float = float(personality.get("fold_to_3bet", 0.4))

    # ======================================================================
    # Public API
    # ======================================================================

    def decide(
        self,
        state: GameState,
        player: Player,
        valid_actions: Optional[dict] = None,
    ) -> Tuple[PlayerAction, int, float]:
        """Decide what action to take.

        Args:
            state: The current game state.
            player: The AI player making the decision.
            valid_actions: Dict of valid actions from
                :meth:`BettingRound.get_valid_actions`.  When ``None`` a
                minimal default is derived from *state*.

        Returns:
            ``(action, amount, confidence)`` where *confidence* is in
            ``[0.0, 1.0]``.
        """
        if valid_actions is None:
            valid_actions = self._default_valid_actions(state, player)

        if not valid_actions:
            return PlayerAction.FOLD, 0, 1.0

        # Route to preflop / postflop handler
        if state.phase == GamePhase.PRE_FLOP:
            return self._preflop_decision(state, player, valid_actions)
        else:
            return self._postflop_decision(state, player, valid_actions)

    # ======================================================================
    # Preflop logic
    # ======================================================================

    def _preflop_decision(
        self,
        state: GameState,
        player: Player,
        valid_actions: dict,
    ) -> Tuple[PlayerAction, int, float]:
        """Preflop decision: evaluate hand strength, apply range & aggression.

        Strategy:

        * Fold hands below the personality's range threshold.
        * With playable hands, raise/limp proportional to aggression.
        * Occasionally bluff with junk hands (controlled by *bluff_freq*).
        * When facing a raise (3-bet), fold at *fold_to_3bet* rate for
          marginal hands.
        """
        strength = self._evaluate_preflop_hand(player.hole_cards)
        range_threshold = 1.0 - (self.range_pct / 100.0)

        # Position adjustment — widen playable range in late position
        pos_mult = self._position_multiplier(player.position)
        effective_strength = min(1.0, strength * pos_mult)

        # --- 3-bet handling --------------------------------------------------
        # A 3-bet means the player has already committed chips this round and
        # is now facing a re-raise (call_amount > 0 despite having bet already).
        call_amount = max(0, state.current_bet - (player.current_bet or 0))
        is_facing_3bet = call_amount > 0 and player.total_bet_this_round > 0

        # --- Fold decision ---------------------------------------------------
        if effective_strength < range_threshold:
            if self._should_bluff():
                return self._attempt_bluff(valid_actions, strength)
            if self._can_check(valid_actions):
                return PlayerAction.CHECK, 0, 1.0 - strength
            return PlayerAction.FOLD, 0, 1.0 - strength

        # --- Marginal hand facing a 3-bet ------------------------------------
        if is_facing_3bet and effective_strength < range_threshold + 0.12:
            if random.random() < self.fold_to_3bet:
                return PlayerAction.FOLD, 0, 0.5

        # --- Playable hand — decide aggression level -------------------------
        confidence = 0.5 + effective_strength * 0.5
        raise_tendency = self.aggression * effective_strength

        if random.random() < raise_tendency:
            return self._make_raise(state, player, valid_actions, effective_strength)
        else:
            if self._can_check(valid_actions):
                return PlayerAction.CHECK, 0, confidence
            return self._make_call(valid_actions, confidence)

    # ======================================================================
    # Postflop logic
    # ======================================================================

    def _postflop_decision(
        self,
        state: GameState,
        player: Player,
        valid_actions: dict,
    ) -> Tuple[PlayerAction, int, float]:
        """Postflop decision: evaluate absolute hand strength + draws.

        Uses :func:`evaluate_hand` for absolute hand ranking and supplements
        with draw detection for semi-bluff opportunities.
        """
        community = state.community_cards

        # --- Hand strength ---------------------------------------------------
        strength = self._evaluate_postflop_strength(player.hole_cards, community)
        draw_bonus = self._evaluate_draws(player.hole_cards, community)

        # Effective strength: blend absolute strength with draw potential.
        # When we have a significant draw, the draw IS the hand — give it
        # more weight so semi-bluffing becomes viable.
        if draw_bonus > 0.15:
            effective = strength * 0.35 + draw_bonus * 0.65
        else:
            effective = strength * 0.8 + draw_bonus * 0.2

        # Position adjustment
        pos_mult = self._position_multiplier(player.position)
        effective = min(1.0, effective * pos_mult)

        # Confidence: draws are inherently uncertain; strong made hands are not
        if draw_bonus > 0.15 and strength < 0.5:
            # Drawing hand — lower confidence, more likely to trigger LLM
            confidence = 0.35 + draw_bonus * 0.6
        else:
            distance_from_center = abs(effective - 0.5) * 2
            confidence = 0.5 + distance_from_center * 0.4

        # --- Decision thresholds ---------------------------------------------
        call_amount = max(0, state.current_bet - (player.current_bet or 0))

        # Very strong hand (>0.75): raise / re-raise
        if effective > 0.75:
            if self._can_raise(valid_actions):
                return self._make_raise(state, player, valid_actions, effective)

        # Strong hand (0.55-0.75): bet if first to act, otherwise call/raise
        if effective > 0.55:
            raise_tendency = self.aggression * effective
            if random.random() < raise_tendency and self._can_raise(valid_actions):
                return self._make_raise(state, player, valid_actions, effective)
            if self._can_check(valid_actions):
                return PlayerAction.CHECK, 0, confidence
            return self._make_call(valid_actions, confidence)

        # Marginal hand (0.3-0.55): pot-odds aware decision
        if effective > 0.3:
            if self._can_check(valid_actions):
                # Sometimes bet as a semi-bluff when we have draw potential
                if draw_bonus > 0.2 and self._should_bluff():
                    return self._make_raise(state, player, valid_actions, effective)
                return PlayerAction.CHECK, 0, confidence

            # Facing a bet — use pot odds to decide
            if call_amount > 0 and player.chips > 0:
                pot_odds = call_amount / (state.pot + call_amount) if state.pot > 0 else 1.0
                # Call if pot odds justify it or aggression is high
                if effective > pot_odds or self.aggression > 0.7:
                    return self._make_call(valid_actions, confidence)

            if self._should_bluff():
                return self._attempt_bluff(valid_actions, effective)
            return PlayerAction.FOLD, 0, confidence

        # Weak hand (<0.3): mostly fold, occasionally bluff.
        # Draws are an exception — they have future potential.
        if self._can_check(valid_actions):
            if draw_bonus > 0.15:
                # Semi-bluff raise with a draw
                if self._should_bluff() and self._can_raise(valid_actions):
                    return self._make_raise(state, player, valid_actions, effective)
                # Take the free card; confidence is lower for draws
                return PlayerAction.CHECK, 0, 0.35 + draw_bonus * 0.6
            return PlayerAction.CHECK, 0, 1.0 - effective

        if self._should_bluff() and call_amount / max(player.chips, 1) < 0.3:
            return self._attempt_bluff(valid_actions, effective)

        # Facing a bet with a draw — pot-odds aware call.
        # A draw_bonus of 0.20 (flush draw) ≈ 35% equity by river.
        # A draw_bonus of 0.30 (flush+gutshot) ≈ 45% equity by river.
        if draw_bonus > 0.15 and call_amount > 0:
            pot_odds = call_amount / (state.pot + call_amount) if state.pot > 0 else 1.0
            # Call when draw equity exceeds required pot odds
            if draw_bonus * 1.2 > pot_odds:
                return self._make_call(valid_actions, 0.35 + draw_bonus * 0.5)

        return PlayerAction.FOLD, 0, 1.0 - effective

    # ======================================================================
    # Hand evaluation
    # ======================================================================

    def _evaluate_preflop_hand(self, cards: List[Card]) -> float:
        """Evaluate preflop hand strength on a 0.0-1.0 scale.

        Roughly calibrated to percentiles:
        * 0.90+  : top ~5%   (AA, KK, QQ, AKs)
        * 0.78+  : top ~15%  (JJ, TT, AKo, AQs, KQs)
        * 0.60+  : top ~35%  (most pairs, suited broadways, AT+)
        * 0.45+  : top ~50%  (any pair, broadways, suited connectors)
        * <0.30  : junk (72o, 83o, etc.)
        """
        if len(cards) != 2:
            return 0.0

        c1, c2 = cards
        r1 = RANK_ORDER[c1.rank]
        r2 = RANK_ORDER[c2.rank]
        suited = c1.suit == c2.suit
        paired = r1 == r2

        high = max(r1, r2)
        low = min(r1, r2)
        gap = high - low - 1  # 0 = connected, 1 = one-gap, 2 = two-gap, etc.

        # --- Pairs: 22=0.52 ... AA=0.98 ------------------------------------
        if paired:
            return 0.52 + (high - 2) / 12.0 * 0.46

        # --- Unpaired ------------------------------------------------------
        # High-card contribution: 2→0.08 ... A→0.50
        base = 0.04 + (high - 2) / 12.0 * 0.46

        # Low-card contribution: adds up to 0.16 for a second high card
        base += (low - 2) / 12.0 * 0.16

        # Suited bonus
        if suited:
            base += 0.07

        # Broadway bonus (both cards 10+)
        if high >= 10 and low >= 10:
            base += 0.06

        # Connectedness bonus
        if gap == 0:
            base += 0.05      # e.g. AK, JT, 98
        elif gap == 1:
            base += 0.03      # e.g. AQ, KT
        elif gap == 2:
            base += 0.01      # e.g. AJ, K9

        # Gap penalty for very disconnected hands
        if gap >= 4:
            base -= 0.02
        if gap >= 5:
            base -= 0.03

        return max(0.0, min(1.0, base))

    def _evaluate_postflop_strength(
        self, hole_cards: List[Card], community_cards: List[Card]
    ) -> float:
        """Evaluate postflop hand strength on a 0.0-1.0 scale.

        Uses :func:`evaluate_hand` for the absolute best 5-card hand and
        normalises the rank value.
        """
        if not hole_cards or not community_cards:
            return 0.0

        rank_val, kickers, _hand_name = evaluate_hand(hole_cards, community_cards)

        # Normalise rank 0-9 to 0.1-0.95
        base = 0.1 + (rank_val / 9.0) * 0.85

        # Kicker bonus within the same rank
        kicker_bonus = 0.0
        if kickers:
            # Top kicker contributes a small boost
            kicker_bonus = (kickers[0] - 2) / 12.0 * 0.04
            # Second kicker (if any) adds a tiny amount
            if len(kickers) > 1:
                kicker_bonus += (kickers[1] - 2) / 12.0 * 0.01

        return min(1.0, base + kicker_bonus)

    def _evaluate_draws(
        self, hole_cards: List[Card], community_cards: List[Card]
    ) -> float:
        """Detect straight and flush draws and return a draw-strength bonus
        in ``[0.0, 0.35]``.

        * 0.30-0.35: open-ended straight + flush draw (combo draw)
        * 0.20-0.25: flush draw (4 to a flush)
        * 0.15-0.20: open-ended straight draw
        * 0.05-0.10: gutshot straight draw
        * 0.00: no draw
        """
        all_cards = list(hole_cards) + list(community_cards)
        if len(all_cards) < 5:
            return 0.0

        # --- Flush draw detection --------------------------------------------
        suits = [c.suit for c in all_cards]
        suit_counts: dict = {}
        for s in suits:
            suit_counts[s] = suit_counts.get(s, 0) + 1
        max_suit_count = max(suit_counts.values()) if suit_counts else 0
        flush_draw = max_suit_count == 4
        # Also detect backdoor flush draw (3 of a suit on flop with 2 to come)
        flush_backdoor = max_suit_count == 3 and len(community_cards) <= 3

        # --- Straight draw detection -----------------------------------------
        ranks = sorted(set(RANK_ORDER[c.rank] for c in all_cards))
        straight_draw = 0.0  # 0=none, 0.5=gutshot, 1.0=open-ended

        # Check for open-ended straight draw (4 consecutive ranks)
        for i in range(len(ranks) - 3):
            window = ranks[i:i + 4]
            if window[-1] - window[0] == 3:
                # Four consecutive — open-ended straight draw
                straight_draw = max(straight_draw, 1.0)
                break
        else:
            # Check for gutshot (needs one specific rank in the middle)
            gutshot_found = False
            for i in range(len(ranks) - 2):
                window = ranks[i:i + 3]
                if 0 < window[-1] - window[0] <= 4:
                    gutshot_found = True
                    break
            # Also check Ace-low wheel draw
            if not gutshot_found and 14 in ranks:
                wheel_ranks = [r for r in ranks if r <= 5 or r == 14]
                if len(wheel_ranks) >= 3:
                    gutshot_found = True
            if gutshot_found:
                straight_draw = 0.5

        # --- Combine into bonus ----------------------------------------------
        bonus = 0.0
        if flush_draw and straight_draw >= 1.0:
            bonus = 0.30  # Combo draw (flush + open-ended)
        elif flush_draw and straight_draw >= 0.5:
            bonus = 0.25  # Flush + gutshot
        elif flush_draw:
            bonus = 0.20  # Flush draw only
        elif straight_draw >= 1.0:
            bonus = 0.15  # Open-ended straight draw
        elif straight_draw >= 0.5:
            bonus = 0.08  # Gutshot
        elif flush_backdoor:
            bonus = 0.03  # Backdoor flush (low value)

        return bonus

    # ======================================================================
    # Action helpers
    # ======================================================================

    def _calculate_raise(
        self,
        state: GameState,
        player: Player,
        strength: float,
        valid_actions: dict,
    ) -> int:
        """Calculate an appropriate raise amount based on hand strength,
        aggression, and pot size.

        Returns a total-bet amount clamped to ``[min_raise, max_raise]``.
        """
        raise_info = valid_actions.get(PlayerAction.RAISE.value, {})
        min_raise = raise_info.get("min", 0)
        max_raise = raise_info.get("max", player.chips)

        if min_raise <= 0:
            return 0

        pot = state.pot

        # Sizing: proportional to pot, scaled by strength and aggression
        # Weak strength -> smaller raise (min-raise or 0.5x pot)
        # Strong strength -> larger raise (0.75x-1.5x pot)
        sizing_factor = 0.5 + strength * self.aggression
        pot_based = int(pot * sizing_factor)

        # Ensure at least min-raise, at most max-raise
        amount = max(min_raise, min(pot_based, max_raise))

        # Add some controlled randomness (+/- 15%)
        jitter = random.uniform(0.85, 1.15)
        amount = int(amount * jitter)

        return max(min_raise, min(amount, max_raise))

    def _make_raise(
        self,
        state: GameState,
        player: Player,
        valid_actions: dict,
        strength: float,
    ) -> Tuple[PlayerAction, int, float]:
        """Construct a raise action with a calculated amount."""
        confidence = 0.6 + strength * 0.35
        amount = self._calculate_raise(state, player, strength, valid_actions)
        return PlayerAction.RAISE, amount, confidence

    def _make_call(
        self, valid_actions: dict, confidence: float
    ) -> Tuple[PlayerAction, int, float]:
        """Construct a call action."""
        call_info = valid_actions.get(PlayerAction.CALL.value, {})
        amount = call_info.get("amount", 0)
        return PlayerAction.CALL, amount, confidence

    def _attempt_bluff(
        self, valid_actions: dict, strength: float
    ) -> Tuple[PlayerAction, int, float]:
        """Attempt a bluff: prefer raising, fall back to calling."""
        if self._can_raise(valid_actions):
            # Weak-hand raise (bluff-raise is smaller)
            raise_info = valid_actions.get(PlayerAction.RAISE.value, {})
            min_raise = raise_info.get("min", 0)
            return PlayerAction.RAISE, min_raise, 0.3
        if self._can_check(valid_actions):
            return PlayerAction.CHECK, 0, 0.3
        call_info = valid_actions.get(PlayerAction.CALL.value, {})
        return PlayerAction.CALL, call_info.get("amount", 0), 0.3

    # ======================================================================
    # Predicates
    # ======================================================================

    def _should_bluff(self) -> bool:
        """Return ``True`` if the player should attempt a bluff this hand."""
        return random.random() < self.bluff_freq

    @staticmethod
    def _can_check(valid_actions: dict) -> bool:
        """Return ``True`` if CHECK is a valid action."""
        return PlayerAction.CHECK.value in valid_actions

    @staticmethod
    def _can_raise(valid_actions: dict) -> bool:
        """Return ``True`` if RAISE is a valid action."""
        return PlayerAction.RAISE.value in valid_actions

    @staticmethod
    def _position_multiplier(position: Optional[Position]) -> float:
        """Return a position-strength multiplier.

        Later positions get a bonus (more information), early positions
        get a penalty.
        """
        multipliers = {
            Position.BTN: 1.12,
            Position.CO: 1.06,
            Position.MP: 1.00,
            Position.UTG: 0.94,
            Position.BB: 0.96,
            Position.SB: 0.90,
        }
        if position is None:
            return 1.0
        return multipliers.get(position, 1.0)

    @staticmethod
    def _default_valid_actions(
        state: GameState, player: Player
    ) -> dict:
        """Derive a minimal valid-actions dict from *state* when the caller
        does not supply one from :class:`BettingRound`.

        This is a simplified fallback and may not be 100 % accurate for
        pot-limit min-raise calculations.
        """
        actions: dict = {}

        # Always allow fold
        actions[PlayerAction.FOLD.value] = {
            "action": PlayerAction.FOLD,
            "amount": 0,
        }

        call_amount = max(0, state.current_bet - (player.current_bet or 0))

        if call_amount == 0:
            actions[PlayerAction.CHECK.value] = {
                "action": PlayerAction.CHECK,
                "amount": 0,
            }
        else:
            if call_amount >= player.chips:
                actions[PlayerAction.ALL_IN.value] = {
                    "action": PlayerAction.ALL_IN,
                    "amount": player.chips,
                }
            else:
                actions[PlayerAction.CALL.value] = {
                    "action": PlayerAction.CALL,
                    "amount": call_amount,
                }
                actions[PlayerAction.ALL_IN.value] = {
                    "action": PlayerAction.ALL_IN,
                    "amount": player.chips,
                }

        # Raise
        bb = state.blinds.big if state.blinds else 10
        min_raise = max(bb, state.current_bet + bb)
        if player.chips > call_amount:
            actions[PlayerAction.RAISE.value] = {
                "action": PlayerAction.RAISE,
                "amount": -1,
                "min": min_raise,
                "max": player.chips,
            }
            if PlayerAction.ALL_IN.value not in actions:
                actions[PlayerAction.ALL_IN.value] = {
                    "action": PlayerAction.ALL_IN,
                    "amount": player.chips,
                }

        return actions

    # ======================================================================
    # LLM trigger
    # ======================================================================

    @staticmethod
    def should_use_llm(
        state: GameState,
        player: Player,
        confidence: float,
        trigger_config: Optional[dict] = None,
    ) -> bool:
        """Determine whether the LLM should be consulted for this decision.

        The LLM is triggered when:

        1. The rule engine's confidence is below the threshold.
        2. The pot-to-stack ratio is high (significant decision).
        3. An all-in decision is being faced.
        4. The hand is on a late street (turn or river).

        Args:
            state: Current game state.
            player: The AI player making the decision.
            confidence: The rule engine's confidence in its decision (0-1).
            trigger_config: Dict of trigger thresholds from
                ``config/llm_config.yaml``.

        Returns:
            ``True`` if the LLM should be consulted.
        """
        if trigger_config is None:
            return False

        # 1. Low confidence
        threshold = trigger_config.get("confidence_threshold", 0.6)
        if confidence < threshold:
            return True

        # 2. High pot-to-stack ratio
        if player.chips > 0 and state.pot > 0:
            pot_ratio = state.pot / (player.chips + state.pot)
            ptr_threshold = trigger_config.get("pot_to_stack_ratio", 0.3)
            if pot_ratio > ptr_threshold:
                return True

        # 3. All-in situations
        if trigger_config.get("enable_on_allin", True):
            call_amount = max(0, state.current_bet - (player.current_bet or 0))
            if player.chips > 0 and call_amount >= player.chips * 0.5:
                return True

        # 4. Late street
        if trigger_config.get("enable_on_late_street", True):
            if state.phase in (GamePhase.TURN, GamePhase.RIVER):
                return True

        return False

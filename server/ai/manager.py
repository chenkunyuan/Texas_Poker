"""
AI Manager for Texas Hold'em Poker.

Orchestrates the full AI decision pipeline:

1. Rule engine produces a baseline decision + confidence score.
2. If confidence is below the LLM trigger threshold (or the situation
   warrants it), the LLM is consulted.
3. A realistic thinking delay is applied before returning the result.

**Data Isolation**: When building the LLM prompt, ONLY the current
player's hole cards are included.  Other players' private cards are
NEVER accessed.
"""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, Tuple

import yaml

from server.ai.prompts import build_poker_prompt
from server.ai.rule_engine import RuleEngine
from server.llm.client import LLMClient, LLMClientFactory, LLMDecision
from server.models.schemas import (
    GameState,
    PersonalityProfile,
    Player,
    PlayerAction,
)

logger = logging.getLogger(__name__)

# Default path to the LLM trigger / timing config
_DEFAULT_LLM_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "llm_config.yaml"
)


class AIManager:
    """Central AI coordinator for all non-human players.

    Maintains one :class:`RuleEngine` per AI player (keyed by player ID)
    and optionally delegates to an LLM when the rule engine's confidence
    is low or the situation is high-stakes.

    Typical usage inside :class:`GameController`::

        manager = AIManager(llm_client=LLMClientFactory.create())
        for ai_player in ai_players:
            manager.register_player(ai_player.id, ai_player.personality)
        ...
        action, amount, source = await manager.get_decision(state, player)
    """

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        self.llm_client = llm_client
        self.engines: dict[str, RuleEngine] = {}

        # Load trigger configuration
        self._trigger_config: dict = {}
        self._decision_timing: dict[str, int] = {
            "rule_delay_min_sec": 2,
            "rule_delay_max_sec": 5,
            "llm_extra_delay_sec": 0,
        }
        self._load_config()

    # ======================================================================
    # Registration
    # ======================================================================

    def register_player(
        self, player_id: str, personality: Optional[PersonalityProfile]
    ) -> None:
        """Create and store a :class:`RuleEngine` for *player_id*.

        Args:
            player_id: Unique identifier matching :attr:`Player.id`.
            personality: The player's personality profile.  If ``None`` a
                balanced default is used.
        """
        if personality is None:
            personality_dict = {
                "aggression": 0.5,
                "bluff_frequency": 0.1,
                "preflop_range_pct": 25,
                "fold_to_3bet": 0.4,
            }
        else:
            personality_dict = {
                "aggression": personality.aggression,
                "bluff_frequency": personality.bluff_frequency,
                "preflop_range_pct": personality.preflop_range_pct,
                "fold_to_3bet": personality.fold_to_3bet,
            }

        self.engines[player_id] = RuleEngine(personality_dict)

    # ======================================================================
    # Decision pipeline
    # ======================================================================

    async def get_decision(
        self,
        state: GameState,
        player: Player,
        valid_actions: Optional[dict] = None,
    ) -> Tuple[PlayerAction, int, str]:
        """Run the full AI decision pipeline for *player*.

        Steps:

        1. :class:`RuleEngine` produces a baseline decision and confidence.
        2. :meth:`RuleEngine.should_use_llm` checks whether the LLM should
           override the rule-engine decision.
        3. If yes, :meth:`_call_llm` is invoked and its result used.
        4. A realistic thinking delay is applied.
        5. The final ``(action, amount, source)`` tuple is returned, where
           *source* is ``"RULE"`` or ``"LLM"``.

        Args:
            state: The current (mutable) game state.
            player: The AI player whose turn it is.
            valid_actions: Dict from :meth:`BettingRound.get_valid_actions`.
                When ``None`` the rule engine derives a minimal default.

        Returns:
            ``(action, amount, source)`` — *source* is ``"RULE"`` or
            ``"LLM"``.
        """
        # --- 1. Rule engine baseline -----------------------------------------
        engine = self.engines.get(player.id)
        if engine is None:
            # Lazy registration with balanced default
            self.register_player(player.id, player.personality)
            engine = self.engines[player.id]

        action, amount, confidence = engine.decide(state, player, valid_actions)

        # --- 2. Check LLM trigger --------------------------------------------
        use_llm = False
        if self.llm_client is not None and self._trigger_config:
            use_llm = RuleEngine.should_use_llm(
                state, player, confidence, self._trigger_config
            )

        # --- 3. LLM override -------------------------------------------------
        decision_source = "RULE"
        if use_llm:
            try:
                llm_action, llm_amount = await self._call_llm(state, player, valid_actions)
                action = llm_action
                amount = llm_amount
                decision_source = "LLM"
            except Exception as exc:
                logger.warning(
                    "LLM decision unavailable for player %s: %s; using rule engine.",
                    player.id,
                    type(exc).__name__,
                )
                # Fall back to rule-engine decision (already set above)

        # --- 4. Thinking delay -----------------------------------------------
        await self._apply_thinking_delay(decision_source)

        return action, amount, decision_source

    # ======================================================================
    # LLM invocation (DATA ISOLATION CRITICAL)
    # ======================================================================

    async def _call_llm(
        self,
        state: GameState,
        player: Player,
        valid_actions: Optional[dict] = None,
    ) -> Tuple[PlayerAction, int]:
        """Build a prompt with ONLY public information + *player*'s own
        hole cards, send it to the LLM, and parse the response.

        **DATA ISOLATION**:  This method NEVER accesses
        ``other_player.hole_cards``.  The prompt contains:

        * *player*'s hole cards (2 cards).
        * Community cards (shared, visible to all).
        * Pot size.
        * Current bet.
        * *player*'s chip count.
        * *player*'s position.
        * Action history (public actions only — no hole-card leaks).
        * Game variant.

        Returns:
            ``(action, amount)`` parsed from the LLM response.
        """
        if self.llm_client is None:
            raise RuntimeError("LLM client is not configured.")

        # --- Build the prompt (DATA ISOLATION: only player's own cards) ------
        prompt = build_poker_prompt(
            personality=player.personality,
            hole_cards=player.hole_cards,
            community_cards=state.community_cards,
            pot=state.pot,
            current_bet=state.current_bet,
            player_chips=player.chips,
            position=player.position,
            action_history=state.action_history,
            variant=state.config.variant if state.config else "no_limit",
            valid_actions=valid_actions,
        )

        # --- Query the LLM ---------------------------------------------------
        decision: LLMDecision = await self.llm_client.decide(prompt)

        # Map string action to PlayerAction enum
        action_map = {
            "FOLD": PlayerAction.FOLD,
            "CHECK": PlayerAction.CHECK,
            "CALL": PlayerAction.CALL,
            "RAISE": PlayerAction.RAISE,
            "ALL_IN": PlayerAction.ALL_IN,
        }
        action = action_map.get(decision.action.upper(), PlayerAction.FOLD)

        # --- Validate against actually available actions ---------------------
        if valid_actions:
            # If the LLM chose an action that is not valid, fall back safely
            if action.value not in valid_actions:
                logger.warning(
                    "LLM chose invalid action '%s' for player %s. "
                    "Falling back to safest valid action.",
                    decision.action,
                    player.id,
                )
                action, amount = self._safe_fallback(valid_actions)
                return action, amount

            # If LLM chose RAISE, clamp the amount to [min, max]
            if action == PlayerAction.RAISE:
                raise_info = valid_actions.get(PlayerAction.RAISE.value, {})
                min_r = raise_info.get("min", 0)
                max_r = raise_info.get("max", player.chips)
                amount = max(min_r, min(decision.amount, max_r))

            # If LLM chose ALL_IN, use the actual all-in amount
            elif action == PlayerAction.ALL_IN:
                all_in_info = valid_actions.get(PlayerAction.ALL_IN.value, {})
                amount = all_in_info.get("amount", player.chips)

            # If LLM chose CALL, use the actual call amount
            elif action == PlayerAction.CALL:
                call_info = valid_actions.get(PlayerAction.CALL.value, {})
                amount = call_info.get("amount", 0)

        return action, amount

    # ======================================================================
    # Helpers
    # ======================================================================

    @staticmethod
    def _safe_fallback(valid_actions: dict) -> Tuple[PlayerAction, int]:
        """Return the safest valid action when the LLM produces an invalid one.

        Preference order: CHECK > CALL > FOLD.
        """
        if "CHECK" in valid_actions:
            return PlayerAction.CHECK, 0
        if "CALL" in valid_actions:
            call_info = valid_actions["CALL"]
            return PlayerAction.CALL, call_info.get("amount", 0)
        return PlayerAction.FOLD, 0

    async def _apply_thinking_delay(self, source: str) -> None:
        """Apply a realistic thinking delay before the AI acts.

        Args:
            source: ``"RULE"`` or ``"LLM"`` — LLM decisions may add extra
                delay.
        """
        min_delay = self._decision_timing.get("rule_delay_min_sec", 2)
        max_delay = self._decision_timing.get("rule_delay_max_sec", 5)

        if source == "LLM":
            extra = self._decision_timing.get("llm_extra_delay_sec", 0)
            min_delay += extra
            max_delay += extra

        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    # ======================================================================
    # Config loading
    # ======================================================================

    def _load_config(self) -> None:
        """Load LLM trigger and timing configuration from YAML.

        On any error the defaults (empty trigger config, 2-5 s delay) are
        kept so the AI remains functional.
        """
        try:
            if _DEFAULT_LLM_CONFIG_PATH.exists():
                with open(_DEFAULT_LLM_CONFIG_PATH, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}

                # LLM trigger thresholds
                trigger = data.get("trigger", {})
                if isinstance(trigger, dict):
                    self._trigger_config = trigger

                # Decision timing (can also be in personalities.yaml, but
                # we also check here for convenience)
                timing = data.get("decision_timing", {})
                if isinstance(timing, dict):
                    for key in ("rule_delay_min_sec", "rule_delay_max_sec",
                                "llm_extra_delay_sec"):
                        if key in timing:
                            self._decision_timing[key] = int(timing[key])

        except Exception:
            logger.warning(
                "Could not load LLM config from %s; using defaults.",
                _DEFAULT_LLM_CONFIG_PATH,
            )

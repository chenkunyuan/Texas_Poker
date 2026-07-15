"""
Texas Hold'em Poker — Game Controller.

Orchestrates the full game lifecycle: hand dealing, betting rounds,
showdown resolution, and event emission to connected clients.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import random
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Optional, Tuple

import yaml

from server.models.schemas import (
    Action,
    BlindsConfig,
    Card,
    GameConfig,
    GamePhase,
    GameState,
    PersonalityProfile,
    PersonalityType,
    Player,
    PlayerAction,
    Position,
)
from server.engine.betting import BettingRound
from server.engine.dealer import Dealer
from server.engine.evaluator import evaluate_hand
from server.engine.pot import PotCalculator


# ---------------------------------------------------------------------------
# Hand-score encoding helper
# ---------------------------------------------------------------------------

def _encode_hand_score(rank_val: int, kickers: List[int]) -> int:
    """Encode hand rank + kickers into a single integer for comparison.

    Each kicker is shifted into its own base-100 "digit" so that ordering
    is preserved and ties are correctly detected.
    """
    score = rank_val
    for k in kickers:
        score = score * 100 + k
    return score


def _hand_score_for_distribution(
    hole_cards: List[Card], community_cards: List[Card]
) -> int:
    """Wrapper matching the signature expected by
    :meth:`PotCalculator.distribute_pots`."""
    rank_val, kickers, __ = evaluate_hand(hole_cards, community_cards)
    return _encode_hand_score(rank_val, kickers)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PERSONALITIES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "personalities.yaml"
)


# ---------------------------------------------------------------------------
# GameController
# ---------------------------------------------------------------------------


class GameController:
    """Full state-machine orchestrator for a single Texas Hold'em game.

    Responsibilities
    ----------------
    * Player initialisation (human + AI) with personality profiles.
    * Per-hand lifecycle: deal, betting rounds, showdown, pot distribution.
    * Event emission for connected WebSocket clients.
    * Human-action synchronisation via ``asyncio.Event``.
    * Placeholder AI decision-making (random action with realistic delay).
    """

    def __init__(self, config: GameConfig, game_id: str) -> None:
        self.game_id = game_id
        self.config = config

        # Seeds the initial blinds from config into GameState so the dealer
        # and betting engine always have access to them.
        self.state = GameState(
            config=config,
            blinds=config.blinds,
        )
        self.dealer = Dealer(self.state)

        # Event callback registry:  event_name -> async callable
        self.callbacks: Dict[str, Callable[..., Coroutine[Any, Any, None]]] = {}

        # Human-action synchronisation
        self._human_action: Optional[Dict[str, Any]] = None
        self._human_action_event = asyncio.Event()
        self._pending_human_turn: Optional[Dict[str, Any]] = None
        self._human_turn_lock = asyncio.Lock()

        # Personality / timing registry loaded from YAML
        self._personality_registry: Dict[str, PersonalityProfile] = {}
        self._decision_timing: Dict[str, int] = {
            "rule_delay_min_sec": 2,
            "rule_delay_max_sec": 5,
            "llm_extra_delay_sec": 0,
        }
        self._load_personalities()

    # ======================================================================
    # Event system
    # ======================================================================

    def on(self, event: str, callback: Callable[..., Coroutine[Any, Any, None]]) -> None:
        """Register an async callback for *event*.

        Typical events:

        * ``"game_state"``
        * ``"your_turn"``
        * ``"player_action"``
        * ``"ai_thinking"``
        * ``"community_updated"``
        * ``"hand_result"``
        * ``"game_over"``
        """
        self.callbacks[event] = callback

    async def _emit(self, event: str, data: Any = None) -> None:
        """Fire *event*, invoking the registered callback (if any)."""
        if event in self.callbacks:
            await self.callbacks[event](data)

    # ======================================================================
    # Player initialisation
    # ======================================================================

    def init_players(
        self, personalities: Optional[List[PersonalityProfile]] = None
    ) -> None:
        """Create the human player and the configured number of AI opponents.

        Args:
            personalities: Optional manual personality list used when
                ``config.personality_mode == "manual"``.  If ``None`` and the
                mode is ``"manual"``, falls back to
                ``config.manual_personalities``.
        """
        self.state.players = []

        # --- Human player -------------------------------------------------------
        human = Player(
            id="human",
            name="You",
            is_human=True,
            chips=self.config.starting_chips,
        )
        self.state.players.append(human)

        # --- AI players ---------------------------------------------------------
        effective_personalities: List[PersonalityProfile] = []
        if self.config.personality_mode == "manual":
            effective_personalities = (
                personalities or self.config.manual_personalities or []
            )
            if len(effective_personalities) < self.config.ai_player_count:
                remaining = self.config.ai_player_count - len(effective_personalities)
                effective_personalities.extend(self._random_personalities(remaining))
        else:
            # "random" mode — pick N random profiles
            effective_personalities = self._random_personalities(
                self.config.ai_player_count
            )

        for i, profile in enumerate(effective_personalities):
            ai = Player(
                id=f"ai_{i + 1}",
                name=profile.name or f"AI {i + 1}",
                is_human=False,
                chips=self.config.starting_chips,
                personality=profile,
            )
            self.state.players.append(ai)

        # Initialise the dealer button at a random position so hands aren't
        # biased towards one seating.
        if self.state.players:
            self.state.dealer_index = random.randrange(len(self.state.players))

    # ======================================================================
    # Main game loop
    # ======================================================================

    async def run(self) -> None:
        """Play hands until fewer than 2 players have chips remaining."""
        self.state.phase = GamePhase.SETUP
        await self._emit("game_state", self.state)

        while not self._is_game_over():
            await self._play_hand()

            # Remove players who busted (no chips left).
            self._remove_busted_players()

        # --- Game over ----------------------------------------------------------
        self.state.phase = GamePhase.GAME_OVER

        rankings = self._build_rankings()
        stats = self._build_stats()

        await self._emit("game_over", {
            "rankings": rankings,
            "stats": stats,
            "replay_id": None,  # Task 12 will wire this
        })

    # ======================================================================
    # Single hand
    # ======================================================================

    async def _play_hand(self) -> None:
        """Run one complete hand: deal, betting rounds, showdown."""

        # Guard: need at least 2 players with chips.
        if self._is_game_over():
            return

        # --- Deal a new hand ----------------------------------------------------
        # The dealer mutates state in-place: resets per-hand fields, rotates
        # the button, assigns positions, posts blinds, shuffles & deals.
        self.dealer.start_new_hand()

        await self._emit("game_state", self.state)

        # --- Pre-flop betting round ---------------------------------------------
        hand_over = await self._run_phase(GamePhase.PRE_FLOP)
        if hand_over:
            return

        # --- Flop (3 community cards) -------------------------------------------
        self.state.phase = GamePhase.FLOP
        self.dealer.deal_community(3)
        await self._emit("community_updated", self.state.community_cards)
        await self._emit("game_state", self.state)
        hand_over = await self._run_phase(GamePhase.FLOP)
        if hand_over:
            return

        # --- Turn (1 community card) --------------------------------------------
        self.state.phase = GamePhase.TURN
        self.dealer.deal_community(1)
        await self._emit("community_updated", self.state.community_cards)
        await self._emit("game_state", self.state)
        hand_over = await self._run_phase(GamePhase.TURN)
        if hand_over:
            return

        # --- River (1 community card) -------------------------------------------
        self.state.phase = GamePhase.RIVER
        self.dealer.deal_community(1)
        await self._emit("community_updated", self.state.community_cards)
        await self._emit("game_state", self.state)
        hand_over = await self._run_phase(GamePhase.RIVER)
        if hand_over:
            return

        # --- Showdown -----------------------------------------------------------
        await self._showdown()

    async def _run_phase(self, phase: GamePhase) -> bool:
        """Run a single betting round for *phase*.

        Returns:
            ``True`` if the hand ended early (everyone folded except one),
            ``False`` if the hand continues to the next phase.
        """
        hand_ended = await self._run_betting_round()

        if hand_ended:
            await self._handle_early_win()
            return True

        return False

    # ======================================================================
    # Betting round
    # ======================================================================

    async def _run_betting_round(self) -> bool:
        """Execute a full betting round.

        Loops through players in action order (determined by the dealer from
        the current phase), collecting actions until the round is complete or
        only one active player remains.

        Returns:
            ``True`` if the hand ended early (only one active player left),
            ``False`` otherwise.
        """
        variant = self.config.variant if self.config else "no_limit"
        betting = BettingRound(self.state, variant)
        action_order = self.dealer.get_action_order()

        if not action_order:
            return True

        # Safety ceiling: prevent infinite loops from unexpected state.
        # Each player should act at most a few times per round (fold/check/call
        # once, plus one extra action per raise they face).
        max_iterations = len(action_order) * 8
        iterations = 0
        idx = 0
        n = len(action_order)

        while not betting.is_round_complete() and iterations < max_iterations:
            iterations += 1
            player = action_order[idx % n]

            # Skip players who are folded, all-in, or have already acted.
            if not player.is_active or player.is_all_in or player.has_acted_this_round:
                idx += 1
                continue

            self.state.current_player_index = idx % n

            # --- Collect action --------------------------------------------------
            action, amount = await self._get_player_action(player, betting)

            # --- Apply action ----------------------------------------------------
            betting.apply_action(player, action, amount)

            # Record in history for replay / UI
            self.state.action_history.append({
                "player_id": player.id,
                "action": action.value,
                "amount": amount,
            })

            # --- Emit events ----------------------------------------------------
            await self._emit("player_action", {
                "player_id": player.id,
                "player_name": player.name,
                "action": action.value,
                "amount": amount,
            })
            await self._emit("game_state", self.state)

            # --- Early termination -----------------------------------------------
            if self._is_hand_over_early():
                self._end_betting_round()
                return True

            idx += 1

        # --- Cleanup after round ------------------------------------------------
        self._end_betting_round()
        await self._emit("game_state", self.state)
        return False

    def _end_betting_round(self) -> None:
        """Reset per-round player state so the next betting round starts clean.

        ``total_bet_this_round`` is left untouched — it accumulates across
        the entire hand and is needed for side-pot calculation at showdown.
        """
        self.state.current_bet = 0
        for p in self.state.players:
            p.current_bet = 0
            p.has_acted_this_round = False
        self.state.current_player_index = None

    # ======================================================================
    # Action collection
    # ======================================================================

    async def _get_player_action(
        self, player: Player, betting: BettingRound
    ) -> Tuple[PlayerAction, int]:
        """Dispatch action collection to the right handler (human vs AI)."""
        if player.is_human:
            return await self._get_human_action(betting, player)
        else:
            return await self._get_ai_action(player, betting)

    # ----------------------------------------------------------------------
    # Human action
    # ----------------------------------------------------------------------

    @property
    def pending_human_turn(self) -> Optional[Dict[str, Any]]:
        """Return an isolated snapshot of the outstanding human turn."""
        if self._pending_human_turn is None:
            return None
        return deepcopy(self._pending_human_turn)

    async def replay_pending_human_turn(
        self,
        send: Callable[[Dict[str, Any]], Awaitable[None]],
        send_timeout: float = 5.0,
    ) -> bool:
        """Atomically replay the outstanding turn through *send*, if any."""
        async with self._human_turn_lock:
            if self._pending_human_turn is None:
                return False
            await asyncio.wait_for(
                send(deepcopy(self._pending_human_turn)),
                timeout=send_timeout,
            )
            return True

    async def _get_human_action(
        self, betting: BettingRound, player: Player
    ) -> Tuple[PlayerAction, int]:
        """Wait for the human player to submit an action via
        :meth:`submit_human_action`."""
        valid_actions = betting.get_valid_actions(player)
        raise_info = valid_actions.get(PlayerAction.RAISE.value, {})

        call_amount = 0
        call_info = valid_actions.get(PlayerAction.CALL.value)
        if call_info:
            call_amount = call_info.get("amount", 0)

        # Reformat valid_actions for the client: action enum -> string
        client_actions: Dict[str, dict] = {}
        for key, info in valid_actions.items():
            entry: dict = dict(info)
            if isinstance(entry.get("action"), PlayerAction):
                entry["action"] = entry["action"].value
            client_actions[key] = entry

        turn_payload = {
            "valid_actions": client_actions,
            "min_raise": raise_info.get("min", 0),
            "max_raise": raise_info.get("max", 0),
            "call_amount": call_amount,
        }

        # Prepare the waiter before publishing the turn so an immediate
        # response from the client cannot be cleared and lost.
        async with self._human_turn_lock:
            self._human_action_event.clear()
            self._human_action = None
            self._pending_human_turn = deepcopy(turn_payload)
        try:
            await self._emit("your_turn", deepcopy(turn_payload))
            await self._human_action_event.wait()
            action_data = self._human_action or {}
        finally:
            # Also clear on callback failure or task cancellation so a game
            # that stops while waiting never leaves a stale replay payload.
            async with self._human_turn_lock:
                self._pending_human_turn = None

        action_str = action_data.get("action", "FOLD").upper()
        amount = action_data.get("amount", 0)

        # Map string to PlayerAction enum
        action_map = {
            "FOLD": PlayerAction.FOLD,
            "CHECK": PlayerAction.CHECK,
            "CALL": PlayerAction.CALL,
            "RAISE": PlayerAction.RAISE,
            "ALL_IN": PlayerAction.ALL_IN,
        }
        action = action_map.get(action_str, PlayerAction.FOLD)

        # Safety: if the submitted action is not currently valid, fall back
        # to a legal alternative.
        if action.value not in valid_actions:
            if PlayerAction.CHECK.value in valid_actions:
                action = PlayerAction.CHECK
                amount = 0
            else:
                action = PlayerAction.FOLD
                amount = 0

        return action, amount

    async def submit_human_action(self, action: str, amount: int = 0) -> bool:
        """Called by the WebSocket handler when the human player acts.

        Args:
            action: One of ``"FOLD"``, ``"CHECK"``, ``"CALL"``, ``"RAISE"``,
                    ``"ALL_IN"``.
            amount: The bet amount (meaningful for RAISE / ALL_IN).

        Returns:
            ``True`` when this is the first action for the pending human turn;
            ``False`` when no human action is currently pending.
        """
        async with self._human_turn_lock:
            if self._pending_human_turn is None:
                return False
            self._human_action = {"action": action.upper(), "amount": amount}
            self._pending_human_turn = None
            self._human_action_event.set()
            return True

    # ----------------------------------------------------------------------
    # AI action (placeholder — Task 10 will replace with real AI)
    # ----------------------------------------------------------------------

    async def _get_ai_action(
        self, player: Player, betting: BettingRound
    ) -> Tuple[PlayerAction, int]:
        """Placeholder AI: pick a random valid action after a realistic delay.

        The delay is read from ``config/personalities.yaml`` (default 2-5 s).
        This method will be replaced by the real AI engine in Task 10.
        """
        # --- Delay for realism --------------------------------------------------
        min_delay = self._decision_timing.get("rule_delay_min_sec", 2)
        max_delay = self._decision_timing.get("rule_delay_max_sec", 5)
        delay = random.uniform(min_delay, max_delay)

        # Notify clients that an AI is "thinking"
        await self._emit("ai_thinking", {
            "player_id": player.id,
            "player_name": player.name,
        })

        await asyncio.sleep(delay)

        # --- Pick a random valid action -----------------------------------------
        valid_actions = betting.get_valid_actions(player)

        if not valid_actions:
            return PlayerAction.FOLD, 0

        # Weighted pool: favour calling/checking, sometimes fold, less often
        # raise, and rarely all-in.
        weights = {
            PlayerAction.FOLD.value: 10,
            PlayerAction.CHECK.value: 25,
            PlayerAction.CALL.value: 40,
            PlayerAction.RAISE.value: 15,
            PlayerAction.ALL_IN.value: 5,
        }

        pool: List[str] = []
        pool_weights: List[float] = []
        for key, info in valid_actions.items():
            w = weights.get(key, 5)
            pool.append(key)
            pool_weights.append(w)

        if not pool:
            return PlayerAction.FOLD, 0

        chosen_key = random.choices(pool, weights=pool_weights, k=1)[0]
        chosen_info = valid_actions[chosen_key]
        action = chosen_info["action"]

        # Determine the amount
        amount = chosen_info.get("amount", 0)
        if action == PlayerAction.RAISE and "min" in chosen_info and "max" in chosen_info:
            mn = chosen_info["min"]
            mx = chosen_info["max"]
            if mx > mn:
                amount = random.randint(mn, mx)
            else:
                amount = mn
        elif action == PlayerAction.ALL_IN:
            amount = chosen_info.get("amount", 0)

        return action, amount

    # ======================================================================
    # Showdown
    # ======================================================================

    async def _showdown(self) -> None:
        """Resolve the hand: calculate side pots, evaluate hands, distribute
        chips, and emit results."""
        self.state.phase = GamePhase.SHOWDOWN
        await self._emit("game_state", self.state)

        # Players who can win (haven't folded)
        live_players = [p for p in self.state.players if p.is_active]

        if not live_players:
            # Should not happen — early-win would have triggered first.
            return

        # --- Side pots ----------------------------------------------------------
        side_pots = PotCalculator.calculate_side_pots(self.state.players)
        self.state.side_pots = side_pots

        # --- Evaluate and distribute --------------------------------------------
        distributions = PotCalculator.distribute_pots(
            side_pots,
            self.state.players,
            self.state.community_cards,
            _hand_score_for_distribution,
        )

        # --- Build hand descriptions for display --------------------------------
        hands: Dict[str, str] = {}
        for p in live_players:
            if p.hole_cards:
                __, __, hand_name = evaluate_hand(
                    p.hole_cards, self.state.community_cards
                )
                hands[p.id] = hand_name

        # --- Collect winners across all side pots -------------------------------
        winner_ids: set[str] = set()
        for dist in distributions:
            for wid in dist.get("winners", []):
                winner_ids.add(wid)

        winners_list: List[dict] = []
        for wid in winner_ids:
            wp = self.state.get_player_by_id(wid)
            winners_list.append({
                "player_id": wid,
                "player_name": wp.name if wp else wid,
            })

        # --- Emit hand result ---------------------------------------------------
        await self._emit("hand_result", {
            "winners": winners_list,
            "hands": hands,
            "pot_distribution": distributions,
        })
        await self._emit("game_state", self.state)

        self.state.phase = GamePhase.HAND_END

    # ======================================================================
    # Helpers
    # ======================================================================

    def _is_hand_over_early(self) -> bool:
        """Return ``True`` when only one active (non-folded) player remains.

        That player wins the pot without a showdown.
        """
        active = [p for p in self.state.players if p.is_active]
        return len(active) <= 1

    async def _handle_early_win(self) -> None:
        """Award the pot to the sole remaining player (everyone else folded)."""
        active = [p for p in self.state.players if p.is_active]
        if not active:
            return

        winner = active[0]
        pot_amount = self.state.pot
        winner.chips += pot_amount
        self.state.pot = 0
        self.state.phase = GamePhase.HAND_END

        await self._emit("hand_result", {
            "winners": [
                {"player_id": winner.id, "player_name": winner.name}
            ],
            "hands": {},
            "pot_distribution": [
                {
                    "pot_amount": pot_amount,
                    "winners": [winner.id],
                    "winning_score": 0,
                    "split_amount": pot_amount,
                }
            ],
        })
        await self._emit("game_state", self.state)

    def _is_game_over(self) -> bool:
        """Return ``True`` when fewer than 2 players have chips."""
        players_with_chips = [p for p in self.state.players if p.chips > 0]
        return len(players_with_chips) < 2

    def _remove_busted_players(self) -> None:
        """Remove players with no chips from the table.

        The human player is never removed — they stay to observe even when
        busted.
        """
        self.state.players = [
            p
            for p in self.state.players
            if p.chips > 0 or p.is_human
        ]

    # Blinds are increased automatically inside Dealer.start_new_hand() via
    # Dealer._update_blinds(), so the controller does not need a separate
    # increase method.

    def _build_rankings(self) -> List[dict]:
        """Build a final ranking table sorted by chips (descending)."""
        sorted_players = sorted(
            self.state.players, key=lambda p: p.chips, reverse=True
        )
        return [
            {
                "player_id": p.id,
                "player_name": p.name,
                "chips": p.chips,
                "is_human": p.is_human,
            }
            for p in sorted_players
        ]

    def _build_stats(self) -> Dict[str, dict]:
        """Build per-player statistics for the final summary."""
        stats: Dict[str, dict] = {}
        for p in self.state.players:
            stats[p.id] = {
                "final_chips": p.chips,
                "starting_chips": self.config.starting_chips,
                "net": p.chips - self.config.starting_chips,
            }
        return stats

    # ======================================================================
    # Personality loading
    # ======================================================================

    def _load_personalities(self) -> None:
        """Parse the personalities YAML file and populate the registry.

        On any error the registry stays empty and :meth:`_random_personalities`
        falls back to hard-coded defaults.
        """
        try:
            if _PERSONALITIES_PATH.exists():
                with open(_PERSONALITIES_PATH, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}

                # Decision timing
                timing = data.get("decision_timing", {})
                if timing:
                    self._decision_timing.update(timing)

                # Personality profiles
                profiles = data.get("personalities", {})
                for key, vals in profiles.items():
                    if not isinstance(vals, dict):
                        continue

                    # Map the YAML key to a PersonalityType enum
                    key_upper = key.upper().replace(" ", "_")
                    try:
                        ptype = PersonalityType(key_upper)
                    except ValueError:
                        ptype = PersonalityType.TAG

                    profile = PersonalityProfile(
                        type=ptype,
                        name=vals.get("name", vals.get("description", key)),
                        preflop_range_pct=vals.get("preflop_range_pct", 15),
                        aggression=vals.get("aggression", 0.5),
                        bluff_frequency=vals.get("bluff_frequency", 0.1),
                        fold_to_3bet=vals.get("fold_to_3bet", 0.5),
                    )
                    self._personality_registry[key_upper] = profile

        except Exception:
            # If YAML loading fails, the registry stays empty and
            # _random_personalities will return TAG defaults.
            pass

    def _random_personalities(self, count: int) -> List[PersonalityProfile]:
        """Return *count* randomly chosen personality profiles.

        Cycles through the available profiles if *count* exceeds the number
        in the registry.
        """
        available = list(self._personality_registry.values())
        if not available:
            # Fallback defaults when YAML is missing or unparseable
            available = [
                PersonalityProfile(
                    type=PersonalityType.TAG,
                    name="Tight-Aggressive",
                    preflop_range_pct=15,
                    aggression=0.8,
                    bluff_frequency=0.15,
                    fold_to_3bet=0.4,
                ),
                PersonalityProfile(
                    type=PersonalityType.LAG,
                    name="Loose-Aggressive",
                    preflop_range_pct=35,
                    aggression=0.95,
                    bluff_frequency=0.35,
                    fold_to_3bet=0.2,
                ),
                PersonalityProfile(
                    type=PersonalityType.NIT,
                    name="Tight-Passive",
                    preflop_range_pct=8,
                    aggression=0.2,
                    bluff_frequency=0.03,
                    fold_to_3bet=0.7,
                ),
                PersonalityProfile(
                    type=PersonalityType.CALLING_STATION,
                    name="Loose-Passive",
                    preflop_range_pct=50,
                    aggression=0.15,
                    bluff_frequency=0.05,
                    fold_to_3bet=0.1,
                ),
            ]

        if count <= 0:
            return []

        # Shuffle and cycle through if more are needed
        result: List[PersonalityProfile] = []
        shuffled = list(available)
        random.shuffle(shuffled)
        for i in range(count):
            result.append(shuffled[i % len(shuffled)])
        return result

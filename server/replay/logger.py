"""
Replay Logger for Texas Hold'em Poker.

Records every hand played in a game so it can be reviewed later.
Produces self-contained JSON files under the ``replays/`` directory.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from server.models.schemas import Card

logger = logging.getLogger(__name__)

# Directory where replay files are persisted
_REPLAYS_DIR = Path(__file__).resolve().parent.parent.parent / "replays"


class ReplayLogger:
    """Records per-hand state for a single game.

    Each hand is captured as a frame containing:
    * The game state at the start of the hand.
    * Every player action taken during the hand.
    * Community cards dealt at each phase.
    * The game state at the end of the hand.
    * The result (winners, pot distribution, hand names).

    When :meth:`save` is called, the entire log is written as a JSON file
    to ``replays/<game_id>_<timestamp>.json``.

    Usage::

        logger = ReplayLogger(game_id)
        logger.start_hand(state)
        logger.record_action(player_id, action, amount, source)
        logger.record_community(cards)
        logger.end_hand(state, result)
        filepath = logger.save()
    """

    def __init__(self, game_id: str) -> None:
        self.game_id = game_id

        # High-level metadata
        self.game_config: Optional[dict] = None
        self.players: list[dict] = []

        # Ordered list of per-hand frames
        self.hands: list[dict] = []

        # The current hand being recorded (None between hands)
        self._current_hand: Optional[dict] = None

    # ------------------------------------------------------------------
    # Hand lifecycle
    # ------------------------------------------------------------------

    def start_hand(self, state: Any) -> None:
        """Begin recording a new hand.

        Captures a snapshot of the public game state.  Private hole-card
        information is intentionally **not** stored — replays are
        public-information-only to avoid data leaks.

        Args:
            state: The current :class:`GameState` at the start of the hand.
        """
        self._current_hand = {
            "hand_number": getattr(state, "hand_number", len(self.hands) + 1),
            "phase": getattr(state, "phase", "PRE_FLOP"),
            "players": self._serialize_players(state),
            "dealer_index": getattr(state, "dealer_index", 0),
            "blinds": self._serialize_blinds(state),
            "actions": [],
            "community_cards": [],
            "start_pot": getattr(state, "pot", 0),
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_state": None,
            "result": None,
        }

        logger.debug(
            "Replay: started hand %d for game '%s'.",
            self._current_hand["hand_number"],
            self.game_id,
        )

    def record_action(
        self,
        player_id: str,
        action: str,
        amount: int = 0,
        source: str = "RULE",
    ) -> None:
        """Record a single player action in the current hand.

        Args:
            player_id: The ID of the player who acted.
            action: The action string (e.g. ``"FOLD"``, ``"RAISE"``).
            amount: The bet / call / raise amount.
            source: ``"RULE"`` or ``"LLM"`` — how the decision was made.
        """
        if self._current_hand is None:
            return

        self._current_hand["actions"].append({
            "player_id": player_id,
            "action": action,
            "amount": amount,
            "source": source,
        })

    def record_community(self, cards: list[Card]) -> None:
        """Record newly-dealt community cards for the current hand.

        Args:
            cards: A list of :class:`Card` instances.
        """
        if self._current_hand is None:
            return

        self._current_hand["community_cards"] = [
            c.to_dict() for c in cards
        ]

    def end_hand(self, state: Any, result: Optional[dict]) -> None:
        """Finalise the current hand with end state and result.

        Args:
            state: The :class:`GameState` at hand end.
            result: The ``"hand_result"`` event payload:
                ``{"winners": [...], "hands": {...}, "pot_distribution": [...]}``.
        """
        if self._current_hand is None:
            return

        self._current_hand["end_state"] = {
            "phase": getattr(state, "phase", "HAND_END"),
            "players": self._serialize_players(state),
            "pot": getattr(state, "pot", 0),
            "community_cards": [
                c.to_dict() for c in getattr(state, "community_cards", [])
            ],
        }
        self._current_hand["result"] = result
        self._current_hand["end_time"] = datetime.now(timezone.utc).isoformat()

        self.hands.append(self._current_hand)
        self._current_hand = None

        logger.debug(
            "Replay: ended hand %d for game '%s'.",
            len(self.hands),
            self.game_id,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> str:
        """Write the full replay log to disk and return the file path.

        The file is placed in ``replays/`` with a name like
        ``<game_id>_<uuid_short>.json``.

        Returns:
            Absolute path to the saved replay file.
        """
        short_id = uuid.uuid4().hex[:8]
        filename = f"{self.game_id}_{short_id}.json"
        filepath = _REPLAYS_DIR / filename

        _REPLAYS_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "replay_id": filename.replace(".json", ""),
            "game_id": self.game_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "config": self.game_config,
            "players": self.players,
            "hands": self.hands,
        }

        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

        logger.info("Replay saved: %s", filepath)
        return str(filepath.resolve())

    def set_game_info(
        self,
        config: Optional[dict] = None,
        players: Optional[list[dict]] = None,
    ) -> None:
        """Store top-level game metadata for the replay header.

        Call this once after the game is initialised so the replay file
        includes the game configuration and player roster.

        Args:
            config: Serialised game config dict.
            players: Serialised player list dicts.
        """
        if config:
            self.game_config = config
        if players:
            self.players = players

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_players(state: Any) -> list[dict]:
        """Extract public-only player info from *state*."""
        players = []
        for p in getattr(state, "players", []):
            players.append({
                "id": p.id,
                "name": p.name,
                "is_human": p.is_human,
                "chips": p.chips,
                "position": p.position.value if p.position else None,
                "is_active": p.is_active,
                "is_all_in": p.is_all_in,
            })
        return players

    @staticmethod
    def _serialize_blinds(state: Any) -> Optional[dict]:
        """Extract blinds info from *state*."""
        blinds = getattr(state, "blinds", None)
        if blinds is None:
            return None
        if hasattr(blinds, "model_dump"):
            return blinds.model_dump()
        if isinstance(blinds, dict):
            return dict(blinds)
        return {"small": getattr(blinds, "small", 0), "big": getattr(blinds, "big", 0)}

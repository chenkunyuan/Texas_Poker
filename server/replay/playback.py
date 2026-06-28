"""
Replay Playback for Texas Hold'em Poker.

Static utilities for loading replay files, listing available replays,
and computing per-player statistics from replay data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directory where replay files are persisted (shared with logger.py)
_REPLAYS_DIR = Path(__file__).resolve().parent.parent.parent / "replays"


class ReplayPlayback:
    """Static helper for reading and analysing replay files.

    All methods are ``@staticmethod`` and do not require instantiation.
    """

    @staticmethod
    def load(path: str) -> dict:
        """Load a single replay file from disk.

        Args:
            path: Absolute or relative path to a ``.json`` replay file.

        Returns:
            The parsed replay data as a dict.

        Raises:
            FileNotFoundError: If *path* does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        filepath = Path(path)
        if not filepath.is_absolute():
            filepath = _REPLAYS_DIR / filepath

        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        logger.info("Loaded replay: %s", filepath)
        return data

    @staticmethod
    def list_replays() -> list[dict]:
        """List all replay files in the ``replays/`` directory.

        Returns:
            A list of dicts with keys ``replay_id``, ``game_id``,
            ``saved_at``, ``hand_count``, and ``filepath`` (absolute string
            path).  Sorted by ``saved_at`` descending (newest first).
        """
        _REPLAYS_DIR.mkdir(parents=True, exist_ok=True)

        result: list[dict] = []

        for filepath in sorted(
            _REPLAYS_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    data = json.load(fh)

                result.append({
                    "replay_id": data.get("replay_id", filepath.stem),
                    "game_id": data.get("game_id", ""),
                    "saved_at": data.get("saved_at", ""),
                    "hand_count": len(data.get("hands", [])),
                    "filepath": str(filepath.resolve()),
                })
            except (json.JSONDecodeError, OSError):
                logger.warning("Skipping unreadable replay: %s", filepath)
                continue

        return result

    @staticmethod
    def compute_stats(replay_data: dict, player_id: str) -> dict:
        """Compute per-player statistics from replay data.

        Calculates the following poker metrics:

        * **VPIP** (Voluntarily Put money In Pot): Percentage of hands where
          the player voluntarily put money in (call, raise, or all-in pre-flop).
        * **PFR** (Pre-Flop Raise): Percentage of hands where the player
          raised or went all-in pre-flop.
        * **win_rate**: Percentage of hands won by this player.
        * **AF** (Aggression Factor): Ratio of aggressive actions (raises +
          all-ins) to passive actions (calls) post-flop.  If no passive
          actions, returns ``999.0``.
        * **hands_played**: Total number of hands the player participated in.
        * **hands_won**: Number of hands the player won.
        * **net_chips**: Net chip change (final - starting).

        Args:
            replay_data: A loaded replay dict (as returned by :meth:`load`).
            player_id: The player ID to compute stats for.

        Returns:
            A dict of computed statistics.
        """
        hands = replay_data.get("hands", [])
        players_meta = replay_data.get("players", [])

        # Safely get starting chips from player metadata
        starting_chips = 0
        for p in players_meta:
            if p.get("id") == player_id:
                starting_chips = p.get("chips", 0)
                break

        vpip_count = 0       # hands with voluntary pre-flop action
        pfr_count = 0        # hands with pre-flop raise / all-in
        hands_won = 0        # hands where player appears in winners
        hands_participated = 0  # hands the player was dealt into

        # Post-flop aggression counters
        aggressive_actions = 0   # raises + all-ins post-flop
        passive_actions = 0      # calls post-flop

        for hand in hands:
            # Check if player was in this hand
            players_in_hand = hand.get("players", [])
            player_found = any(
                p.get("id") == player_id for p in players_in_hand
            )
            if not player_found:
                continue

            hands_participated += 1

            actions = hand.get("actions", [])
            community_cards = hand.get("community_cards", [])
            is_preflop = len(community_cards) == 0

            # --- Analyse actions -------------------------------------------------
            voluntary_preflop = False
            raised_preflop = False

            for act in actions:
                if act.get("player_id") != player_id:
                    continue

                action = act.get("action", "").upper()

                if is_preflop:
                    if action in ("CALL", "RAISE", "ALL_IN"):
                        voluntary_preflop = True
                    if action in ("RAISE", "ALL_IN"):
                        raised_preflop = True
                else:
                    # Post-flop
                    if action in ("RAISE", "ALL_IN"):
                        aggressive_actions += 1
                    elif action == "CALL":
                        passive_actions += 1

                # For the current hand loop, only check pre-flop once we've
                # seen all actions (will set below)

            if voluntary_preflop:
                vpip_count += 1
            if raised_preflop:
                pfr_count += 1

            # --- Check if player won this hand ----------------------------------
            result = hand.get("result") or {}
            winners_list = result.get("winners", [])
            for w in winners_list:
                if w.get("player_id") == player_id:
                    hands_won += 1
                    break

        # --- Compute final chips ------------------------------------------------
        final_chips = starting_chips
        # Try to get final chips from the last hand's end_state
        if hands:
            last_hand = hands[-1]
            end_state = last_hand.get("end_state") or {}
            for p in end_state.get("players", []):
                if p.get("id") == player_id:
                    final_chips = p.get("chips", starting_chips)
                    break

        # --- Rate calculations --------------------------------------------------
        total_hands = len(hands)
        vpip = (vpip_count / total_hands * 100) if total_hands > 0 else 0.0
        pfr = (pfr_count / total_hands * 100) if total_hands > 0 else 0.0
        win_rate = (hands_won / total_hands * 100) if total_hands > 0 else 0.0

        if passive_actions == 0:
            af = 999.0 if aggressive_actions > 0 else 0.0
        else:
            af = aggressive_actions / passive_actions

        return {
            "vpip": round(vpip, 1),
            "pfr": round(pfr, 1),
            "win_rate": round(win_rate, 1),
            "af": round(af, 1),
            "hands_played": hands_participated,
            "hands_won": hands_won,
            "net_chips": final_chips - starting_chips,
            "starting_chips": starting_chips,
            "final_chips": final_chips,
        }

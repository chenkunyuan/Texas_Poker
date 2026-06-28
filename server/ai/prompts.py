"""
Prompt builder for Texas Hold'em Poker AI LLM decisions.

Constructs a detailed natural-language prompt describing the current game
situation so the LLM can make an informed poker decision.
"""

from __future__ import annotations

from typing import List, Optional

from server.models.schemas import (
    Card,
    GamePhase,
    PersonalityProfile,
    PlayerAction,
    Position,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_poker_prompt(
    personality: Optional[PersonalityProfile],
    hole_cards: List[Card],
    community_cards: List[Card],
    pot: int,
    current_bet: int,
    player_chips: int,
    position: Optional[Position],
    action_history: List[dict],
    variant: str = "no_limit",
    valid_actions: Optional[dict] = None,
) -> str:
    """Build a detailed prompt describing the current poker situation.

    **DATA ISOLATION**: Only the player's own hole cards are included.
    Other players' hole cards are NEVER exposed in the prompt.

    Args:
        personality: The player's personality profile (or ``None``).
        hole_cards: The player's two private cards.
        community_cards: Shared community cards (0-5).
        pot: Current pot size in chips.
        current_bet: The current bet to match.
        player_chips: How many chips the player has remaining.
        position: The player's table position.
        action_history: Public action history (actions only, no hole cards).
        variant: ``"no_limit"`` or ``"pot_limit"``.
        valid_actions: Optional dict of valid actions with min/max raise info.

    Returns:
        A prompt string ready to send to the LLM.
    """
    lines: List[str] = []

    # --- Role & personality --------------------------------------------------
    lines.append("You are a Texas Hold'em poker player")
    if personality:
        lines.append(f"with a {personality.type.value} playing style.")
        lines.append(f"- Aggression: {personality.aggression:.0%}")
        lines.append(f"- Bluff tendency: {personality.bluff_frequency:.0%}")
        lines.append(f"- Preflop hand range: top {personality.preflop_range_pct:.0f}%")
        lines.append(f"- Fold-to-3bet frequency: {personality.fold_to_3bet:.0%}")
    else:
        lines.append("with a balanced, adaptive style.")
    lines.append("")

    # --- Game context --------------------------------------------------------
    lines.append("## Game Situation")
    variant_label = "No Limit" if variant == "no_limit" else "Pot Limit"
    lines.append(f"Variant: {variant_label}")
    lines.append(f"Position: {position.value if position else 'Unknown'}")
    lines.append("")

    # --- Hole cards ----------------------------------------------------------
    if hole_cards:
        hole_str = " ".join(str(c) for c in hole_cards)
        lines.append(f"## Your Hole Cards: {hole_str}")
    else:
        lines.append("## Your Hole Cards: (none dealt yet)")
    lines.append("")

    # --- Community cards -----------------------------------------------------
    if community_cards:
        comm_str = " ".join(str(c) for c in community_cards)
        phase_label = _phase_from_community_count(len(community_cards))
        lines.append(f"## Community Cards ({phase_label}): {comm_str}")
    else:
        lines.append("## Community Cards: (none)")
    lines.append("")

    # --- Pot & betting -------------------------------------------------------
    lines.append("## Pot & Betting")
    lines.append(f"Pot: {pot} chips")
    lines.append(f"Current bet to call: {current_bet} chips")
    lines.append(f"Your remaining chips: {player_chips} chips")
    to_call = max(0, current_bet)
    if to_call > 0:
        lines.append(f"You need to add {to_call} chips to call.")
    lines.append("")

    # --- Valid actions -------------------------------------------------------
    if valid_actions:
        lines.append("## Available Actions")
        lines.extend(_format_valid_actions(valid_actions))
        lines.append("")

    # --- Action history ------------------------------------------------------
    if action_history:
        lines.append("## Action History (this hand)")
        for entry in action_history[-20:]:  # Last 20 actions max
            pid = entry.get("player_id", "?")
            act = entry.get("action", "?")
            amt = entry.get("amount", 0)
            if amt > 0:
                lines.append(f"- {pid}: {act} {amt}")
            else:
                lines.append(f"- {pid}: {act}")
        lines.append("")

    # --- Instructions --------------------------------------------------------
    lines.append("## Instructions")
    lines.append("Analyze the situation and decide your action.")
    lines.append("Consider your hole cards, the community cards, position, pot odds,")
    lines.append("your chip stack, your playing style, and the action history.")
    lines.append("")
    lines.append("Respond with a **single JSON object** in this exact format:")
    lines.append("```json")
    lines.append("{")
    lines.append('    "action": "FOLD|CHECK|CALL|RAISE|ALL_IN",')
    lines.append('    "amount": <integer, 0 for FOLD/CHECK/CALL>,')
    lines.append('    "reasoning": "<brief poker reasoning>",')
    lines.append('    "confidence": <float between 0.0 and 1.0>')
    lines.append("}")
    lines.append("```")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _phase_from_community_count(count: int) -> str:
    """Return a human-readable phase label for the number of community cards."""
    mapping = {0: "Preflop", 3: "Flop", 4: "Turn", 5: "River"}
    return mapping.get(count, f"{count} cards")


def _format_valid_actions(valid_actions: dict) -> List[str]:
    """Format valid actions into bullet points for the prompt.

    Args:
        valid_actions: Dict keyed by action name (e.g. ``"FOLD"``), each value
            a dict with at minimum ``{"action": ..., "amount": ...}`` and
            optionally ``"min"`` / ``"max"`` for raises.

    Returns:
        A list of bullet-point strings.
    """
    lines: List[str] = []
    for key, info in sorted(valid_actions.items()):
        action_name = info.get("action", key)
        if hasattr(action_name, "value"):
            action_name = action_name.value

        if action_name in ("FOLD", "CHECK"):
            lines.append(f"- {action_name}")
        elif action_name == "CALL":
            lines.append(f"- {action_name} ({info.get('amount', 0)} chips)")
        elif action_name == "RAISE":
            mn = info.get("min", 0)
            mx = info.get("max", 0)
            lines.append(f"- {action_name} (bet between {mn} and {mx} chips)")
        elif action_name == "ALL_IN":
            lines.append(f"- {action_name} ({info.get('amount', 0)} chips — all your chips)")
        else:
            lines.append(f"- {action_name}")
    return lines

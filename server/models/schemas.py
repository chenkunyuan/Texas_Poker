"""
Texas Hold'em Poker — Pydantic Data Models

Single source of truth for all data types used across the project.
Every module (engine, AI, WebSocket, replay) imports from here.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class Suit(str, Enum):
    """Card suits with Unicode display symbols."""

    HEARTS = "HEARTS"
    DIAMONDS = "DIAMONDS"
    CLUBS = "CLUBS"
    SPADES = "SPADES"

    @property
    def symbol(self) -> str:
        symbols = {
            Suit.HEARTS: "♥",   # ♥
            Suit.DIAMONDS: "♦", # ♦
            Suit.CLUBS: "♣",    # ♣
            Suit.SPADES: "♠",   # ♠
        }
        return symbols[self]


class Rank(str, Enum):
    """Card ranks. Values match the standard short notation."""

    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "T"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"

    @property
    def numeric(self) -> int:
        """Numeric value for hand comparison (2..14)."""
        order = {
            Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 4, Rank.FIVE: 5,
            Rank.SIX: 6, Rank.SEVEN: 7, Rank.EIGHT: 8, Rank.NINE: 9,
            Rank.TEN: 10, Rank.JACK: 11, Rank.QUEEN: 12, Rank.KING: 13,
            Rank.ACE: 14,
        }
        return order[self]


class Position(str, Enum):
    """Table positions in a 6-max game."""

    SB = "SB"      # Small Blind
    BB = "BB"      # Big Blind
    UTG = "UTG"    # Under the Gun
    MP = "MP"      # Middle Position
    CO = "CO"      # Cutoff
    BTN = "BTN"    # Button (Dealer)


class GamePhase(str, Enum):
    """Game state machine phases."""

    SETUP = "SETUP"
    PRE_FLOP = "PRE_FLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    SHOWDOWN = "SHOWDOWN"
    HAND_END = "HAND_END"
    GAME_OVER = "GAME_OVER"


class PlayerAction(str, Enum):
    """Actions a player can take during a betting round."""

    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    RAISE = "RAISE"
    ALL_IN = "ALL_IN"


class PersonalityType(str, Enum):
    """AI personality archetypes."""

    TAG = "TAG"                      # Tight-Aggressive
    LAG = "LAG"                      # Loose-Aggressive
    NIT = "NIT"                      # Tight-Passive
    CALLING_STATION = "CALLING_STATION"  # Loose-Passive


# =============================================================================
# Core Models
# =============================================================================


class Card(BaseModel):
    """A single playing card."""

    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        """Return human-readable representation, e.g. 'A♥'."""
        return f"{self.rank.value}{self.suit.symbol}"

    def __repr__(self) -> str:
        return f"Card(rank={self.rank.value}, suit={self.suit.value})"

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict."""
        return {"rank": self.rank.value, "suit": self.suit.value}

    class Config:
        use_enum_values = False


class PersonalityProfile(BaseModel):
    """Parameterized personality for AI agents."""

    type: PersonalityType
    name: str = ""
    preflop_range_pct: float = Field(ge=0.0, le=100.0)
    aggression: float = Field(ge=0.0, le=1.0)
    bluff_frequency: float = Field(ge=0.0, le=1.0)
    fold_to_3bet: float = Field(ge=0.0, le=1.0)


class Action(BaseModel):
    """A single action taken by a player during a betting round."""

    player_id: str
    action: PlayerAction
    amount: int = 0
    decision_source: str = "RULE"  # "RULE" or "LLM"


class Player(BaseModel):
    """Represents a player at the table (human or AI)."""

    id: str
    name: str
    is_human: bool = False
    chips: int = 0
    hole_cards: List[Card] = Field(default_factory=list)
    position: Optional[Position] = None
    is_active: bool = True
    is_all_in: bool = False
    current_bet: int = 0
    total_bet_this_round: int = 0
    personality: Optional[PersonalityProfile] = None
    has_acted_this_round: bool = False

    def reset_for_new_hand(self) -> None:
        """Reset per-hand state. Called at the start of each new hand."""
        self.hole_cards = []
        self.is_active = True
        self.is_all_in = False
        self.current_bet = 0
        self.total_bet_this_round = 0
        self.has_acted_this_round = False
        # Note: position is set externally by the dealer each hand


class BlindsConfig(BaseModel):
    """Blinds configuration for the game."""

    mode: str = "fixed"  # "fixed" or "increasing"
    small: int = 1
    big: int = 2
    increase_interval: Optional[int] = None   # hands between increases (increasing mode)
    increase_multiplier: Optional[float] = None  # multiplier per increase (increasing mode)


class GameConfig(BaseModel):
    """Full game configuration submitted before the game starts."""

    variant: str = "no_limit"          # "no_limit" or "pot_limit"
    ai_player_count: int = Field(ge=1, le=8)
    starting_chips: int = 1000
    blinds: BlindsConfig = Field(default_factory=BlindsConfig)
    personality_mode: str = "random"    # "random" or "manual"
    manual_personalities: Optional[List[PersonalityProfile]] = None
    llm_provider: str = "anthropic"     # "anthropic", "openai", or "custom"


class GameState(BaseModel):
    """Complete game state snapshot sent to clients and used by the engine."""

    phase: GamePhase = GamePhase.SETUP
    players: List[Player] = Field(default_factory=list)
    community_cards: List[Card] = Field(default_factory=list)
    pot: int = 0
    current_bet: int = 0
    dealer_index: int = 0
    action_history: List[Action] = Field(default_factory=list)
    hand_number: int = 0
    blinds: Optional[BlindsConfig] = None
    config: Optional[GameConfig] = None
    current_player_index: Optional[int] = None
    side_pots: List[dict] = Field(default_factory=list)

    def get_active_players(self) -> List[Player]:
        """Return players who have not folded and still have chips."""
        return [p for p in self.players if p.is_active and not p.is_all_in]

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """Find a player by their ID. Returns None if not found."""
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    class Config:
        arbitrary_types_allowed = True


# =============================================================================
# WebSocket Message Models
# =============================================================================


class GameStateMessage(BaseModel):
    """Server -> Client: Full game state snapshot."""

    type: str = "game_state"
    state: GameState


class YourTurnMessage(BaseModel):
    """Server -> Client: Human player's turn to act, with valid actions."""

    type: str = "your_turn"
    valid_actions: List[str] = Field(default_factory=list)
    min_raise: int = 0
    max_raise: int = 0
    call_amount: int = 0


class PlayerActionMessage(BaseModel):
    """Server -> Client: Notification that any player performed an action."""

    type: str = "player_action"
    player_id: str = ""
    player_name: str = ""
    action: str = ""
    amount: int = 0


class AIThinkingMessage(BaseModel):
    """Server -> Client: An AI player is deliberating."""

    type: str = "ai_thinking"
    player_id: str = ""
    player_name: str = ""


class HandResultMessage(BaseModel):
    """Server -> Client: Showdown results for the hand."""

    type: str = "hand_result"
    winners: List[dict] = Field(default_factory=list)
    hands: List[dict] = Field(default_factory=list)
    pot_distribution: List[dict] = Field(default_factory=list)


class GameOverMessage(BaseModel):
    """Server -> Client: Final game-over summary."""

    type: str = "game_over"
    rankings: List[dict] = Field(default_factory=list)
    stats: List[dict] = Field(default_factory=list)
    replay_id: Optional[str] = None


class ClientActionMessage(BaseModel):
    """Client -> Server: Human player submits an action."""

    type: str = "player_action"
    action: str = ""
    amount: int = 0


class ClientConfigMessage(BaseModel):
    """Client -> Server: Submit game configuration to start a new game."""

    type: str = "new_game"
    config: GameConfig

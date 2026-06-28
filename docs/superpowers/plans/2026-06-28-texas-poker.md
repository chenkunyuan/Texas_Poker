# Texas Hold'em Poker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser-based Texas Hold'em poker game with 1 human player + N AI agents using rule-engine + LLM hybrid decision making.

**Architecture:** Python FastAPI backend with modular game engine, WebSocket real-time communication, provider-agnostic LLM client, and vanilla HTML/CSS/JS frontend with classic oval table layout.

**Tech Stack:** Python 3.11+, FastAPI, websockets, httpx (LLM calls), PyYAML, Pydantic, vanilla HTML/CSS/JS

**Source spec:** `spec.md`

---

## File Structure

```
Texas_Poker/
├── server/
│   ├── main.py                 # FastAPI app entry, static file serving
│   ├── config.py               # YAML config loader
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── deck.py             # Card, Deck (shuffle, deal)
│   │   ├── dealer.py           # Dealer (positions, blinds, action order)
│   │   ├── game_controller.py  # State machine, game orchestration
│   │   ├── betting.py          # BettingRound logic
│   │   ├── pot.py              # PotCalculator (main + side pots)
│   │   └── evaluator.py        # HandEvaluator (7→5 best hand)
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── manager.py          # AI decision orchestration
│   │   ├── rule_engine.py      # Rule-based poker decisions
│   │   ├── personality.py      # Personality profile definitions
│   │   └── prompts.py          # LLM prompt templates
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py           # Abstract LLMClient + factory
│   │   ├── claude_adapter.py   # Anthropic Claude adapter
│   │   ├── openai_adapter.py   # OpenAI GPT adapter
│   │   └── custom_adapter.py   # Generic OpenAI-compatible adapter
│   ├── replay/
│   │   ├── __init__.py
│   │   ├── logger.py           # Game state recorder
│   │   └── playback.py         # Replay engine + stats
│   ├── ws/
│   │   ├── __init__.py
│   │   └── manager.py          # WebSocket connection manager
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic models for API/WS
├── frontend/
│   ├── index.html              # SPA entry point
│   ├── css/
│   │   └── style.css           # All styles (dark theme, table, cards)
│   └── js/
│       ├── app.js              # App shell, view switching
│       ├── ws.js               # WebSocket client
│       ├── setup.js            # Setup view logic
│       ├── table.js            # Game table view + rendering
│       └── results.js          # Game over / replay view
├── config/
│   ├── llm_config.yaml         # LLM provider settings
│   └── personalities.yaml      # AI personality profiles
├── replays/                    # Saved game replay JSON files
├── requirements.txt
├── spec.md
└── Requirement.md
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config/llm_config.yaml`
- Create: `config/personalities.yaml`
- Create: all `__init__.py` files
- Create: `replays/.gitkeep`

- [ ] **Step 1: Create requirements.txt**

```txt
fastapi==0.111.0
uvicorn[standard]==0.30.1
websockets==12.0
httpx==0.27.0
pyyaml==6.1
pydantic==2.7.3
```

- [ ] **Step 2: Create directory structure**

Run:
```bash
cd D:\Claude\Texas_Poker
mkdir -p server\engine server\ai server\llm server\replay server\ws server\models
mkdir -p frontend\css frontend\js
mkdir -p config replays
```

- [ ] **Step 3: Create all __init__.py files**

```bash
cd D:\Claude\Texas_Poker
for d in server server\engine server\ai server\llm server\replay server\ws server\models; do echo "" > "$d\__init__.py"; done
```

- [ ] **Step 4: Create llm_config.yaml**

```yaml
# LLM Provider Configuration
# provider: anthropic | openai | custom
provider: anthropic
model: claude-sonnet-4-6
api_key: ${ANTHROPIC_API_KEY}
max_tokens: 500
temperature: 0.7
timeout_seconds: 30

# LLM trigger thresholds
trigger:
  confidence_threshold: 0.6
  pot_to_stack_ratio: 0.3
  enable_on_allin: true
  enable_on_late_street: true

custom:
  base_url: null
  api_key_env: null
  headers: {}
```

- [ ] **Step 5: Create personalities.yaml**

```yaml
personalities:
  TAG:
    name: "Tight-Aggressive"
    description: "Selective with hands, plays them aggressively"
    preflop_range_pct: 15
    aggression: 0.8
    bluff_frequency: 0.15
    fold_to_3bet: 0.4

  LAG:
    name: "Loose-Aggressive"
    description: "Wide range, constant pressure"
    preflop_range_pct: 35
    aggression: 0.95
    bluff_frequency: 0.35
    fold_to_3bet: 0.2

  Nit:
    name: "Tight-Passive"
    description: "Only premium hands, rarely bluffs"
    preflop_range_pct: 8
    aggression: 0.2
    bluff_frequency: 0.03
    fold_to_3bet: 0.7

  CallingStation:
    name: "Loose-Passive"
    description: "Plays many hands, calls too much"
    preflop_range_pct: 50
    aggression: 0.15
    bluff_frequency: 0.05
    fold_to_3bet: 0.1

decision_timing:
  rule_delay_min_sec: 2
  rule_delay_max_sec: 5
  llm_extra_delay_sec: 0
```

- [ ] **Step 6: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding with configs and dependencies"
```

---

### Task 2: Data Models (Pydantic Schemas)

**Files:**
- Create: `server/models/schemas.py`

- [ ] **Step 1: Write schemas.py**

```python
"""Pydantic data models for Texas Hold'em poker."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Suit(str, Enum):
    HEARTS = "hearts"
    DIAMONDS = "diamonds"
    CLUBS = "clubs"
    SPADES = "spades"


class Rank(str, Enum):
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


class Card(BaseModel):
    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        symbols = {Suit.HEARTS: "♥", Suit.DIAMONDS: "♦",
                   Suit.CLUBS: "♣", Suit.SPADES: "♠"}
        return f"{self.rank.value}{symbols[self.suit]}"

    def to_dict(self) -> dict:
        return {"suit": self.suit.value, "rank": self.rank.value}


class Position(str, Enum):
    SB = "SB"
    BB = "BB"
    UTG = "UTG"
    MP = "MP"
    CO = "CO"
    BTN = "BTN"


class GamePhase(str, Enum):
    SETUP = "setup"
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    HAND_END = "hand_end"
    GAME_OVER = "game_over"


class PlayerAction(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"


class PersonalityType(str, Enum):
    TAG = "TAG"
    LAG = "LAG"
    NIT = "Nit"
    CALLING_STATION = "CallingStation"


class PersonalityProfile(BaseModel):
    type: PersonalityType
    name: str
    preflop_range_pct: float
    aggression: float
    bluff_frequency: float
    fold_to_3bet: float


class Action(BaseModel):
    player_id: str
    action: PlayerAction
    amount: int = 0
    decision_source: str = "RULE"  # "RULE" or "LLM"


class Player(BaseModel):
    id: str
    name: str
    is_human: bool = False
    chips: int = 1000
    hole_cards: list[Card] = []
    position: Optional[Position] = None
    is_active: bool = True
    is_all_in: bool = False
    current_bet: int = 0
    total_bet_this_round: int = 0
    personality: Optional[PersonalityProfile] = None
    has_acted_this_round: bool = False

    def reset_for_new_hand(self):
        self.hole_cards = []
        self.is_active = True
        self.is_all_in = False
        self.current_bet = 0
        self.total_bet_this_round = 0
        self.has_acted_this_round = False


class BlindsConfig(BaseModel):
    mode: str = "fixed"  # "fixed" | "increasing"
    small: int = 5
    big: int = 10
    increase_interval: int = 10  # hands between increases
    increase_multiplier: float = 2.0


class GameConfig(BaseModel):
    variant: str = "no_limit"  # "no_limit" | "pot_limit"
    ai_player_count: int = 5
    starting_chips: int = 1000
    blinds: BlindsConfig = BlindsConfig()
    personality_mode: str = "random"  # "random" | "manual"
    manual_personalities: dict[str, PersonalityType] = {}
    llm_provider: str = "anthropic"


class GameState(BaseModel):
    phase: GamePhase = GamePhase.SETUP
    players: list[Player] = []
    community_cards: list[Card] = []
    pot: int = 0
    current_bet: int = 0
    dealer_index: int = 0
    action_history: list[Action] = []
    hand_number: int = 0
    blinds: BlindsConfig = BlindsConfig()
    config: Optional[GameConfig] = None
    current_player_index: int = 0
    side_pots: list[dict] = []  # [{"amount": int, "eligible_players": [str]}]

    def get_active_players(self) -> list[Player]:
        return [p for p in self.players if p.is_active and not p.is_all_in]

    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None


class GameStateMessage(BaseModel):
    """WebSocket message: server -> client game state."""
    type: str = "game_state"
    state: GameState


class YourTurnMessage(BaseModel):
    """WebSocket message: prompt human player."""
    type: str = "your_turn"
    valid_actions: list[str]
    min_raise: int = 0
    max_raise: int = 0
    call_amount: int = 0


class PlayerActionMessage(BaseModel):
    """WebSocket message: action notification."""
    type: str = "player_action"
    player_id: str
    player_name: str
    action: str
    amount: int = 0


class AIThinkingMessage(BaseModel):
    """WebSocket message: AI thinking indicator."""
    type: str = "ai_thinking"
    player_id: str
    player_name: str


class HandResultMessage(BaseModel):
    """WebSocket message: showdown results."""
    type: str = "hand_result"
    winners: list[dict]  # [{"player_id": str, "hand_name": str, "amount": int}]
    hands: dict[str, str]  # player_id -> hand description
    pot_distribution: list[dict]


class GameOverMessage(BaseModel):
    """WebSocket message: final results."""
    type: str = "game_over"
    rankings: list[dict]  # [{"player_id": str, "name": str, "chips": int, "rank": int}]
    stats: dict  # player_id -> stats dict
    replay_id: str


class ClientActionMessage(BaseModel):
    """WebSocket message: client -> server action."""
    type: str = "player_action"
    action: str
    amount: int = 0


class ClientConfigMessage(BaseModel):
    """WebSocket message: client -> server game config."""
    type: str = "new_game"
    config: GameConfig
```

- [ ] **Step 2: Verify models import correctly**

Run: `cd D:\Claude\Texas_Poker && python -c "from server.models.schemas import Card, Suit, Rank; c = Card(suit=Suit.HEARTS, rank=Rank.ACE); print(c)"`
Expected: `A♥`

- [ ] **Step 3: Commit**

```bash
git add server/models/schemas.py
git commit -m "feat: add Pydantic data models for poker game"
```

---

### Task 3: Deck and Card Utilities

**Files:**
- Create: `server/engine/deck.py`

- [ ] **Step 1: Write deck.py**

```python
"""Card and Deck classes for Texas Hold'em."""

import random
from server.models.schemas import Card, Suit, Rank


RANK_ORDER: dict[Rank, int] = {
    Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 4, Rank.FIVE: 5,
    Rank.SIX: 6, Rank.SEVEN: 7, Rank.EIGHT: 8, Rank.NINE: 9,
    Rank.TEN: 10, Rank.JACK: 11, Rank.QUEEN: 12, Rank.KING: 13, Rank.ACE: 14,
}


class Deck:
    """Standard 52-card deck with Fisher-Yates shuffle."""

    def __init__(self):
        self.cards: list[Card] = []
        self._build()

    def _build(self):
        self.cards = [Card(suit=s, rank=r) for s in Suit for r in Rank]
        self.cards = []  # placeholder — will be populated below
        # Actually build properly:
        self.cards = [
            Card(suit=suit, rank=rank)
            for suit in Suit
            for rank in Rank
        ]

    def shuffle(self):
        """Fisher-Yates shuffle."""
        for i in range(len(self.cards) - 1, 0, -1):
            j = random.randint(0, i)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]

    def deal(self, count: int = 1) -> list[Card]:
        """Deal `count` cards from top of deck."""
        if count > len(self.cards):
            raise ValueError(f"Not enough cards: {len(self.cards)} < {count}")
        dealt = self.cards[:count]
        self.cards = self.cards[count:]
        return dealt

    def burn(self):
        """Burn one card (discard from top)."""
        self.deal(1)

    def reset(self):
        """Rebuild and reshuffle deck."""
        self._build()
        self.shuffle()

    def __len__(self) -> int:
        return len(self.cards)
```

- [ ] **Step 2: Verify deck works**

Run:
```bash
cd D:\Claude\Texas_Poker && python -c "
from server.engine.deck import Deck
d = Deck()
print(f'Deck size: {len(d)}')
d.shuffle()
cards = d.deal(5)
print(f'Dealt: {[str(c) for c in cards]}')
print(f'Remaining: {len(d)}')
"
```
Expected: Deck size: 52, Dealt: 5 cards, Remaining: 47

- [ ] **Step 3: Commit**

```bash
git add server/engine/deck.py
git commit -m "feat: add Deck class with Fisher-Yates shuffle"
```

---

### Task 4: Hand Evaluator

**Files:**
- Create: `server/engine/evaluator.py`

- [ ] **Step 1: Write evaluator.py**

```python
"""Texas Hold'em hand evaluator — best 5-card hand from 7 cards."""

from itertools import combinations
from server.models.schemas import Card, Rank
from server.engine.deck import RANK_ORDER


HAND_RANKS = {
    "high_card": 0, "one_pair": 1, "two_pair": 2, "three_of_a_kind": 3,
    "straight": 4, "flush": 5, "full_house": 6, "four_of_a_kind": 7,
    "straight_flush": 8, "royal_flush": 9,
}


def _get_rank_val(card: Card) -> int:
    return RANK_ORDER[card.rank]


def _evaluate_5_cards(cards: list[Card]) -> tuple[int, list[int]]:
    """Evaluate exactly 5 cards. Returns (hand_rank, kickers)."""
    ranks = sorted([_get_rank_val(c) for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    is_flush = len(set(suits)) == 1
    is_straight = False
    straight_high = 0

    # Check straight
    if len(set(ranks)) == 5:
        if ranks[0] - ranks[4] == 4:
            is_straight = True
            straight_high = ranks[0]
        # Ace-low straight (A-2-3-4-5)
        elif ranks == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5

    # Count rank frequencies
    rank_counts: dict[int, int] = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)

    if is_flush and is_straight:
        if straight_high == 14:
            return (HAND_RANKS["royal_flush"], [14])
        return (HAND_RANKS["straight_flush"], [straight_high])

    if counts == [4, 1]:
        quads = [r for r, c in rank_counts.items() if c == 4][0]
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (HAND_RANKS["four_of_a_kind"], [quads, kicker])

    if counts == [3, 2]:
        trips = [r for r, c in rank_counts.items() if c == 3][0]
        pair = [r for r, c in rank_counts.items() if c == 2][0]
        return (HAND_RANKS["full_house"], [trips, pair])

    if is_flush:
        return (HAND_RANKS["flush"], ranks)

    if is_straight:
        return (HAND_RANKS["straight"], [straight_high])

    if counts == [3, 1, 1]:
        trips = [r for r, c in rank_counts.items() if c == 3][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (HAND_RANKS["three_of_a_kind"], [trips] + kickers)

    if counts == [2, 2, 1]:
        pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (HAND_RANKS["two_pair"], pairs + [kicker])

    if counts == [2, 1, 1, 1]:
        pair = [r for r, c in rank_counts.items() if c == 2][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (HAND_RANKS["one_pair"], [pair] + kickers)

    return (HAND_RANKS["high_card"], ranks)


def evaluate_hand(hole_cards: list[Card], community_cards: list[Card]) -> tuple[int, list[int], str]:
    """
    Evaluate the best 5-card hand from 2 hole + 5 community cards.
    Returns (hand_rank_value, kickers, hand_name).
    """
    all_cards = hole_cards + community_cards
    best_rank = -1
    best_kickers: list[int] = []
    best_hand_name = ""

    for combo in combinations(all_cards, 5):
        rank_val, kickers = _evaluate_5_cards(list(combo))
        if rank_val > best_rank or (rank_val == best_rank and kickers > best_kickers):
            best_rank = rank_val
            best_kickers = kickers
            for name, val in HAND_RANKS.items():
                if val == rank_val:
                    best_hand_name = name
                    break

    return best_rank, best_kickers, best_hand_name


def compare_hands(
    hole1: list[Card], hole2: list[Card], community: list[Card]
) -> int:
    """
    Compare two hands. Returns 1 if hand1 wins, -1 if hand2 wins, 0 if tie.
    """
    r1, k1, _ = evaluate_hand(hole1, community)
    r2, k2, _ = evaluate_hand(hole2, community)
    if r1 > r2:
        return 1
    if r2 > r1:
        return -1
    # Compare kickers
    for a, b in zip(k1, k2):
        if a > b:
            return 1
        if b > a:
            return -1
    return 0
```

- [ ] **Step 2: Verify evaluator**

Run:
```bash
cd D:\Claude\Texas_Poker && python -c "
from server.engine.deck import Deck
from server.engine.evaluator import evaluate_hand, compare_hands
from server.models.schemas import Card, Suit, Rank

# Test: pair of aces vs pair of kings
hole1 = [Card(suit=Suit.HEARTS, rank=Rank.ACE), Card(suit=Suit.DIAMONDS, rank=Rank.ACE)]
hole2 = [Card(suit=Suit.HEARTS, rank=Rank.KING), Card(suit=Suit.DIAMONDS, rank=Rank.KING)]
community = [Card(suit=Suit.CLUBS, rank=Rank.TWO), Card(suit=Suit.SPADES, rank=Rank.FIVE),
             Card(suit=Suit.HEARTS, rank=Rank.NINE), Card(suit=Suit.DIAMONDS, rank=Rank.THREE),
             Card(suit=Suit.CLUBS, rank=Rank.JACK)]

r1, k1, n1 = evaluate_hand(hole1, community)
r2, k2, n2 = evaluate_hand(hole2, community)
print(f'Hand1: {n1} rank={r1} kickers={k1}')
print(f'Hand2: {n2} rank={r2} kickers={k2}')
print(f'Compare: {compare_hands(hole1, hole2, community)} (expect 1)')
"
```
Expected: Hand1 wins (1)

- [ ] **Step 3: Commit**

```bash
git add server/engine/evaluator.py
git commit -m "feat: add 7-card hand evaluator with ranking"
```

---

### Task 5: Betting and Pot Logic

**Files:**
- Create: `server/engine/betting.py`
- Create: `server/engine/pot.py`

- [ ] **Step 1: Write betting.py**

```python
"""Betting round logic for Texas Hold'em."""

from server.models.schemas import GameState, PlayerAction, Player


class BettingRound:
    """Manages a single betting round (pre-flop, flop, turn, river)."""

    def __init__(self, state: GameState, variant: str = "no_limit"):
        self.state = state
        self.variant = variant
        self._round_complete = False

    def get_valid_actions(self, player: Player) -> dict:
        """Return dict of valid actions for a player."""
        actions: dict[str, dict] = {}

        call_amount = self.state.current_bet - player.current_bet

        # Fold is always valid if there's a bet to call
        if call_amount > 0:
            actions["fold"] = {"valid": True}

        # Check is valid if no bet to call
        if call_amount == 0:
            actions["check"] = {"valid": True}

        # Call is valid if there's a bet to call and player has chips
        if call_amount > 0 and player.chips > 0:
            actual_call = min(call_amount, player.chips)
            actions["call"] = {"valid": True, "amount": actual_call}

        # Bet/Raise
        if player.chips > call_amount:
            min_raise = self._get_min_raise()
            max_raise = self._get_max_raise(player)
            if max_raise > min_raise or max_raise == min_raise > 0:
                actions["raise"] = {
                    "valid": True,
                    "min": min(call_amount + min_raise, player.chips),
                    "max": max_raise,
                }

        # All-in
        if player.chips > 0:
            actions["all_in"] = {"valid": True, "amount": player.chips}

        return actions

    def apply_action(self, player: Player, action: PlayerAction, amount: int = 0) -> None:
        """Apply a player's action to the game state."""
        call_amount = self.state.current_bet - player.current_bet

        if action == PlayerAction.FOLD:
            player.is_active = False

        elif action == PlayerAction.CHECK:
            pass  # Nothing changes

        elif action == PlayerAction.CALL:
            actual_call = min(call_amount, player.chips)
            player.chips -= actual_call
            player.current_bet += actual_call
            player.total_bet_this_round += actual_call
            self.state.pot += actual_call
            if player.chips == 0:
                player.is_all_in = True

        elif action == PlayerAction.RAISE:
            # Total amount the player needs to put in this action (including their current bet)
            total_bet = call_amount + amount
            actual = min(total_bet, player.chips)
            player.chips -= actual
            player.current_bet += actual
            player.total_bet_this_round += actual
            self.state.pot += actual
            self.state.current_bet = player.current_bet
            if player.chips == 0:
                player.is_all_in = True
            # Reset has_acted for other players since there's a raise
            for p in self.state.players:
                if p.id != player.id and p.is_active and not p.is_all_in:
                    p.has_acted_this_round = False

        elif action == PlayerAction.ALL_IN:
            all_in_amount = player.chips
            player.chips -= all_in_amount
            player.current_bet += all_in_amount
            player.total_bet_this_round += all_in_amount
            self.state.pot += all_in_amount
            player.is_all_in = True
            # If all-in amount exceeds current bet, it's a raise
            if player.current_bet > self.state.current_bet:
                self.state.current_bet = player.current_bet
                for p in self.state.players:
                    if p.id != player.id and p.is_active and not p.is_all_in:
                        p.has_acted_this_round = False

        player.has_acted_this_round = True

    def is_round_complete(self) -> bool:
        """Check if the betting round is complete."""
        active_players = [p for p in self.state.players if p.is_active and not p.is_all_in]

        # If 0 or 1 active players left, round is over
        if len(active_players) <= 1:
            return True

        # Check if all active players have acted and bets are equalized
        all_acted = all(p.has_acted_this_round for p in active_players)
        bets_equal = all(p.current_bet == self.state.current_bet for p in active_players)

        return all_acted and bets_equal

    def _get_min_raise(self) -> int:
        """Get the minimum raise amount."""
        if self.state.current_bet == 0:
            return self.state.blinds.big
        # Min raise is at least the last raise size, or the big blind
        return max(self.state.blinds.big, self.state.current_bet)

    def _get_max_raise(self, player: Player) -> int:
        """Get maximum raise amount based on variant rules."""
        if self.variant == "no_limit":
            return player.chips
        elif self.variant == "pot_limit":
            # Pot-sized raise: call the current bet, then raise the size of the pot
            call_amount = self.state.current_bet - player.current_bet
            pot_after_call = self.state.pot + call_amount
            return call_amount + min(pot_after_call, player.chips - call_amount)
        return player.chips
```

- [ ] **Step 2: Write pot.py**

```python
"""Pot and side-pot calculator for Texas Hold'em."""

from server.models.schemas import GameState, Player


class PotCalculator:
    """Calculates main pot and side pots."""

    @staticmethod
    def calculate_side_pots(players: list[Player]) -> list[dict]:
        """
        Calculate main and side pots from player all-in amounts.
        Returns list of {"amount": int, "eligible_players": [player_id]}.
        """
        active_players = [p for p in players if p.is_active]
        if not active_players:
            return []

        # Sort by total bet this round (ascending)
        sorted_players = sorted(active_players, key=lambda p: p.total_bet_this_round)
        pots = []
        prev_amount = 0
        remaining_players = [p for p in active_players]

        for i, player in enumerate(sorted_players):
            contribution = player.total_bet_this_round - prev_amount
            if contribution > 0:
                pot_amount = contribution * len(remaining_players)
                pots.append({
                    "amount": pot_amount,
                    "eligible_players": [p.id for p in remaining_players],
                })
                prev_amount = player.total_bet_this_round
            remaining_players = [p for p in remaining_players if p.id != player.id]
            if not remaining_players:
                break

        return pots

    @staticmethod
    def distribute_pots(
        pots: list[dict],
        players: list[Player],
        community_cards: list,
        evaluator_func,
    ) -> list[dict]:
        """
        Distribute pots to winners. Returns list of {player_id, amount, hand_name}.
        Evaluates players in reverse order (side pots resolved first).
        """
        from server.engine.evaluator import compare_hands

        distributions = []

        for pot in pots:
            eligible = [p for p in players if p.id in pot["eligible_players"]]
            if not eligible:
                continue

            # Find winner(s) among eligible players
            winners = [eligible[0]]
            for player in eligible[1:]:
                result = compare_hands(
                    winners[0].hole_cards if hasattr(winners[0], 'hole_cards') else [],
                    player.hole_cards if hasattr(player, 'hole_cards') else [],
                    community_cards,
                )
                if result < 0:
                    winners = [player]
                elif result == 0:
                    winners.append(player)

            # Split pot among winners
            split_amount = pot["amount"] // len(winners)
            remainder = pot["amount"] % len(winners)

            for i, winner in enumerate(winners):
                extra = 1 if i < remainder else 0
                distributions.append({
                    "player_id": winner.id,
                    "amount": split_amount + extra,
                    "hand_name": "TBD",  # will be filled by caller
                })

        return distributions
```

- [ ] **Step 3: Verify betting and pot**

Run:
```bash
cd D:\Claude\Texas_Poker && python -c "
from server.models.schemas import GameState, Player, PlayerAction, BlindsConfig, GamePhase
from server.engine.betting import BettingRound
from server.engine.pot import PotCalculator

# Create a simple game state
state = GameState(
    phase=GamePhase.PRE_FLOP,
    players=[
        Player(id='p1', name='P1', chips=1000, is_active=True),
        Player(id='p2', name='P2', chips=1000, is_active=True),
    ],
    pot=15,
    current_bet=10,
    blinds=BlindsConfig(small=5, big=10),
)
state.players[0].current_bet = 5
state.players[1].current_bet = 10

br = BettingRound(state, 'no_limit')
actions = br.get_valid_actions(state.players[0])
print(f'Valid actions for P1: {list(actions.keys())}')
# P1 should be able to call (5 more), raise, fold, all-in
assert 'call' in actions
assert 'raise' in actions
print('Betting tests passed!')

# Test side pots
p1 = Player(id='p1', name='P1', chips=0, is_active=True, total_bet_this_round=200, is_all_in=True)
p2 = Player(id='p2', name='P2', chips=500, is_active=True, total_bet_this_round=500)
p3 = Player(id='p3', name='P3', chips=300, is_active=True, total_bet_this_round=500)
pots = PotCalculator.calculate_side_pots([p1, p2, p3])
print(f'Side pots: {pots}')
print('Pot tests passed!')
"
```

- [ ] **Step 4: Commit**

```bash
git add server/engine/betting.py server/engine/pot.py
git commit -m "feat: add betting round logic and pot calculator"
```

---

### Task 6: Dealer (Position Management & Blinds)

**Files:**
- Create: `server/engine/dealer.py`

- [ ] **Step 1: Write dealer.py**

```python
"""Dealer — manages button position, blinds, and player positions."""

from server.models.schemas import GameState, Player, Position
from server.engine.deck import Deck


class Dealer:
    """Handles table logistics: button rotation, blind posting, position assignment."""

    POSITION_ORDER = [Position.SB, Position.BB, Position.UTG, Position.MP, Position.CO, Position.BTN]

    def __init__(self, state: GameState):
        self.state = state
        self.deck = Deck()

    def start_new_hand(self):
        """Prepare for a new hand: reset deck, rotate button, assign positions, post blinds."""
        # Reset all players for new hand
        for player in self.state.players:
            player.reset_for_new_hand()

        # Remove busted players
        self.state.players = [p for p in self.state.players if p.chips > 0]

        # Rotate dealer button (clockwise)
        if self.state.hand_number > 0:
            self.state.dealer_index = (self.state.dealer_index + 1) % len(self.state.players)

        self.state.hand_number += 1
        self.state.community_cards = []
        self.state.pot = 0
        self.state.current_bet = 0
        self.state.action_history = []
        self.state.side_pots = []

        # Assign positions
        self._assign_positions()

        # Check/increase blinds
        self._update_blinds()

        # Post blinds
        self._post_blinds()

        # Shuffle and deal
        self.deck.reset()
        self._deal_hole_cards()

    def _assign_positions(self):
        """Assign positions based on dealer button."""
        n = len(self.state.players)
        for i, player in enumerate(self.state.players):
            offset = (i - self.state.dealer_index) % n
            if n <= 2:
                # Heads-up: dealer is SB, other is BB
                positions_h2 = [Position.SB, Position.BB]
                player.position = positions_h2[offset] if offset < 2 else None
            else:
                player.position = self.POSITION_ORDER[offset] if offset < len(self.POSITION_ORDER) else None

    def _update_blinds(self):
        """Increase blinds if in increasing mode."""
        blinds = self.state.blinds
        if blinds.mode == "increasing" and blinds.increase_interval > 0:
            if self.state.hand_number > 1 and self.state.hand_number % blinds.increase_interval == 0:
                blinds.small = int(blinds.small * blinds.increase_multiplier)
                blinds.big = int(blinds.big * blinds.increase_multiplier)

    def _post_blinds(self):
        """Post small and big blinds."""
        sb_player = self._get_player_by_position(Position.SB)
        bb_player = self._get_player_by_position(Position.BB)

        if sb_player:
            sb_amount = min(self.state.blinds.small, sb_player.chips)
            sb_player.chips -= sb_amount
            sb_player.current_bet = sb_amount
            sb_player.total_bet_this_round = sb_amount
            self.state.pot += sb_amount

        if bb_player:
            bb_amount = min(self.state.blinds.big, bb_player.chips)
            bb_player.chips -= bb_amount
            bb_player.current_bet = bb_amount
            bb_player.total_bet_this_round = bb_amount
            self.state.pot += bb_amount
            self.state.current_bet = bb_amount

    def _deal_hole_cards(self):
        """Deal 2 hole cards to each active player."""
        for player in self.state.players:
            player.hole_cards = self.deck.deal(2)

    def deal_community(self, count: int):
        """Deal community cards: burn one, then deal `count`."""
        self.deck.burn()
        new_cards = self.deck.deal(count)
        self.state.community_cards.extend(new_cards)

    def get_action_order(self) -> list[Player]:
        """
        Get the order in which players should act.
        Pre-flop: starts after BB (UTG acts first). Otherwise: starts after dealer.
        """
        active = [p for p in self.state.players if p.is_active and not p.is_all_in]
        if not active:
            return []

        n = len(self.state.players)
        if self.state.community_cards == []:
            # Pre-flop: start after BB
            bb_idx = next((i for i, p in enumerate(self.state.players)
                           if p.position == Position.BB), self.state.dealer_index)
            start_idx = (bb_idx + 1) % n
        else:
            # Post-flop: start after dealer
            start_idx = (self.state.dealer_index + 1) % n

        # Reorder active players starting from start_idx
        ordered = []
        for i in range(n):
            idx = (start_idx + i) % n
            player = self.state.players[idx]
            if player in active:
                ordered.append(player)

        return ordered

    def _get_player_by_position(self, position: Position) -> Player | None:
        for p in self.state.players:
            if p.position == position:
                return p
        return None
```

- [ ] **Step 2: Verify dealer**

Run:
```bash
cd D:\Claude\Texas_Poker && python -c "
from server.models.schemas import GameState, Player, BlindsConfig, GamePhase
from server.engine.dealer import Dealer

state = GameState(
    players=[
        Player(id='p1', name='You', is_human=True, chips=1000),
        Player(id='p2', name='AI1', chips=1000),
        Player(id='p3', name='AI2', chips=1000),
        Player(id='p4', name='AI3', chips=1000),
        Player(id='p5', name='AI4', chips=1000),
        Player(id='p6', name='AI5', chips=1000),
    ],
    blinds=BlindsConfig(small=5, big=10),
)
dealer = Dealer(state)
dealer.start_new_hand()
print(f'Hand: {state.hand_number}, Pot: {state.pot}, Dealer: {state.dealer_index}')
for p in state.players:
    print(f'  {p.name}: pos={p.position}, chips={p.chips}, cards={[str(c) for c in p.hole_cards]}')
order = dealer.get_action_order()
print(f'Action order: {[p.name for p in order]}')
"
```

- [ ] **Step 3: Commit**

```bash
git add server/engine/dealer.py
git commit -m "feat: add Dealer with position rotation and blind posting"
```

---

### Task 7: Game Controller (State Machine)

**Files:**
- Create: `server/engine/game_controller.py`

- [ ] **Step 1: Write game_controller.py**

```python
"""Game Controller — orchestrates the full game lifecycle."""

import asyncio
import random
from server.models.schemas import (
    GameState, GamePhase, GameConfig, Player, BlindsConfig,
    PlayerAction, Position, PersonalityType,
)
from server.engine.dealer import Dealer
from server.engine.betting import BettingRound
from server.engine.pot import PotCalculator
from server.engine.evaluator import evaluate_hand, HAND_RANKS


class GameController:
    """Top-level orchestrator for a Texas Hold'em game."""

    def __init__(self, config: GameConfig, game_id: str):
        self.game_id = game_id
        self.config = config
        self.state = GameState(config=config)
        self.dealer = Dealer(self.state)
        self._action_queue: asyncio.Queue = asyncio.Queue()
        self._human_action_event: asyncio.Event = asyncio.Event()
        self._human_action: dict | None = None
        self.callbacks: dict[str, callable] = {}

    def on(self, event: str, callback: callable):
        """Register an event callback."""
        self.callbacks[event] = callback

    async def _emit(self, event: str, data=None):
        """Emit an event to registered callbacks."""
        if event in self.callbacks:
            await self.callbacks[event](data)

    def init_players(self, personalities: dict[str, PersonalityType] | None = None):
        """Create players based on game config."""
        self.state.players = []

        # Human player
        self.state.players.append(Player(
            id="human",
            name="You",
            is_human=True,
            chips=self.config.starting_chips,
        ))

        # AI players
        for i in range(self.config.ai_player_count):
            pid = f"ai_{i+1}"
            self.state.players.append(Player(
                id=pid,
                name=f"AI-{i+1}",
                is_human=False,
                chips=self.config.starting_chips,
            ))

        # Assign personalities
        import yaml
        with open("config/personalities.yaml") as f:
            profiles = yaml.safe_load(f)["personalities"]

        personality_keys = list(profiles.keys())
        for i, player in enumerate(self.state.players):
            if not player.is_human:
                if self.config.personality_mode == "random":
                    ptype = random.choice(personality_keys)
                else:
                    ptype = self.config.manual_personalities.get(
                        player.id, random.choice(personality_keys)
                    )
                pdata = profiles[ptype]
                player.personality = {
                    "type": PersonalityType(ptype),
                    "name": pdata["name"],
                    "preflop_range_pct": pdata["preflop_range_pct"],
                    "aggression": pdata["aggression"],
                    "bluff_frequency": pdata["bluff_frequency"],
                    "fold_to_3bet": pdata["fold_to_3bet"],
                }

        self.state.blinds = self.config.blinds

    async def run(self):
        """Main game loop."""
        self.state.phase = GamePhase.SETUP
        await self._emit("game_started", self.state)

        while self.state.phase != GamePhase.GAME_OVER:
            await self._play_hand()

        await self._emit("game_over", self.state)

    async def _play_hand(self):
        """Play a single hand of poker."""
        self.dealer.start_new_hand()

        # Pre-flop
        self.state.phase = GamePhase.PRE_FLOP
        await self._run_betting_round()
        if self._is_hand_over_early():
            await self._showdown()
            return

        # Flop
        self.dealer.deal_community(3)
        self.state.phase = GamePhase.FLOP
        await self._emit("community_updated", self.state)
        await self._run_betting_round()
        if self._is_hand_over_early():
            await self._showdown()
            return

        # Turn
        self.dealer.deal_community(1)
        self.state.phase = GamePhase.TURN
        await self._emit("community_updated", self.state)
        await self._run_betting_round()
        if self._is_hand_over_early():
            await self._showdown()
            return

        # River
        self.dealer.deal_community(1)
        self.state.phase = GamePhase.RIVER
        await self._emit("community_updated", self.state)
        await self._run_betting_round()

        await self._showdown()

    async def _run_betting_round(self):
        """Execute one complete betting round."""
        betting = BettingRound(self.state, self.config.variant)

        # Reset acted flags at start of round
        for p in self.state.players:
            p.has_acted_this_round = False

        while not betting.is_round_complete():
            action_order = self.dealer.get_action_order()
            if not action_order:
                break

            for player in action_order:
                if betting.is_round_complete():
                    break
                if not player.is_active or player.is_all_in:
                    continue

                # Set current player
                self.state.current_player_index = self.state.players.index(player)

                if player.is_human:
                    action, amount = await self._get_human_action(betting, player)
                else:
                    await self._emit("ai_thinking", {"player_id": player.id, "player_name": player.name})
                    action, amount = await self._get_ai_action(player)
                    await self._emit("ai_action", {"player_id": player.id, "player_name": player.name, "action": action.value, "amount": amount})

                betting.apply_action(player, action, amount)
                action_record = {"player_id": player.id, "action": action.value, "amount": amount}
                self.state.action_history.append(action_record)
                await self._emit("player_action", action_record)
                await self._emit("game_state", self.state)

                # Small delay between actions
                await asyncio.sleep(0.5)

    async def _get_human_action(self, betting: BettingRound, player: Player) -> tuple[PlayerAction, int]:
        """Wait for human player to submit an action via WebSocket."""
        valid_actions = betting.get_valid_actions(player)
        await self._emit("your_turn", {
            "valid_actions": valid_actions,
            "call_amount": self.state.current_bet - player.current_bet,
        })

        # Wait for action from WebSocket
        self._human_action_event.clear()
        await self._human_action_event.wait()

        action = PlayerAction(self._human_action["action"])
        amount = self._human_action.get("amount", 0)
        return action, amount

    def submit_human_action(self, action: str, amount: int = 0):
        """Called by WebSocket handler when human player acts."""
        self._human_action = {"action": action, "amount": amount}
        self._human_action_event.set()

    async def _get_ai_action(self, player: Player) -> tuple[PlayerAction, int]:
        """Get AI action. Will be replaced by AI Manager integration."""
        # Placeholder: simple random action
        # This will be replaced in Task 9 with actual AI decision making
        import random
        actions = [PlayerAction.FOLD, PlayerAction.CHECK, PlayerAction.CALL, PlayerAction.RAISE]
        action = random.choice(actions)
        amount = 0
        if action == PlayerAction.RAISE:
            amount = min(self.state.blinds.big * 2, player.chips)
        if action == PlayerAction.CALL:
            amount = min(self.state.current_bet - player.current_bet, player.chips)
        return action, amount

    def _is_hand_over_early(self) -> bool:
        """Check if hand is over (everyone folded except one)."""
        active = [p for p in self.state.players if p.is_active]
        return len(active) == 1

    async def _showdown(self):
        """Handle showdown and pot distribution."""
        from server.engine.evaluator import evaluate_hand, compare_hands

        self.state.phase = GamePhase.SHOWDOWN

        # Calculate side pots
        pots = PotCalculator.calculate_side_pots(self.state.players)
        distributions = PotCalculator.distribute_pots(
            pots, self.state.players, self.state.community_cards, None
        )

        # Fill in hand names for winners
        for dist in distributions:
            winner = self.state.get_player_by_id(dist["player_id"])
            if winner and winner.hole_cards:
                _, _, hand_name = evaluate_hand(winner.hole_cards, self.state.community_cards)
                dist["hand_name"] = hand_name
                winner.chips += dist["amount"]

        # Build hand result
        hands = {}
        for p in self.state.players:
            if p.hole_cards and p.is_active:
                _, _, name = evaluate_hand(p.hole_cards, self.state.community_cards)
                hands[p.id] = name

        await self._emit("hand_result", {
            "winners": distributions,
            "hands": hands,
            "pot_distribution": distributions,
        })

        self.state.phase = GamePhase.HAND_END

        # Check game end condition
        for p in self.state.players:
            if p.chips <= 0:
                self.state.phase = GamePhase.GAME_OVER
                # Build rankings
                ranked = sorted(self.state.players, key=lambda x: x.chips, reverse=True)
                rankings = [{"player_id": r.id, "name": r.name, "chips": r.chips, "rank": i+1}
                            for i, r in enumerate(ranked)]
                await self._emit("game_over", {"rankings": rankings})
                return

        # Short pause between hands
        await asyncio.sleep(1)
```

- [ ] **Step 2: Verify controller**

Run:
```bash
cd D:\Claude\Texas_Poker && python -c "
from server.models.schemas import GameConfig, BlindsConfig
from server.engine.game_controller import GameController

config = GameConfig(
    variant='no_limit',
    ai_player_count=2,
    starting_chips=1000,
    blinds=BlindsConfig(small=5, big=10),
)
gc = GameController(config, 'test-1')
gc.init_players()
print(f'Players: {[(p.name, p.chips) for p in gc.state.players]}')
print('GameController created successfully')
"
```

- [ ] **Step 3: Commit**

```bash
git add server/engine/game_controller.py
git commit -m "feat: add GameController with full state machine"
```

---

### Task 8: AI Rule Engine

**Files:**
- Create: `server/ai/rule_engine.py`

- [ ] **Step 1: Write rule_engine.py**

```python
"""Rule-based poker decision engine."""

import random
from server.models.schemas import GameState, Player, PlayerAction, Card
from server.engine.evaluator import evaluate_hand, RANK_ORDER, HAND_RANKS


class RuleEngine:
    """Makes poker decisions based on hand strength, pot odds, and personality."""

    def __init__(self, personality: dict):
        self.personality = personality
        self.aggression = personality.get("aggression", 0.5)
        self.bluff_freq = personality.get("bluff_frequency", 0.1)
        self.range_pct = personality.get("preflop_range_pct", 25)
        self.fold_to_3bet = personality.get("fold_to_3bet", 0.4)

        # Pre-flop hand rankings (simplified Sklansky groups)
        # Higher score = better starting hand
        self._premium_pairs = {"A", "K", "Q", "J"}
        self._playable_pairs = {"T", "9", "8", "7"}

    def decide(self, state: GameState, player: Player) -> tuple[PlayerAction, int, float]:
        """
        Make a decision. Returns (action, amount, confidence).
        Confidence: 0.0 (totally uncertain) to 1.0 (totally certain).
        """
        if not state.community_cards:
            return self._preflop_decision(state, player)
        else:
            return self._postflop_decision(state, player)

    def _preflop_decision(self, state: GameState, player: Player) -> tuple[PlayerAction, int, float]:
        """Pre-flop decision based on hand strength and position."""
        hand_strength = self._evaluate_preflop_hand(player.hole_cards)

        call_amount = state.current_bet - player.current_bet
        pot_odds = call_amount / (state.pot + call_amount) if call_amount > 0 else 0

        # Determine if we should play this hand
        should_play = hand_strength >= (1.0 - self.range_pct / 100.0)

        # Check for premium hands (always play)
        ranks = sorted([RANK_ORDER[c.rank] for c in player.hole_cards], reverse=True)
        is_pair = ranks[0] == ranks[1]
        is_premium = is_pair and ranks[0] >= 12  # QQ+

        if call_amount == 0:
            # No bet to face — check or raise
            if is_premium or (should_play and random.random() < self.aggression):
                raise_amount = self._calculate_raise(state, player, hand_strength)
                return PlayerAction.RAISE, raise_amount, 0.8
            else:
                return PlayerAction.CHECK, 0, 0.7 if should_play else 0.3

        # Facing a bet
        if is_premium:
            # Re-raise with premium hands
            if random.random() < self.aggression * 1.5:
                raise_amount = max(call_amount * 3, state.blinds.big * 3)
                raise_amount = min(raise_amount, player.chips)
                return PlayerAction.RAISE, raise_amount, 0.9
            return PlayerAction.CALL, call_amount, 0.85

        if should_play:
            if random.random() < self.aggression * 0.5:
                raise_amount = max(call_amount * 2, state.blinds.big * 2)
                raise_amount = min(raise_amount, player.chips)
                return PlayerAction.RAISE, raise_amount, 0.6
            return PlayerAction.CALL, call_amount, 0.55

        # Marginal hand — sometimes bluff, usually fold
        if random.random() < self.bluff_freq and call_amount <= player.chips * 0.1:
            raise_amount = max(call_amount * 3, state.blinds.big * 3)
            raise_amount = min(raise_amount, player.chips)
            return PlayerAction.RAISE, raise_amount, 0.4

        return PlayerAction.FOLD, 0, 0.8

    def _postflop_decision(self, state: GameState, player: Player) -> tuple[PlayerAction, int, float]:
        """Post-flop decision based on hand strength evaluation."""
        hand_rank, kickers, hand_name = evaluate_hand(player.hole_cards, state.community_cards)

        # Normalize hand strength (0.0 to 1.0)
        max_rank = HAND_RANKS["royal_flush"]
        strength = hand_rank / max_rank if max_rank > 0 else 0

        # Adjust for kicker strength
        kicker_bonus = sum(k * (0.01 ** i) for i, k in enumerate(kickers[:3])) / 100
        strength = min(1.0, strength + kicker_bonus * 0.1)

        call_amount = state.current_bet - player.current_bet
        pot_odds = call_amount / (state.pot + call_amount) if call_amount > 0 else 0

        # Decision logic
        if call_amount == 0:
            # Can check
            if strength > 0.6 and random.random() < self.aggression:
                raise_amount = self._calculate_raise(state, player, strength)
                return PlayerAction.RAISE, raise_amount, 0.75
            elif strength > 0.3 and random.random() < self.aggression * 0.5:
                raise_amount = self._calculate_raise(state, player, strength)
                return PlayerAction.RAISE, raise_amount, 0.5
            return PlayerAction.CHECK, 0, 0.6

        # Facing a bet
        # Strong hand: raise or call
        if strength > 0.7:
            if random.random() < self.aggression:
                raise_amount = self._calculate_raise(state, player, strength)
                return PlayerAction.RAISE, raise_amount, 0.85
            return PlayerAction.CALL, min(call_amount, player.chips), 0.8

        # Medium hand: call if pot odds justify
        if strength > 0.4:
            if strength > pot_odds * 2:
                if random.random() < self.aggression * 0.3:
                    raise_amount = self._calculate_raise(state, player, strength)
                    return PlayerAction.RAISE, raise_amount, 0.4
                return PlayerAction.CALL, min(call_amount, player.chips), 0.5
            return PlayerAction.FOLD, 0, 0.55

        # Weak hand: usually fold, sometimes bluff
        if random.random() < self.bluff_freq * 0.5 and call_amount <= player.chips * 0.05:
            raise_amount = self._calculate_raise(state, player, 0.3)
            return PlayerAction.RAISE, raise_amount, 0.3

        return PlayerAction.FOLD, 0, 0.7

    def _calculate_raise(self, state: GameState, player: Player, strength: float) -> int:
        """Calculate raise amount based on hand strength and aggression."""
        call_amount = state.current_bet - player.current_bet

        # Base raise: 2.5x the current bet for strong hands, 2x for medium
        multiplier = 2.0 + self.aggression * 1.5 + strength * 0.5

        if state.current_bet == 0:
            # Opening bet
            base = state.blinds.big * int(2 + self.aggression * 2)
        else:
            base = int(call_amount * multiplier)

        # Add some randomness
        base = int(base * random.uniform(0.8, 1.2))

        # Ensure minimum raise
        min_raise = state.blinds.big if state.current_bet == 0 else state.current_bet
        base = max(base, call_amount + min_raise)

        return min(base, player.chips)

    def _evaluate_preflop_hand(self, cards: list[Card]) -> float:
        """Evaluate pre-flop hand strength (0.0 to 1.0)."""
        if not cards or len(cards) != 2:
            return 0.0

        ranks = sorted([RANK_ORDER[c.rank] for c in cards], reverse=True)
        suited = cards[0].suit == cards[1].suit
        is_pair = ranks[0] == ranks[1]

        score = 0.0

        if is_pair:
            score = 0.5 + (ranks[0] - 2) / 24  # 0.5 for low pair, ~1.0 for AA
        else:
            # High cards + suited bonus
            high_card_score = (ranks[0] - 2) / 12 * 0.4
            second_card_score = (ranks[1] - 2) / 12 * 0.2
            suited_bonus = 0.1 if suited else 0.0
            connected_bonus = 0.1 if ranks[0] - ranks[1] <= 2 else 0.0
            score = high_card_score + second_card_score + suited_bonus + connected_bonus

        return min(1.0, score)

    @staticmethod
    def should_use_llm(state: GameState, player: Player, confidence: float,
                       trigger_config: dict) -> bool:
        """Determine if LLM should be consulted for this decision."""
        if confidence is None:
            return True

        # Low confidence
        if confidence < trigger_config.get("confidence_threshold", 0.6):
            return True

        # Large pot relative to stack
        pot_to_stack = state.pot / max(player.chips, 1)
        if pot_to_stack > trigger_config.get("pot_to_stack_ratio", 0.3):
            return True

        # Facing all-in
        if trigger_config.get("enable_on_allin", True):
            call_amount = state.current_bet - player.current_bet
            if call_amount >= player.chips * 0.5:
                return True

        # Late street key decision
        if trigger_config.get("enable_on_late_street", True):
            if len(state.community_cards) >= 4:  # Turn or River
                # Multi-way pot on late street
                active_count = len([p for p in state.players if p.is_active and not p.is_all_in])
                if active_count >= 2 and state.pot > player.chips * 0.3:
                    return True

        return False
```

- [ ] **Step 2: Verify rule engine**

Run:
```bash
cd D:\Claude\Texas_Poker && python -c "
from server.models.schemas import GameState, Player, Card, Suit, Rank, GamePhase, BlindsConfig
from server.ai.rule_engine import RuleEngine

# Create a test state
state = GameState(
    phase=GamePhase.PRE_FLOP,
    pot=15,
    current_bet=10,
    blinds=BlindsConfig(small=5, big=10),
)
player = Player(id='ai_1', name='AI1', chips=1000)
player.hole_cards = [Card(suit=Suit.HEARTS, rank=Rank.ACE), Card(suit=Suit.DIAMONDS, rank=Rank.KING)]

personality = {'aggression': 0.8, 'bluff_frequency': 0.15, 'preflop_range_pct': 15, 'fold_to_3bet': 0.4}
engine = RuleEngine(personality)
action, amount, confidence = engine.decide(state, player)
print(f'AK pre-flop: action={action}, amount={amount}, confidence={confidence:.2f}')
"
```

- [ ] **Step 3: Commit**

```bash
git add server/ai/rule_engine.py
git commit -m "feat: add rule-based AI decision engine"
```

---

### Task 9: LLM Client & Adapters

**Files:**
- Create: `server/llm/client.py`
- Create: `server/llm/claude_adapter.py`
- Create: `server/llm/openai_adapter.py`
- Create: `server/llm/custom_adapter.py`

- [ ] **Step 1: Write client.py**

```python
"""Abstract LLM client with provider-agnostic interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import yaml


@dataclass
class LLMDecision:
    action: str  # "fold", "check", "call", "raise", "all_in"
    amount: int
    reasoning: str
    confidence: float


class LLMClient(ABC):
    """Abstract base for LLM poker decision clients."""

    @abstractmethod
    async def decide(self, prompt: str) -> LLMDecision:
        """Send prompt to LLM and return structured decision."""
        ...


class LLMClientFactory:
    """Factory to create the appropriate LLM client based on config."""

    @staticmethod
    def create(config_path: str = "config/llm_config.yaml") -> Optional[LLMClient]:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        provider = config.get("provider", "anthropic")
        model = config.get("model", "claude-sonnet-4-6")
        api_key = config.get("api_key", "")
        max_tokens = config.get("max_tokens", 500)
        temperature = config.get("temperature", 0.7)
        timeout = config.get("timeout_seconds", 30)
        custom = config.get("custom", {})

        # Resolve env var in api_key
        if api_key.startswith("${") and api_key.endswith("}"):
            import os
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var, "")

        if provider == "anthropic":
            from server.llm.claude_adapter import ClaudeAdapter
            return ClaudeAdapter(api_key, model, max_tokens, temperature, timeout)
        elif provider == "openai":
            from server.llm.openai_adapter import OpenAIAdapter
            return OpenAIAdapter(api_key, model, max_tokens, temperature, timeout)
        elif provider == "custom":
            from server.llm.custom_adapter import CustomAdapter
            base_url = custom.get("base_url", "")
            headers = custom.get("headers", {})
            api_key_env = custom.get("api_key_env")
            if api_key_env:
                import os
                api_key = os.environ.get(api_key_env, api_key)
            return CustomAdapter(api_key, model, max_tokens, temperature, timeout, base_url, headers)
        else:
            return None
```

- [ ] **Step 2: Write claude_adapter.py**

```python
"""Anthropic Claude LLM adapter."""

import json
import httpx
from server.llm.client import LLMClient, LLMDecision


class ClaudeAdapter(LLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int,
                 temperature: float, timeout: int):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def decide(self, prompt: str) -> LLMDecision:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.base_url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = data["content"][0]["text"]
        return self._parse_response(content)

    def _parse_response(self, text: str) -> LLMDecision:
        """Parse JSON from LLM response text."""
        try:
            # Try to find JSON in the response
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end]
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                text = text[start:end]

            data = json.loads(text)
            return LLMDecision(
                action=data.get("action", "check"),
                amount=data.get("amount", 0),
                reasoning=data.get("reasoning", ""),
                confidence=data.get("confidence", 0.5),
            )
        except (json.JSONDecodeError, ValueError):
            return LLMDecision(action="check", amount=0,
                              reasoning="Failed to parse LLM response", confidence=0.3)
```

- [ ] **Step 3: Write openai_adapter.py**

```python
"""OpenAI GPT LLM adapter."""

import json
import httpx
from server.llm.client import LLMClient, LLMDecision


class OpenAIAdapter(LLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int,
                 temperature: float, timeout: int):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.base_url = "https://api.openai.com/v1/chat/completions"

    async def decide(self, prompt: str) -> LLMDecision:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.base_url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_response(content)

    def _parse_response(self, text: str) -> LLMDecision:
        try:
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end]
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                text = text[start:end]

            data = json.loads(text)
            return LLMDecision(
                action=data.get("action", "check"),
                amount=data.get("amount", 0),
                reasoning=data.get("reasoning", ""),
                confidence=data.get("confidence", 0.5),
            )
        except (json.JSONDecodeError, ValueError):
            return LLMDecision(action="check", amount=0,
                              reasoning="Failed to parse LLM response", confidence=0.3)
```

- [ ] **Step 4: Write custom_adapter.py**

```python
"""Custom OpenAI-compatible API adapter."""

import json
import httpx
from server.llm.client import LLMClient, LLMDecision


class CustomAdapter(LLMClient):
    def __init__(self, api_key: str, model: str, max_tokens: int,
                 temperature: float, timeout: int, base_url: str,
                 extra_headers: dict):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.extra_headers = extra_headers

    async def decide(self, prompt: str) -> LLMDecision:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }

        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.base_url, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_response(content)

    def _parse_response(self, text: str) -> LLMDecision:
        try:
            if "```json" in text:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end]
            elif "{" in text:
                start = text.index("{")
                end = text.rindex("}") + 1
                text = text[start:end]

            data = json.loads(text)
            return LLMDecision(
                action=data.get("action", "check"),
                amount=data.get("amount", 0),
                reasoning=data.get("reasoning", ""),
                confidence=data.get("confidence", 0.5),
            )
        except (json.JSONDecodeError, ValueError):
            return LLMDecision(action="check", amount=0,
                              reasoning="Failed to parse LLM response", confidence=0.3)
```

- [ ] **Step 5: Commit**

```bash
git add server/llm/client.py server/llm/claude_adapter.py server/llm/openai_adapter.py server/llm/custom_adapter.py
git commit -m "feat: add LLM client with Claude, OpenAI, and custom adapters"
```

---

### Task 10: AI Manager & Prompt Templates

**Files:**
- Create: `server/ai/prompts.py`
- Create: `server/ai/manager.py`

- [ ] **Step 1: Write prompts.py**

```python
"""LLM prompt templates for poker decision making."""

def build_poker_prompt(
    personality: str,
    hole_cards: str,
    community_cards: str,
    pot: int,
    current_bet: int,
    player_chips: int,
    position: str,
    action_history: str,
    variant: str,
) -> str:
    """Build a structured prompt for LLM poker decision."""

    return f"""You are an AI poker player with a {personality} playing style.
You are playing {variant} Texas Hold'em.

Your hole cards: {hole_cards}
Community cards: {community_cards if community_cards else "(none yet - pre-flop)"}

Current situation:
- Pot: {pot} chips
- Current bet to you: {current_bet} chips
- Your chips: {player_chips} chips
- Your position: {position}

Action history this hand:
{action_history}

Analyze this situation and respond with a JSON object containing:
{{
    "action": "fold" | "check" | "call" | "raise" | "all_in",
    "amount": <number, the amount to raise to if action is raise, or all-in amount if all_in>,
    "hand_assessment": "<brief assessment of your hand strength>",
    "opponent_read": "<your read on opponents based on their actions>",
    "reasoning": "<why you chose this action>",
    "confidence": <0.0 to 1.0, how confident you are in this decision>
}}

IMPORTANT:
- Play according to your {personality} style.
- Only make legal actions (you cannot check if there's a bet to call).
- Your raise amount must be at least the minimum raise and cannot exceed your chips.
- If you call, the amount should be the exact call amount (you don't need to specify it).
- For "all_in", set amount to your remaining chips.
- Respond with ONLY the JSON object, no other text."""
```

- [ ] **Step 2: Write manager.py**

```python
"""AI Manager — orchestrates rule engine and LLM decisions with data isolation."""

import asyncio
import random
import yaml
from server.models.schemas import GameState, Player, PlayerAction, Card
from server.ai.rule_engine import RuleEngine
from server.ai.prompts import build_poker_prompt
from server.llm.client import LLMClient


class AIManager:
    """Manages AI player decision making with data isolation."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client
        self.engines: dict[str, RuleEngine] = {}
        self._load_trigger_config()

    def _load_trigger_config(self):
        with open("config/llm_config.yaml") as f:
            config = yaml.safe_load(f)
        self.trigger_config = config.get("trigger", {})

    def register_player(self, player_id: str, personality: dict):
        """Create a rule engine for a player with their personality."""
        self.engines[player_id] = RuleEngine(personality)

    async def get_decision(self, state: GameState, player: Player) -> tuple[PlayerAction, int, str]:
        """
        Get AI decision for a player.
        Returns (action, amount, source: "RULE" or "LLM").

        DATA ISOLATION: Only public information from `state` is used.
        Player's hole cards are accessed via `player` parameter (own cards only).
        """
        engine = self.engines.get(player.id)
        if not engine:
            # Fallback: basic random
            if state.current_bet > player.current_bet:
                return PlayerAction.CALL, min(state.current_bet - player.current_bet, player.chips), "RULE"
            return PlayerAction.CHECK, 0, "RULE"

        # Step 1: Rule engine decision
        action, amount, confidence = engine.decide(state, player)

        # Step 2: Check if LLM should enhance
        if self.llm_client and RuleEngine.should_use_llm(state, player, confidence, self.trigger_config):
            try:
                llm_decision = await self._call_llm(state, player)
                if llm_decision:
                    action_map = {
                        "fold": PlayerAction.FOLD, "check": PlayerAction.CHECK,
                        "call": PlayerAction.CALL, "raise": PlayerAction.RAISE,
                        "all_in": PlayerAction.ALL_IN,
                    }
                    action = action_map.get(llm_decision.action, action)
                    amount = llm_decision.amount
                    return action, amount, "LLM"
            except Exception:
                pass  # Fall back to rule engine on LLM failure

        # Step 3: Apply thinking delay
        delay = random.uniform(2, 5)
        await asyncio.sleep(delay)

        return action, amount, "RULE"

    async def _call_llm(self, state: GameState, player: Player):
        """Call LLM with only public information + this player's cards."""
        # Build public context (data isolation enforced here)
        hole_str = ", ".join(str(c) for c in player.hole_cards)
        community_str = ", ".join(str(c) for c in state.community_cards)

        # Build action history (only public actions visible)
        history_lines = []
        for a in state.action_history:
            p = state.get_player_by_id(a["player_id"])
            if p:
                history_lines.append(f"{p.name} ({p.position.value if p.position else '?'}): {a['action']} {a.get('amount', '') or ''}")

        personality_name = player.personality.get("name", "balanced") if player.personality else "balanced"

        prompt = build_poker_prompt(
            personality=personality_name,
            hole_cards=hole_str,
            community_cards=community_str,
            pot=state.pot,
            current_bet=state.current_bet - player.current_bet,
            player_chips=player.chips,
            position=player.position.value if player.position else "unknown",
            action_history="\n".join(history_lines) if history_lines else "No actions yet",
            variant="No-Limit" if state.config.variant == "no_limit" else "Pot-Limit",
        )

        return await self.llm_client.decide(prompt)
```

- [ ] **Step 3: Commit**

```bash
git add server/ai/prompts.py server/ai/manager.py
git commit -m "feat: add AI Manager with rule+LLM orchestration and data isolation"
```

---

### Task 11: WebSocket Manager

**Files:**
- Create: `server/ws/manager.py`

- [ ] **Step 1: Write manager.py**

```python
"""WebSocket connection manager."""

from fastapi import WebSocket
import json


class WSManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}  # game_id -> [ws connections]
        self.human_ws: dict[str, WebSocket] = {}  # game_id -> human's ws

    async def connect(self, game_id: str, websocket: WebSocket, is_human: bool = False):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        if game_id not in self.connections:
            self.connections[game_id] = []
        self.connections[game_id].append(websocket)
        if is_human:
            self.human_ws[game_id] = websocket

    def disconnect(self, game_id: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if game_id in self.connections:
            self.connections[game_id].remove(websocket)
            if not self.connections[game_id]:
                del self.connections[game_id]
        if game_id in self.human_ws and self.human_ws[game_id] == websocket:
            del self.human_ws[game_id]

    async def broadcast(self, game_id: str, message: dict):
        """Send a message to all connections for a game."""
        if game_id not in self.connections:
            return
        msg_str = json.dumps(message)
        dead = []
        for ws in self.connections[game_id]:
            try:
                await ws.send_text(msg_str)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(game_id, ws)

    async def send_to_human(self, game_id: str, message: dict):
        """Send a message specifically to the human player."""
        ws = self.human_ws.get(game_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                del self.human_ws[game_id]

    async def receive_message(self, game_id: str, websocket: WebSocket) -> dict | None:
        """Receive and parse a message from a WebSocket."""
        try:
            data = await websocket.receive_text()
            return json.loads(data)
        except Exception:
            return None
```

- [ ] **Step 2: Commit**

```bash
git add server/ws/manager.py
git commit -m "feat: add WebSocket connection manager"
```

---

### Task 12: Replay Logger

**Files:**
- Create: `server/replay/logger.py`
- Create: `server/replay/playback.py`

- [ ] **Step 1: Write logger.py**

```python
"""Replay logger — records complete game state per hand."""

import json
import os
from datetime import datetime
from server.models.schemas import GameState, GameConfig


class ReplayLogger:
    """Records every hand of a game for later replay."""

    def __init__(self, game_id: str, config: GameConfig):
        self.game_id = game_id
        self.config = config
        self.hands: list[dict] = []
        self.current_hand: dict = {}
        self.current_actions: list[dict] = []

    def start_hand(self, state: GameState):
        """Begin recording a new hand."""
        self.current_hand = {
            "hand_number": state.hand_number,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "chips_start": p.chips,
                    "hole_cards": [c.to_dict() for c in p.hole_cards] if p.hole_cards else [],
                    "position": p.position.value if p.position else None,
                    "is_human": p.is_human,
                }
                for p in state.players
            ],
            "blinds": {"small": state.blinds.small, "big": state.blinds.big},
            "actions": [],
            "community_cards": [],
            "result": None,
        }
        self.current_actions = []

    def record_action(self, player_id: str, action: str, amount: int, source: str = "RULE"):
        """Record a player action."""
        self.current_actions.append({
            "player_id": player_id,
            "action": action,
            "amount": amount,
            "source": source,
        })

    def record_community(self, cards: list):
        """Record community cards dealt."""
        self.current_hand["community_cards"] = [c.to_dict() for c in cards]

    def end_hand(self, state: GameState, result: dict):
        """Finalize the current hand recording."""
        self.current_hand["actions"] = self.current_actions
        self.current_hand["result"] = result
        self.current_hand["players_end"] = [
            {"id": p.id, "name": p.name, "chips_end": p.chips}
            for p in state.players
        ]
        self.hands.append(self.current_hand)
        self.current_hand = {}
        self.current_actions = []

    def save(self):
        """Save complete game replay to JSON file."""
        os.makedirs("replays", exist_ok=True)
        filename = f"replays/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"

        replay_data = {
            "game_id": self.game_id,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "variant": self.config.variant,
                "starting_chips": self.config.starting_chips,
                "blinds_mode": self.config.blinds.mode,
                "ai_player_count": self.config.ai_player_count,
            },
            "hands": self.hands,
        }

        with open(filename, "w") as f:
            json.dump(replay_data, f, indent=2, default=str)

        return filename
```

- [ ] **Step 2: Write playback.py**

```python
"""Replay playback engine and statistics."""

import json
from typing import Optional


class ReplayPlayback:
    """Loads and serves replay data with statistics."""

    @staticmethod
    def load(replay_path: str) -> dict:
        """Load a replay file."""
        with open(replay_path) as f:
            return json.load(f)

    @staticmethod
    def list_replays() -> list[dict]:
        """List all saved replays."""
        import os
        replays = []
        if not os.path.exists("replays"):
            return replays
        for fname in sorted(os.listdir("replays"), reverse=True):
            if fname.endswith(".json"):
                fpath = os.path.join("replays", fname)
                with open(fpath) as f:
                    data = json.load(f)
                replays.append({
                    "id": fname.replace(".json", ""),
                    "filename": fname,
                    "timestamp": data.get("timestamp", ""),
                    "hands_played": len(data.get("hands", [])),
                    "config": data.get("config", {}),
                })
        return replays

    @staticmethod
    def compute_stats(replay_data: dict, player_id: str) -> dict:
        """Compute poker statistics for a specific player."""
        hands = replay_data.get("hands", [])
        total_hands = len(hands)
        if total_hands == 0:
            return {}

        vpip_count = 0  # Voluntarily Put money In Pot
        pfr_count = 0   # Pre-Flop Raise
        won_count = 0
        total_actions = 0
        aggressive_actions = 0

        for hand in hands:
            preflop_actions = [
                a for a in hand["actions"]
                if a["player_id"] == player_id
                and len(hand.get("community_cards", [])) == 0
            ]
            for a in preflop_actions:
                if a["action"] in ("call", "raise", "all_in"):
                    vpip_count += 1
                if a["action"] in ("raise", "all_in"):
                    pfr_count += 1

            # Check if player won
            result = hand.get("result", {})
            winners = result.get("winners", [])
            if any(w["player_id"] == player_id for w in winners):
                won_count += 1

            # Count aggressive actions
            for a in hand["actions"]:
                if a["player_id"] == player_id:
                    total_actions += 1
                    if a["action"] in ("raise", "all_in"):
                        aggressive_actions += 1

        return {
            "hands_played": total_hands,
            "vpip": round(vpip_count / total_hands * 100, 1),
            "pfr": round(pfr_count / total_hands * 100, 1),
            "win_rate": round(won_count / total_hands * 100, 1),
            "af": round(aggressive_actions / max(total_actions - aggressive_actions, 1), 1),
        }
```

- [ ] **Step 3: Commit**

```bash
git add server/replay/logger.py server/replay/playback.py
git commit -m "feat: add replay logger and playback with statistics"
```

---

### Task 13: FastAPI Server & Config

**Files:**
- Create: `server/config.py`
- Create: `server/main.py`

- [ ] **Step 1: Write config.py**

```python
"""Configuration loader."""

import yaml
import os


def load_llm_config(path: str = "config/llm_config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_personalities(path: str = "config/personalities.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 2: Write main.py**

```python
"""FastAPI application entry point."""

import uuid
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from server.models.schemas import (
    GameConfig, GameState,
)
from server.engine.game_controller import GameController
from server.ai.manager import AIManager
from server.llm.client import LLMClientFactory
from server.ws.manager import WSManager
from server.replay.logger import ReplayLogger
from server.replay.playback import ReplayPlayback


# Global state
ws_manager = WSManager()
games: dict[str, GameController] = {}
replays: dict[str, str] = {}  # game_id -> replay filepath

app = FastAPI(title="Texas Hold'em Poker")


@app.post("/api/game/start")
async def start_game(config: GameConfig):
    """Start a new game with the given configuration."""
    game_id = str(uuid.uuid4())[:8]
    controller = GameController(config, game_id)
    controller.init_players()

    # Setup AI Manager
    llm_client = LLMClientFactory.create()
    ai_manager = AIManager(llm_client)
    for player in controller.state.players:
        if not player.is_human and player.personality:
            ai_manager.register_player(player.id, player.personality)

    # Wire up callbacks
    ws_manager_obj = ws_manager
    replay = ReplayLogger(game_id, config)
    controller._ai_manager = ai_manager  # Attach AI manager

    # Override the AI action method
    original_get_ai = controller._get_ai_action

    async def ai_action_with_manager(player):
        action, amount, source = await ai_manager.get_decision(controller.state, player)
        replay.record_action(player.id, action.value, amount, source)
        return action, amount

    controller._get_ai_action = ai_action_with_manager

    async def on_game_state(state):
        await ws_manager_obj.broadcast(game_id, {
            "type": "game_state",
            "state": state.model_dump() if hasattr(state, 'model_dump') else state,
        })

    async def on_your_turn(data):
        await ws_manager_obj.send_to_human(game_id, {
            "type": "your_turn",
            **data,
        })

    async def on_player_action(data):
        await ws_manager_obj.broadcast(game_id, {
            "type": "player_action",
            **data,
        })

    async def on_ai_thinking(data):
        await ws_manager_obj.broadcast(game_id, {
            "type": "ai_thinking",
            **data,
        })

    async def on_hand_result(data):
        replay.end_hand(controller.state, data)
        await ws_manager_obj.broadcast(game_id, {
            "type": "hand_result",
            **data,
        })

    async def on_game_over(data):
        replay_path = replay.save()
        replays[game_id] = replay_path
        # Build stats for all players
        replay_data = ReplayPlayback.load(replay_path)
        all_stats = {}
        for p in controller.state.players:
            all_stats[p.id] = ReplayPlayback.compute_stats(replay_data, p.id)

        await ws_manager_obj.broadcast(game_id, {
            "type": "game_over",
            "rankings": data.get("rankings", []),
            "stats": all_stats,
            "replay_id": game_id,
        })

    async def on_community_updated(state):
        replay.record_community(state.community_cards)
        await ws_manager_obj.broadcast(game_id, {
            "type": "game_state",
            "state": state.model_dump() if hasattr(state, 'model_dump') else {},
        })

    async def on_game_started(state):
        replay.start_hand(state)

    controller.on("game_started", on_game_started)
    controller.on("game_state", on_game_state)
    controller.on("your_turn", on_your_turn)
    controller.on("player_action", on_player_action)
    controller.on("ai_thinking", on_ai_thinking)
    controller.on("hand_result", on_hand_result)
    controller.on("game_over", on_game_over)
    controller.on("community_updated", on_community_updated)

    games[game_id] = controller

    # Start game in background
    asyncio.create_task(controller.run())

    return {"game_id": game_id}


@app.get("/api/replays")
async def list_replays():
    """List all saved replays."""
    return ReplayPlayback.list_replays()


@app.get("/api/replay/{replay_id}")
async def get_replay(replay_id: str):
    """Get replay data for a specific game."""
    replay_data = ReplayPlayback.load(f"replays/{replay_id}.json")
    return replay_data


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    """WebSocket endpoint for real-time game communication."""
    await ws_manager.connect(game_id, websocket, is_human=True)

    try:
        while True:
            message = await ws_manager.receive_message(game_id, websocket)
            if message is None:
                break

            msg_type = message.get("type", "")

            if msg_type == "player_action":
                controller = games.get(game_id)
                if controller:
                    controller.submit_human_action(
                        action=message.get("action", "fold"),
                        amount=message.get("amount", 0),
                    )

            elif msg_type == "new_game":
                # Handle new game request
                config = GameConfig(**message.get("config", {}))
                # Reconnect with new game
                pass

    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(game_id, websocket)


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 3: Commit**

```bash
git add server/config.py server/main.py
git commit -m "feat: add FastAPI server with REST and WebSocket endpoints"
```

---

### Task 14: Frontend — HTML & CSS

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/css/style.css`

- [ ] **Step 1: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Texas Hold'em Poker</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body>

<div id="app">
  <!-- Setup View -->
  <div id="setup-view" class="view active">
    <div class="setup-container">
      <div class="setup-header">
        <h1>♠ ♥ Texas Hold'em ♦ ♣</h1>
        <p class="subtitle">Configure your game</p>
      </div>
      <div class="setup-form">
        <div class="form-col">
          <div class="form-group">
            <label>Game Mode</label>
            <div class="toggle-group" id="variant-toggle">
              <button class="toggle-btn active" data-value="no_limit">No-Limit</button>
              <button class="toggle-btn" data-value="pot_limit">Pot-Limit</button>
            </div>
          </div>
          <div class="form-group">
            <label>AI Players: <span id="ai-count-display">5</span></label>
            <div class="stepper">
              <button id="ai-count-minus">−</button>
              <span id="ai-count-value">5</span>
              <button id="ai-count-plus">+</button>
            </div>
          </div>
          <div class="form-group">
            <label>Starting Chips</label>
            <input type="number" id="starting-chips" value="1000" min="100" max="10000" step="100">
          </div>
          <div class="form-group">
            <label>Blinds Mode</label>
            <div class="toggle-group" id="blinds-mode-toggle">
              <button class="toggle-btn active" data-value="fixed">Fixed</button>
              <button class="toggle-btn" data-value="increasing">Increasing</button>
            </div>
          </div>
        </div>
        <div class="form-col">
          <div class="form-group">
            <label>Small Blind / Big Blind</label>
            <div class="input-pair">
              <input type="number" id="sb-value" value="5" min="1">
              <span>/</span>
              <input type="number" id="bb-value" value="10" min="2">
            </div>
          </div>
          <div class="form-group" id="blinds-increase-group" style="display:none;">
            <label>Increase every <input type="number" id="blinds-interval" value="10" min="1" style="width:50px;"> hands, ×<input type="number" id="blinds-multiplier" value="2" min="1.1" step="0.1" style="width:60px;"></label>
          </div>
          <div class="form-group">
            <label>AI Personality</label>
            <div class="toggle-group" id="personality-toggle">
              <button class="toggle-btn active" data-value="random">Random</button>
              <button class="toggle-btn" data-value="manual">Manual</button>
            </div>
          </div>
          <div class="form-group">
            <label>LLM Provider</label>
            <select id="llm-provider">
              <option value="anthropic">Anthropic Claude</option>
              <option value="openai">OpenAI GPT</option>
              <option value="custom">Custom API</option>
            </select>
          </div>
          <div class="form-group">
            <label>API Key</label>
            <input type="password" id="api-key" placeholder="••••••••">
          </div>
        </div>
      </div>
      <button id="start-game-btn" class="btn-start">🃏 Start Game</button>
    </div>
  </div>

  <!-- Game View -->
  <div id="game-view" class="view">
    <div id="top-bar">
      <span class="title">♠ Texas Hold'em</span>
      <span id="game-info">Hand #0 | Blinds 5/10 | No-Limit</span>
    </div>
    <div id="game-main">
      <div id="left-sidebar">
        <div class="section-title">Your Hand</div>
        <div id="your-cards" class="cards-display"></div>
        <div class="info-row"><span>Position:</span> <span id="your-position">--</span></div>
        <div class="info-row"><span>Chips:</span> <span id="your-chips">--</span></div>
        <div class="info-row"><span>Pot:</span> <span id="pot-display">0</span></div>
        <div class="info-row"><span>Current Bet:</span> <span id="current-bet-display">0</span></div>
      </div>
      <div id="table-container">
        <div id="poker-table">
          <div id="players-container"></div>
          <div id="community-cards" class="cards-display"></div>
          <div id="pot-label">Pot: <span id="pot-center">0</span></div>
        </div>
      </div>
      <div id="right-sidebar">
        <div class="section-title">Action Log</div>
        <div id="action-log"></div>
      </div>
    </div>
    <div id="action-bar">
      <button id="btn-fold" class="action-btn fold">Fold</button>
      <button id="btn-check" class="action-btn check">Check</button>
      <button id="btn-call" class="action-btn call">Call <span id="call-amount">0</span></button>
      <div class="raise-group">
        <input type="range" id="raise-slider" min="0" max="1000" value="0">
        <input type="number" id="raise-amount" value="0" min="0">
        <button id="btn-raise" class="action-btn raise">Raise</button>
      </div>
      <button id="btn-allin" class="action-btn allin">All-in</button>
    </div>
  </div>

  <!-- Results View -->
  <div id="results-view" class="view">
    <div class="results-container">
      <div class="results-header">
        <h1>🏆 Game Over</h1>
        <p id="results-hands-count">0 hands played</p>
      </div>
      <div id="rankings-list"></div>
      <div id="stats-panel">
        <h3>📊 Your Statistics</h3>
        <div id="your-stats"></div>
      </div>
      <div class="results-actions">
        <button id="btn-play-again" class="btn-start">🔄 Play Again</button>
        <button id="btn-view-replay" class="btn-secondary">▶ View Replay</button>
      </div>
    </div>
  </div>
</div>

<script src="/static/js/ws.js"></script>
<script src="/static/js/setup.js"></script>
<script src="/static/js/table.js"></script>
<script src="/static/js/results.js"></script>
<script src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write style.css**

This is a large file. Key CSS:

```css
/* === Reset & Base === */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #1a1a2e;
  --bg-dark: #0f0f1a;
  --bg-panel: #12121f;
  --table-green: #0d4a1e;
  --table-green-light: #1b6e3a;
  --rail: #5d3a1a;
  --gold: #ffd740;
  --text: #e2e2e2;
  --text-dim: #888;
  --red: #b71c1c;
  --green: #1b5e20;
  --blue: #0d47a1;
  --orange: #e65100;
  --purple: #4a148c;
}

body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow: hidden;
}

/* === View Management === */
.view { display: none; position: absolute; inset: 0; }
.view.active { display: flex; flex-direction: column; }

/* === Setup View === */
#setup-view {
  align-items: center; justify-content: center;
  background: radial-gradient(ellipse at center, #1a1a3e, #0a0a1e);
}
.setup-container {
  background: var(--bg-panel);
  border: 1px solid #333;
  border-radius: 12px;
  padding: 32px;
  max-width: 700px;
  width: 90%;
}
.setup-header { text-align: center; margin-bottom: 24px; }
.setup-header h1 { color: var(--gold); font-size: 24px; }
.setup-header .subtitle { color: var(--text-dim); font-size: 13px; margin-top: 4px; }
.setup-form { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
.form-group { margin-bottom: 10px; }
.form-group label { color: #ffb74d; font-size: 12px; display: block; margin-bottom: 4px; }
.toggle-group { display: flex; gap: 4px; }
.toggle-btn {
  background: #333; color: var(--text-dim); border: none;
  padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 11px;
}
.toggle-btn.active { background: var(--gold); color: #000; }
.stepper { display: flex; align-items: center; gap: 8px; }
.stepper button { background: #333; color: #fff; border: none; width: 24px; height: 24px; border-radius: 4px; cursor: pointer; }
.stepper span { font-size: 14px; min-width: 20px; text-align: center; }
input[type="number"], select, input[type="password"] {
  background: #1a1a2e; color: #fff; border: 1px solid #444;
  padding: 4px 8px; border-radius: 4px; font-size: 12px; width: 80px;
}
select { width: 100%; }
.input-pair { display: flex; gap: 6px; align-items: center; }
.btn-start {
  display: block; width: 100%; padding: 12px;
  background: linear-gradient(135deg, var(--gold), #ff8f00);
  color: #000; border: none; border-radius: 8px;
  font-size: 16px; font-weight: bold; cursor: pointer;
}
.btn-start:hover { opacity: 0.9; }
.btn-secondary {
  padding: 10px 24px; background: #333; color: #fff;
  border: none; border-radius: 6px; cursor: pointer; font-size: 13px;
}

/* === Game View Layout === */
#game-view { flex-direction: column; }
#top-bar {
  display: flex; justify-content: space-between; align-items: center;
  background: var(--bg-dark); padding: 8px 16px; border-bottom: 1px solid #333;
}
#top-bar .title { color: var(--gold); font-weight: bold; font-size: 14px; }
#top-bar #game-info { color: var(--text-dim); font-size: 11px; }
#game-main { display: flex; flex: 1; min-height: 0; }
#left-sidebar, #right-sidebar {
  width: 180px; background: var(--bg-panel); padding: 12px;
  font-size: 11px; color: var(--text-dim); overflow-y: auto;
}
#left-sidebar { border-right: 1px solid #222; }
#right-sidebar { border-left: 1px solid #222; }
.section-title { color: #ffb74d; font-weight: bold; margin-bottom: 8px; font-size: 12px; }
.info-row { display: flex; justify-content: space-between; margin-bottom: 4px; }
.info-row span:first-child { color: var(--text-dim); }
.info-row span:last-child { color: #fff; }
#your-cards { display: flex; gap: 6px; margin: 8px 0; }

/* === Poker Table === */
#table-container { flex: 1; display: flex; align-items: center; justify-content: center; padding: 20px; }
#poker-table {
  width: 500px; height: 300px;
  background: radial-gradient(ellipse, var(--table-green-light), var(--table-green));
  border-radius: 50%; border: 12px solid var(--rail);
  position: relative;
  box-shadow: 0 0 60px rgba(0,0,0,0.5), inset 0 0 40px rgba(0,0,0,0.3);
}
#community-cards {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  display: flex; gap: 6px;
}
#pot-label {
  position: absolute; top: 62%; left: 50%;
  transform: translateX(-50%);
  color: var(--gold); font-size: 11px; font-weight: bold;
}

/* === Cards === */
.cards-display { display: flex; gap: 4px; }
.card {
  width: 40px; height: 56px; background: #fff; color: #000;
  border-radius: 4px; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.4);
}
.card.red { color: #d32f2f; }
.card.black { color: #212121; }
.card.back { background: #1565c0; color: #fff; font-size: 10px; }
.card.small { width: 30px; height: 42px; font-size: 10px; }

/* === Player Positions === */
.player-spot {
  position: absolute; text-align: center; transform: translate(-50%, -50%);
}
.player-badge {
  background: #1a1a2e; color: #fff; padding: 4px 10px;
  border-radius: 12px; font-size: 10px; white-space: nowrap;
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.player-badge.human { border: 1px solid var(--gold); color: var(--gold); }
.player-badge.active-turn { border-color: #4fc3f7; animation: pulse 1.5s infinite; }
.player-badge.folded { opacity: 0.4; text-decoration: line-through; }
.player-badge .player-name { font-weight: bold; }
.player-badge .player-chips { color: var(--text-dim); font-size: 9px; }
.player-spot .dealer-btn {
  background: #fff; color: #000; border-radius: 50%;
  width: 16px; height: 16px; font-size: 8px;
  line-height: 16px; text-align: center; font-weight: bold;
  position: absolute; top: -6px; right: -6px;
}
.thinking-indicator {
  color: #ffb74d; font-size: 9px; animation: pulse 1s infinite;
}

/* === Action Bar === */
#action-bar {
  display: flex; gap: 8px; align-items: center; justify-content: center;
  padding: 12px 16px; background: var(--bg-dark); border-top: 1px solid #333;
}
.action-btn {
  padding: 8px 20px; border: none; border-radius: 20px;
  color: #fff; font-size: 13px; font-weight: bold; cursor: pointer;
  min-width: 90px;
}
.action-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.action-btn.fold { background: var(--red); }
.action-btn.check { background: var(--green); }
.action-btn.call { background: var(--blue); }
.action-btn.raise { background: var(--orange); }
.action-btn.allin { background: var(--purple); }
.raise-group { display: flex; gap: 6px; align-items: center; }
#raise-slider { width: 100px; }
#raise-amount { width: 70px; }

/* === Results View === */
#results-view {
  align-items: center; justify-content: center;
  background: radial-gradient(ellipse at center, #1a1a3e, #0a0a1e);
}
.results-container {
  background: var(--bg-panel); border: 1px solid #333;
  border-radius: 12px; padding: 28px; max-width: 500px; width: 90%;
}
.results-header { text-align: center; margin-bottom: 16px; }
.results-header h1 { color: var(--gold); }
#rankings-list { margin-bottom: 16px; }
.rank-row {
  display: flex; justify-content: space-between; padding: 6px 10px;
  border-radius: 4px; margin-bottom: 3px; font-size: 12px;
}
.rank-row.first { background: #1b5e20; color: var(--gold); }
.rank-row.busted { background: #b71c1c; }
.rank-row .medal { margin-right: 8px; }
#stats-panel { background: #1a1a2e; border-radius: 6px; padding: 12px; margin-bottom: 16px; }
#stats-panel h3 { color: #ffb74d; font-size: 12px; margin-bottom: 6px; }
.stat-row { display: flex; justify-content: space-between; font-size: 11px; color: #aaa; margin-bottom: 2px; }
.results-actions { display: flex; gap: 8px; justify-content: center; }

/* === Action Log === */
#action-log { font-size: 10px; line-height: 1.8; }
.log-entry { padding: 2px 0; border-bottom: 1px solid #1a1a2e; }
.log-entry .action-fold { color: #ef5350; }
.log-entry .action-raise { color: #4fc3f7; }
.log-entry .action-call { color: #66bb6a; }
.log-entry .action-allin { color: #ce93d8; }

/* === Animations === */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* === Responsive === */
@media (max-width: 900px) {
  #left-sidebar, #right-sidebar { width: 140px; font-size: 10px; }
  #poker-table { width: 380px; height: 230px; }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html frontend/css/style.css
git commit -m "feat: add frontend HTML structure and dark casino CSS theme"
```

---

### Task 15: Frontend — JavaScript Modules

**Files:**
- Create: `frontend/js/ws.js`
- Create: `frontend/js/setup.js`
- Create: `frontend/js/table.js`
- Create: `frontend/js/results.js`
- Create: `frontend/js/app.js`

- [ ] **Step 1: Write ws.js**

```javascript
// WebSocket client
const WSClient = {
    ws: null,
    gameId: null,
    handlers: {},

    connect(gameId) {
        this.gameId = gameId;
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws/${gameId}`;
        this.ws = new WebSocket(url);

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            const handler = this.handlers[msg.type];
            if (handler) handler(msg);
        };

        this.ws.onclose = () => console.log('WebSocket disconnected');
        this.ws.onerror = (e) => console.error('WebSocket error:', e);
    },

    on(type, handler) {
        this.handlers[type] = handler;
    },

    send(msg) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(msg));
        }
    },

    close() {
        if (this.ws) this.ws.close();
    }
};
```

- [ ] **Step 2: Write setup.js**

```javascript
// Setup view logic
const SetupView = {
    aiCount: 5,

    init() {
        document.getElementById('start-game-btn').addEventListener('click', () => this.startGame());

        // AI count stepper
        document.getElementById('ai-count-plus').addEventListener('click', () => {
            if (this.aiCount < 8) { this.aiCount++; this.updateDisplay(); }
        });
        document.getElementById('ai-count-minus').addEventListener('click', () => {
            if (this.aiCount > 2) { this.aiCount--; this.updateDisplay(); }
        });

        // Toggle groups
        this._setupToggle('variant-toggle');
        this._setupToggle('blinds-mode-toggle');
        this._setupToggle('personality-toggle');

        // Blinds mode: show/hide increase options
        document.querySelectorAll('#blinds-mode-toggle .toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.value;
                document.getElementById('blinds-increase-group').style.display =
                    mode === 'increasing' ? 'block' : 'none';
            });
        });
    },

    updateDisplay() {
        document.getElementById('ai-count-display').textContent = this.aiCount;
        document.getElementById('ai-count-value').textContent = this.aiCount;
    },

    _setupToggle(groupId) {
        const group = document.getElementById(groupId);
        group.querySelectorAll('.toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                group.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    },

    getConfig() {
        const getToggle = (id) => document.querySelector(`#${id} .toggle-btn.active`).dataset.value;
        return {
            variant: getToggle('variant-toggle'),
            ai_player_count: this.aiCount,
            starting_chips: parseInt(document.getElementById('starting-chips').value),
            blinds: {
                mode: getToggle('blinds-mode-toggle'),
                small: parseInt(document.getElementById('sb-value').value),
                big: parseInt(document.getElementById('bb-value').value),
                increase_interval: parseInt(document.getElementById('blinds-interval').value || 10),
                increase_multiplier: parseFloat(document.getElementById('blinds-multiplier').value || 2),
            },
            personality_mode: getToggle('personality-toggle'),
            llm_provider: document.getElementById('llm-provider').value,
        };
    },

    async startGame() {
        const config = this.getConfig();
        try {
            const resp = await fetch('/api/game/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            const data = await resp.json();
            App.startGame(data.game_id);
        } catch (err) {
            alert('Failed to start game: ' + err.message);
        }
    }
};
```

- [ ] **Step 3: Write table.js**

```javascript
// Game table rendering and interaction
const TableView = {
    state: null,
    validActions: null,

    init() {
        // Action buttons
        document.getElementById('btn-fold').addEventListener('click', () => this.submitAction('fold'));
        document.getElementById('btn-check').addEventListener('click', () => this.submitAction('check'));
        document.getElementById('btn-call').addEventListener('click', () => this.submitAction('call'));
        document.getElementById('btn-raise').addEventListener('click', () => {
            const amount = parseInt(document.getElementById('raise-amount').value) || 0;
            this.submitAction('raise', amount);
        });
        document.getElementById('btn-allin').addEventListener('click', () => this.submitAction('all_in'));

        // Raise slider sync
        const slider = document.getElementById('raise-slider');
        const input = document.getElementById('raise-amount');
        slider.addEventListener('input', () => { input.value = slider.value; });
        input.addEventListener('input', () => { slider.value = input.value; });
    },

    updateFromState(msg) {
        this.state = msg.state;
        this.render();
    },

    updateYourTurn(msg) {
        this.validActions = msg.valid_actions;
        document.getElementById('call-amount').textContent = msg.call_amount || 0;
        this.updateActionButtons(msg);
    },

    updateActionButtons(msg) {
        const actions = msg.valid_actions || {};
        const setBtn = (id, enabled) => {
            const btn = document.getElementById(id);
            if (btn) btn.disabled = !enabled;
        };

        setBtn('btn-fold', !!actions.fold);
        setBtn('btn-check', !!actions.check);
        setBtn('btn-call', !!actions.call);
        setBtn('btn-raise', !!actions.raise);
        setBtn('btn-allin', !!actions.all_in);

        if (actions.raise) {
            document.getElementById('raise-slider').min = actions.raise.min || 0;
            document.getElementById('raise-slider').max = actions.raise.max || 0;
            document.getElementById('raise-amount').min = actions.raise.min || 0;
            document.getElementById('raise-amount').max = actions.raise.max || 0;
        }
    },

    submitAction(action, amount = 0) {
        WSClient.send({ type: 'player_action', action, amount });
        // Disable buttons while waiting
        ['btn-fold','btn-check','btn-call','btn-raise','btn-allin'].forEach(id => {
            document.getElementById(id).disabled = true;
        });
    },

    render() {
        if (!this.state) return;

        const s = this.state;

        // Top bar
        document.getElementById('game-info').textContent =
            `Hand #${s.hand_number} | Blinds ${s.blinds.small}/${s.blinds.big} | ${s.config?.variant === 'pot_limit' ? 'Pot-Limit' : 'No-Limit'}`;

        // Left sidebar
        const human = s.players.find(p => p.is_human);
        if (human) {
            document.getElementById('your-cards').innerHTML = this._renderCards(human.hole_cards);
            document.getElementById('your-position').textContent = human.position || '--';
            document.getElementById('your-chips').textContent = human.chips;
        }
        document.getElementById('pot-display').textContent = s.pot;
        document.getElementById('current-bet-display').textContent = s.current_bet;
        document.getElementById('pot-center').textContent = s.pot;

        // Community cards
        document.getElementById('community-cards').innerHTML = this._renderCards(s.community_cards);

        // Players on table
        this._renderPlayers(s.players);

        // Right sidebar — only append new actions
        this._renderActionLog(s.action_history);
    },

    _renderCards(cards) {
        if (!cards || cards.length === 0) return '';
        return cards.map(c => {
            const suitSymbols = { hearts: '♥', diamonds: '♦', clubs: '♣', spades: '♠' };
            const isRed = c.suit === 'hearts' || c.suit === 'diamonds';
            return `<div class="card ${isRed ? 'red' : 'black'}">${c.rank}${suitSymbols[c.suit] || c.suit[0]}</div>`;
        }).join('');
    },

    _renderPlayers(players) {
        const container = document.getElementById('players-container');
        if (!container) return;

        const positions = this._getTablePositions(players.length);
        container.innerHTML = players.map((p, i) => {
            const pos = positions[i];
            let cls = 'player-spot';
            if (p.is_human) cls += ' human';
            if (!p.is_active) cls += ' folded';
            return `
                <div class="${cls}" style="left:${pos.x}%;top:${pos.y}%">
                    <div class="player-badge${p.is_human ? ' human' : ''}${!p.is_active ? ' folded' : ''}">
                        <span class="player-name">${p.is_human ? '👤 You' : '🤖 ' + p.name}</span>
                        <span class="player-chips">${p.chips}</span>
                        ${p.total_bet_this_round > 0 ? `<span class="player-bet">Bet: ${p.total_bet_this_round}</span>` : ''}
                    </div>
                </div>`;
        }).join('');
    },

    _getTablePositions(count) {
        // Pre-computed positions for oval table layout
        const allPositions = {
            2: [{x:50,y:75}, {x:50,y:25}],
            3: [{x:50,y:80}, {x:15,y:25}, {x:85,y:25}],
            4: [{x:50,y:80}, {x:10,y:30}, {x:90,y:30}, {x:50,y:20}],
            5: [{x:50,y:82}, {x:8,y:35}, {x:92,y:35}, {x:30,y:18}, {x:70,y:18}],
            6: [{x:50,y:82}, {x:8,y:35}, {x:92,y:35}, {x:20,y:15}, {x:80,y:15}, {x:50,y:18}],
            7: [{x:50,y:84}, {x:8,y:35}, {x:92,y:35}, {x:15,y:14}, {x:85,y:14}, {x:38,y:16}, {x:62,y:16}],
            8: [{x:50,y:84}, {x:8,y:40}, {x:92,y:40}, {x:10,y:14}, {x:90,y:14}, {x:30,y:16}, {x:70,y:16}, {x:50,y:16}],
            9: [{x:50,y:84}, {x:5,y:40}, {x:95,y:40}, {x:8,y:14}, {x:92,y:14}, {x:25,y:15}, {x:75,y:15}, {x:50,y:14}],
        };
        return allPositions[count] || allPositions[6];
    },

    _renderActionLog(history) {
        const log = document.getElementById('action-log');
        if (!log) return;
        // Only render the last few actions
        const recent = history.slice(-15);
        log.innerHTML = recent.map(a => {
            const cls = `action-${a.action}`;
            const amount = a.amount ? ` ${a.amount}` : '';
            return `<div class="log-entry"><span class="${cls}">${a.player_id}: ${a.action}${amount}</span></div>`;
        }).join('');
        log.scrollTop = log.scrollHeight;
    },

    addLogEntry(text) {
        const log = document.getElementById('action-log');
        if (log) {
            const div = document.createElement('div');
            div.className = 'log-entry';
            div.textContent = text;
            log.appendChild(div);
            log.scrollTop = log.scrollHeight;
        }
    }
};
```

- [ ] **Step 4: Write results.js**

```javascript
// Results view logic
const ResultsView = {
    show(msg) {
        const rankings = msg.rankings || [];
        const stats = msg.stats || {};
        const replayId = msg.replay_id || '';

        document.getElementById('results-hands-count').textContent =
            `${rankings.length} players`;

        // Rankings
        const medals = ['🥇', '🥈', '🥉'];
        document.getElementById('rankings-list').innerHTML = rankings.map((r, i) => {
            let cls = 'rank-row';
            if (i === 0) cls += ' first';
            if (r.chips <= 0) cls += ' busted';
            const medal = i < 3 ? medals[i] : `${i+1}th`;
            return `<div class="${cls}">
                <span><span class="medal">${medal}</span> ${r.name}</span>
                <span><strong>${r.chips}</strong></span>
            </div>`;
        }).join('');

        // Human stats
        const humanStats = stats['human'] || {};
        document.getElementById('your-stats').innerHTML = `
            <div class="stat-row"><span>VPIP</span><span>${humanStats.vpip || 0}%</span></div>
            <div class="stat-row"><span>PFR</span><span>${humanStats.pfr || 0}%</span></div>
            <div class="stat-row"><span>Win Rate</span><span>${humanStats.win_rate || 0}%</span></div>
            <div class="stat-row"><span>Aggression Factor</span><span>${humanStats.af || 0}</span></div>
        `;

        // Store replay ID
        document.getElementById('btn-view-replay').dataset.replayId = replayId;

        App.showView('results-view');
    }
};
```

- [ ] **Step 5: Write app.js**

```javascript
// Main application controller
const App = {
    currentView: 'setup-view',
    currentGameId: null,

    init() {
        SetupView.init();
        TableView.init();

        document.getElementById('btn-play-again').addEventListener('click', () => {
            App.showView('setup-view');
        });

        document.getElementById('btn-view-replay').addEventListener('click', async () => {
            const replayId = document.getElementById('btn-view-replay').dataset.replayId;
            if (replayId) {
                try {
                    const resp = await fetch(`/api/replay/${replayId}`);
                    const data = await resp.json();
                    alert('Replay loaded: ' + data.hands.length + ' hands. Full replay viewer coming soon.');
                } catch (err) {
                    alert('Failed to load replay: ' + err.message);
                }
            }
        });
    },

    showView(viewId) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
        this.currentView = viewId;
    },

    startGame(gameId) {
        this.currentGameId = gameId;
        this.showView('game-view');

        // Setup WebSocket handlers
        WSClient.connect(gameId);

        WSClient.on('game_state', (msg) => {
            TableView.updateFromState(msg);
        });

        WSClient.on('your_turn', (msg) => {
            TableView.updateYourTurn(msg);
        });

        WSClient.on('player_action', (msg) => {
            TableView.addLogEntry(`${msg.player_name || msg.player_id}: ${msg.action} ${msg.amount || ''}`);
        });

        WSClient.on('ai_thinking', (msg) => {
            TableView.addLogEntry(`${msg.player_name} is thinking...`);
        });

        WSClient.on('hand_result', (msg) => {
            const winnerNames = (msg.winners || []).map(w => w.player_id).join(', ');
            TableView.addLogEntry(`--- Hand over! Winner: ${winnerNames} ---`);
        });

        WSClient.on('game_over', (msg) => {
            ResultsView.show(msg);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
```

- [ ] **Step 6: Commit**

```bash
git add frontend/js/ws.js frontend/js/setup.js frontend/js/table.js frontend/js/results.js frontend/js/app.js
git commit -m "feat: add frontend JS modules for real-time poker gameplay"
```

---

### Task 16: Integration & End-to-End Verification

- [ ] **Step 1: Verify server starts**

Run:
```bash
cd D:\Claude\Texas_Poker && timeout 5 python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 || true
```
Expected: Server starts without import errors.

- [ ] **Step 2: Verify setup API**

Start server in background, then:
```bash
curl -s -X POST http://localhost:8000/api/game/start \
  -H "Content-Type: application/json" \
  -d '{"variant":"no_limit","ai_player_count":2,"starting_chips":1000,"blinds":{"mode":"fixed","small":5,"big":10},"personality_mode":"random","llm_provider":"anthropic"}'
```
Expected: Returns `{"game_id": "<8-char-id>"}`

- [ ] **Step 3: Verify frontend is served**

Open `http://localhost:8000` in browser. Setup screen should display with full styling.

- [ ] **Step 4: Verify WebSocket connection**

Connect via browser console:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/test');
ws.onopen = () => console.log('Connected');
```
Expected: "Connected"

- [ ] **Step 5: End-to-end playthrough**

1. Open `http://localhost:8000`
2. Configure game (2 AI players, 1000 chips, fixed blinds 5/10)
3. Click "Start Game"
4. Verify table layout renders with player positions
5. Verify AI players take actions (visible in action log)
6. When human's turn, verify action buttons enable
7. Play through several hands
8. Verify game ends when someone busts
9. Verify results screen shows rankings and stats

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: complete integration, end-to-end game working"
```

---

## Verification Checklist

- [ ] Server starts without errors: `uvicorn server.main:app`
- [ ] Setup API returns game_id
- [ ] Frontend loads at `http://localhost:8000`
- [ ] WebSocket connects successfully
- [ ] Complete game loop: setup → play multiple hands → bust → results
- [ ] AI players make varied decisions (not all the same action)
- [ ] Side pots calculated correctly (test with varying all-in amounts)
- [ ] Hand evaluator correctly ranks all hand types
- [ ] Blinds increase in increasing mode
- [ ] Pot-Limit variant enforces bet limits
- [ ] Replay JSON file saved after game ends
- [ ] Replay list API returns saved replays
- [ ] AI data isolation: no agent accesses other agents' hole cards

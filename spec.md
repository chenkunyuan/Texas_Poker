# Texas Hold'em Poker — Functional Specification

> **Phase 1: Functional Design** | Approved: 2026-06-28
>
> Phase 2 (UI Design) to follow after this spec is confirmed.

---

## 1. Overview

A browser-based Texas Hold'em poker game featuring one human player, one AI dealer, and N AI agent players. The game supports configurable rules, AI personalities, LLM-enhanced decision making, and full replay capability.

---

## 2. Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python (FastAPI) |
| Real-time Communication | WebSocket |
| Frontend | HTML + CSS + JavaScript (vanilla or lightweight) |
| LLM Integration | Provider-agnostic adapter pattern |
| Storage | JSON files (game replays) |

---

## 3. Game Rules

### 3.1 Variants
- **No-Limit Texas Hold'em**: Players may bet/raise any amount up to their stack, including All-in
- **Pot-Limit Texas Hold'em**: Maximum bet/raise is the current pot size
- Player selects variant before game starts

### 3.2 Standard Rules (apply to both variants)
- Each player receives 2 hole cards
- 5 community cards dealt in stages: Flop (3) → Turn (1) → River (1)
- 4 betting rounds: Pre-Flop → Flop → Turn → River
- Best 5-card hand from any combination of hole + community cards wins
- Side pots handled when players go All-in with insufficient chips
- Dealer button rotates clockwise each hand

### 3.3 Hand Rankings (High to Low)
Royal Flush > Straight Flush > Four of a Kind > Full House > Flush > Straight > Three of a Kind > Two Pair > One Pair > High Card

### 3.4 Blinds
- **Fixed**: Small Blind and Big Blind remain constant throughout the game
- **Increasing**: Blinds increase every N hands (configurable interval and multiplier)
- Player selects mode before game starts

### 3.5 Game End
- Game ends immediately when any player loses all chips
- Player with the most chips at game end is the winner

---

## 4. System Architecture

### 4.1 High-Level Architecture
Modular monolithic backend with WebSocket-based real-time communication.

```
┌─────────────────────────────────────────────┐
│              FastAPI Server                  │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ HTTP API │ │WebSocket │ │ Static Files │ │
│  │  (REST)  │ │ Manager  │ │  (Frontend)  │ │
│  └────┬─────┘ └────┬─────┘ └─────────────┘ │
│       └──────┬─────┘                        │
│              ▼                               │
│  ┌───────────────────────────────────────┐  │
│  │          Game Engine                   │  │
│  │  Deck │ Dealer │ Betting │ Pot │ Eval │  │
│  └───────────────────────────────────────┘  │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ │
│  │ AI Manager │ │LLM Client│ │  Replay    │ │
│  │ (Rules+LLM)│ │(Adapter) │ │  Logger    │ │
│  └────────────┘ └──────────┘ └───────────┘ │
│  ┌──────────────────────────────────────┐  │
│  │         Config Store                  │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### 4.2 Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| **Game Engine** | State machine, deck/shuffle/deal, betting rounds, pot/side-pot calculation, hand evaluation, blinds management |
| **AI Manager** | Rule engine, personality profiles, LLM trigger decision, thinking delay, data isolation enforcement |
| **LLM Client** | Provider-agnostic interface, adapter implementations (Claude/OpenAI/Custom), prompt construction |
| **Replay Logger** | Full game state recording per hand, replay playback engine, statistics computation |
| **WebSocket Manager** | Real-time state broadcast, human action input, connection lifecycle |
| **Config Store** | Game settings, LLM config, personality templates |

---

## 5. Game Engine (Detailed)

### 5.1 State Machine
```
SETUP → PRE_FLOP → FLOP → TURN → RIVER → SHOWDOWN → HAND_END
  ↑                                                        │
  └────────── (no one busted) ←────────────────────────────┘
                              (someone busted) → GAME_OVER
```

### 5.2 Sub-modules

**Deck**
- 52-card standard deck
- Fisher-Yates shuffle
- Sequential dealing from top of deck

**Dealer**
- Manages dealer button position
- Blinds rotation (SB/BB assignment)
- Determines action order per betting round

**BettingRound**
- Validates actions: fold, check, call, bet, raise, all-in
- Enforces No-Limit and Pot-Limit rules
- Tracks current bet level, minimum raise, aggressor
- Handles split pots and side pots for partial all-ins

**PotCalculator**
- Main pot + N side pots based on all-in amounts
- Correct pot distribution at showdown

**HandEvaluator**
- Evaluates best 5-card hand from 7 cards (2 hole + 5 community)
- Compares hands for showdown ranking
- Handles ties (chopped pots)

**BlindsManager**
- Fixed mode: constant SB/BB values
- Increasing mode: SB/BB × multiplier every N hands
- Posts blinds automatically each hand

**GameController**
- Orchestrates full hand lifecycle
- Checks game-end condition after each hand
- Manages player elimination (if applicable)

---

## 6. AI Agent System

### 6.1 Decision Flow
```
1. Gather public information (community cards, pot, position, opponent action history)
        ↓
2. Rule Engine evaluation
   ├─ Pre-flop hand range assessment (position + personality adjusted)
   ├─ Pot odds calculation
   ├─ Implied odds estimation
   └─ Output: {action, amount, confidence}
        ↓
3. Should LLM enhance?
   ├─ YES: confidence < threshold OR large pot OR facing all-in OR late street key decision
   └─ NO:  return rule engine decision directly
        ↓
4. (If triggered) LLM analysis → parse structured response → merge/override decision
        ↓
5. Apply simulated thinking delay → return final decision
```

### 6.2 LLM Trigger Conditions
- Rule engine confidence below configurable threshold
- Pot size exceeds X% of player's remaining stack
- Facing an All-in decision (call or fold)
- Turn or River street with multi-way action

### 6.3 Personality Profiles

| Personality | Pre-flop Range | Aggression | Bluff Frequency | Description |
|-------------|---------------|------------|-----------------|-------------|
| **TAG** (Tight-Aggressive) | Top 15% | High | Medium-Low | Selective hands, plays aggressively |
| **LAG** (Loose-Aggressive) | Top 35% | Very High | High | Wide range, constant pressure |
| **Nit** (Tight-Passive) | Top 8% | Low | Very Low | Only premium hands, rarely bluffs |
| **Calling Station** (Loose-Passive) | Top 50% | Low | Low | Plays many hands, calls too much |

- Personalities stored as parameterized configuration files
- Assigned randomly or manually by human player before game start

### 6.4 Data Isolation (Mandatory)
Each AI agent may ONLY access public information:
- ✅ Community cards, pot size, all player chip stacks, opponent visible actions, position, current bet
- ❌ Other players' hole cards, other AI agents' internal state, other AI agents' LLM conversations, remaining deck cards

### 6.5 Decision Timing
- Rule engine decisions: random delay 2-5 seconds (configurable)
- LLM-enhanced decisions: natural API latency + optional extra delay
- "AI thinking..." status broadcast to frontend during delay

---

## 7. LLM Client

### 7.1 Interface (Provider-Agnostic)
```python
class LLMClient(ABC):
    async def decide(
        self,
        game_context: GameContext,      # public game state
        personality: PersonalityProfile, # agent personality
        hand_history: list[Action]      # current hand actions
    ) -> LLMDecision:                   # structured decision
        ...
```

### 7.2 Adapters
- **ClaudeAdapter**: Anthropic API (Claude Sonnet/Opus)
- **OpenAIAdapter**: OpenAI API (GPT-4o, etc.)
- **CustomAdapter**: Any OpenAI-compatible API endpoint

### 7.3 Configuration (`llm_config.yaml`)
```yaml
provider: anthropic          # anthropic | openai | custom
model: claude-sonnet-4-6
api_key: ${ANTHROPIC_API_KEY}
max_tokens: 500
temperature: 0.7
custom:
  base_url: null
  headers: {}
```

### 7.4 Prompt Structure
Each LLM call receives a structured prompt containing:
- Agent personality description
- Hole cards (private to this agent)
- Community cards (public)
- Pot size and current bet
- Position (SB/BB/UTG/MP/CO/BTN)
- Player's chip stack
- Complete action history for current hand
- Request for structured JSON output

---

## 8. Replay System

### 8.1 Recording
Per-hand recording of:
- Game configuration snapshot
- All player hole cards (revealed in replay)
- Community cards per street
- Every player action (player, action type, amount, timestamp)
- AI decision source tag (RULE / LLM)
- Pot changes
- Showdown result and winner

### 8.2 Storage Format
- One JSON file per game session
- Naming: `replays/YYYY-MM-DD_HH-MM-SS.json`

### 8.3 Playback Features
- Step through actions one at a time
- Jump to specific hand
- Show AI internal decisions post-game (rule vs LLM, confidence)
- Statistics panel: VPIP, PFR, AF (Aggression Factor) per player

---

## 9. WebSocket Communication

### 9.1 Message Protocol

**Server → Client:**
| Message | Payload | Description |
|---------|---------|-------------|
| `game_state` | Full game snapshot | Current table state for rendering |
| `your_turn` | Valid actions list | Human player's turn to act |
| `player_action` | {player, action, amount} | Notification of any player action |
| `ai_thinking` | {player_name} | AI is deliberating |
| `hand_result` | {winners, hands, pot_distribution} | Showdown results |
| `game_over` | {rankings, stats} | Final game results |

**Client → Server:**
| Message | Payload | Description |
|---------|---------|-------------|
| `player_action` | {action, amount?} | Human player decision |
| `get_replay` | {game_id} | Request replay data |
| `new_game` | {config} | Start new game with settings |

### 9.2 Connection Lifecycle
1. Client connects to WS endpoint
2. Game configuration submitted → game starts
3. State updates broadcast to all connected clients
4. Human player actions sent back via WS
5. Connection persists until game ends or client disconnects

---

## 10. Game Configuration & Flow

### 10.1 Pre-Game Setup (Human Player Configures)
| Setting | Options |
|---------|---------|
| Game Variant | No-Limit / Pot-Limit |
| AI Player Count | 2 ~ 8 |
| Starting Chips | Equal for all players (amount TBD by player) |
| Blinds Mode | Fixed / Increasing |
| Blind Amount | If fixed: SB/BB values; If increasing: initial + interval + multiplier |
| AI Personalities | Random assignment / Manual per-player selection |
| LLM Provider | Anthropic / OpenAI / Custom |

### 10.2 Full Game Flow
```
Browser opens → Settings panel displayed
     ↓
Player configures game → Clicks "Start"
     ↓
POST /api/game/start → Backend initializes:
  ├─ Create N+1 players (1 human + N AI)
  ├─ Assign personalities to AI agents
  ├─ Set initial chips and blinds
  └─ Start WebSocket connection
     ↓
Game Loop (per hand):
  ├─ Post blinds
  ├─ Deal hole cards
  ├─ Pre-Flop betting round
  ├─ Deal Flop → betting round
  ├─ Deal Turn → betting round
  ├─ Deal River → betting round
  ├─ Showdown → evaluate → distribute pot
  └─ Check game end condition
     ↓
Game Over → Display final rankings → Offer replay
```

---

## 11. Key Data Models

### 11.1 Card
```
{suit: "hearts"|"diamonds"|"clubs"|"spades", rank: "2".."A"}
```

### 11.2 Player
```
{
  id, name, is_human, chips, hole_cards: [Card]|null,
  position: "SB"|"BB"|"UTG"|"MP"|"CO"|"BTN",
  is_active, is_all_in, current_bet, total_bet_this_round,
  personality: PersonalityProfile|null
}
```

### 11.3 GameState
```
{
  phase: "setup"|"pre_flop"|"flop"|"turn"|"river"|"showdown"|"game_over",
  players: [Player],
  community_cards: [Card],
  pot, current_bet, dealer_index,
  action_history: [Action],
  hand_number, blinds: {small, big}
}
```

### 11.4 Action
```
{player_id, action: "fold"|"check"|"call"|"raise"|"all_in", amount, timestamp}
```

---

## 12. REST API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/game/start` | Initialize and start a new game |
| `GET` | `/api/game/{id}/state` | Get current game state |
| `GET` | `/api/replay/{id}` | Get replay data for a completed game |
| `GET` | `/api/replays` | List saved replays |
| `WS` | `/ws/{game_id}` | WebSocket connection for real-time play |

---

## 13. Project Structure (Proposed)

```
Texas_Poker/
├── server/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Configuration loading
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── deck.py             # Card, Deck classes
│   │   ├── dealer.py           # Dealer, position management
│   │   ├── game_controller.py  # State machine, orchestration
│   │   ├── betting.py          # Betting round logic
│   │   ├── pot.py              # Pot & side-pot calculation
│   │   └── evaluator.py        # Hand strength evaluation
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── manager.py          # AI decision orchestration
│   │   ├── rule_engine.py      # Rule-based poker logic
│   │   ├── personality.py      # Personality profiles
│   │   └── prompts.py          # LLM prompt templates
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py           # Abstract LLM client
│   │   ├── claude_adapter.py   # Anthropic adapter
│   │   ├── openai_adapter.py   # OpenAI adapter
│   │   └── custom_adapter.py   # Generic OpenAI-compatible
│   ├── replay/
│   │   ├── __init__.py
│   │   ├── logger.py           # Game state recorder
│   │   └── playback.py         # Replay engine
│   ├── ws/
│   │   ├── __init__.py
│   │   └── manager.py          # WebSocket connection manager
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic data models
├── frontend/
│   ├── index.html              # Main page
│   ├── css/
│   │   ├── tokens.css          # Shared design tokens
│   │   ├── base.css            # Global reset and accessibility styles
│   │   ├── setup.css           # Setup view
│   │   ├── game.css            # Table and action dock
│   │   └── results.css         # Results view
│   ├── js/
│   │   ├── app.js              # Application controller
│   │   ├── game/               # Table, actions, status, and log views
│   │   ├── services/           # HTTP, WebSocket, and sound services
│   │   ├── state/              # Store, preferences, and state helpers
│   │   └── setup.js            # Pre-game setup UI
│   └── assets/
│       └── cards/              # Card images (SVG or PNG)
├── config/
│   ├── llm_config.yaml         # LLM provider settings
│   └── personalities.yaml      # AI personality profiles
├── replays/                    # Saved game replays (JSON)
├── spec.md                     # This document
└── Requirement.md              # Original requirements
```

---

## 14. UI Design (Phase 2)

### 14.1 Design Style
- **Classic top-down poker table** — oval table bird's-eye view, players seated around, community cards in center
- Dark theme with green felt table, gold accents, simulating real casino atmosphere
- Three main views: Setup → Game Table → Results/Replay

### 14.2 Page Layout (Game Table View)

```
┌─────────────────────────────────────────────────────────┐
│  Top Bar: Game Title | Hand # | Blinds | Mode          │
├──────────┬───────────────────────────────┬──────────────┤
│ Left     │      Poker Table (Oval)       │ Right        │
│ Sidebar  │  ┌─────────────────────┐     │ Sidebar       │
│          │  │  P3    P4    P5     │     │              │
│ • Hand   │  │                     │     │ • Action     │
│   Info   │  │   🂧 🂺 🂲 🂭 🂮   │     │   History    │
│ • Your   │  │                     │     │              │
│   Cards  │  │  P2    P1    You    │     │ • Log        │
│ • Position│ │                     │     │              │
│ • Chips  │  │     Pot: 350       │     │              │
│          │  └─────────────────────┘     │              │
├──────────┴───────────────────────────────┴──────────────┤
│  Bottom Action Bar: Fold | Check | Call | [Raise] | All-in │
└─────────────────────────────────────────────────────────┘
```

### 14.3 Three Core Views

**① Setup View**
- Two-column form layout
- Left column: Game Mode (toggle), AI Player Count (± stepper), Starting Chips (input), Blinds Mode (toggle)
- Right column: SB/BB values (inputs), AI Personality (random/manual toggle), LLM Provider (dropdown), API Key (password input)
- Prominent "Start Game" button (gold gradient)

**② Game Table View**
- **Top Bar**: Game title, current hand number, blind levels, game variant
- **Left Sidebar**: Player's hole cards (large display), position label, current chip stack, pot size, current bet info
- **Center (Oval Table)**:
  - Green felt oval with brown rail border
  - Players positioned around the oval with name, chip count, avatar/icon
  - Human player highlighted in gold
  - Community cards displayed face-up in center
  - Dealer button (D) marker rotated per hand
  - Pot amount displayed below community cards
  - AI "thinking" indicator shown when AI deliberates
- **Right Sidebar**: Action history log (scrollable), player actions with color coding
- **Bottom Action Bar**: Fold (red), Check (green), Call (blue), Raise input + button (orange), All-in (purple)
  - Invalid actions auto-grayed out
  - Raise shows slider/input for amount selection

**③ Game Over / Replay View**
- Trophy icon and "Game Over" title with total hands played
- **Ranking List**: Medal icons for top 3, busted player in red highlight
- **Stats Panel**: VPIP, PFR, Win Rate, Aggression Factor for human player
- **Replay Panel**: Total hands recorded, playback entry
- Action buttons: "Play Again" (primary) and "View Replay" (secondary)

### 14.4 UI States & Transitions
- Smooth view transitions between Setup → Game → Results
- AI player actions animate around the table
- Cards dealt with subtle animation (future enhancement)
- Chip stacks update with count changes
- Winning hand highlighted at showdown

### 14.5 Color Palette

| Element | Color |
|---------|-------|
| Background | `#1a1a2e` (Dark navy) |
| Table Felt | Green radial gradient (`#1b6e3a` → `#0d4a1e`) |
| Table Rail | `#5d3a1a` (Brown wood) |
| Accent / Gold | `#ffd740` (Amber gold) |
| Human Player | Gold border highlight |
| Fold Button | `#b71c1c` (Red) |
| Check Button | `#1b5e20` (Green) |
| Call Button | `#0d47a1` (Blue) |
| Raise Button | `#e65100` (Orange) |
| All-in Button | `#4a148c` (Purple) |
| Text Primary | `#e2e2e2` / White |
| Text Secondary | `#888888` |

---

## 15. Out of Scope

- User authentication / multi-user support
- Real-money betting
- Networked multiplayer (multiple human players)
- Mobile native app
- Advanced AI training / reinforcement learning
- Sound effects (future enhancement)
- Card deal animations (future enhancement)

---

## 16. Open Questions / Future Decisions

- Exact threshold values for LLM trigger conditions (tune during development)
- Specific LLM model choice per provider
- Card visual implementation (CSS-drawn vs SVG vs PNG sprite)

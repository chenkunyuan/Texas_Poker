"""
FastAPI Application Entry-Point for Texas Hold'em Poker.

Starts the web server, manages active games, wires together the
GameController, AIManager, ReplayLogger, and WebSocket manager.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from server.config import load_llm_config, load_personalities
from server.engine.game_controller import GameController
from server.ai.manager import AIManager
from server.llm.client import LLMClientFactory
from server.models.schemas import GameConfig, GameState
from server.replay.logger import ReplayLogger
from server.replay.playback import ReplayPlayback
from server.ws.manager import WSManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="Texas Hold'em Poker", version="0.1.0")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

# Single WebSocket manager shared across all games
ws_manager = WSManager()

# Active game controllers, keyed by game_id
_active_games: dict[str, GameController] = {}

# Active replay loggers, keyed by game_id
_active_replays: dict[str, ReplayLogger] = {}

# Project root for serving frontend files
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"

# ---------------------------------------------------------------------------
# Static file serving
# ---------------------------------------------------------------------------

# Mount the frontend directory at /static so JS/CSS files are accessible.
if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# API — Game
# ---------------------------------------------------------------------------


@app.post("/api/game/start")
async def start_game(config: GameConfig) -> JSONResponse:
    """Create and start a new Texas Hold'em game.

    Accepts a :class:`GameConfig` payload, initialises all subsystems,
    and launches the game loop as a background task.  The client should
    then connect via WebSocket at ``/ws/{game_id}``.

    Request body::
        {
          "variant": "no_limit",
          "ai_player_count": 5,
          "starting_chips": 1000,
          "blinds": { "mode": "fixed", "small": 5, "big": 10 },
          "personality_mode": "random"
        }

    Response::
        { "game_id": "abc123", "message": "Game started" }
    """
    game_id = uuid.uuid4().hex[:12]

    # ---- 1. Create GameController ------------------------------------------
    controller = GameController(config=config, game_id=game_id)

    # ---- 2. Create AIManager with LLM client --------------------------------
    llm_client = LLMClientFactory.create()
    ai_manager = AIManager(llm_client=llm_client)

    # ---- 3. Register AI personalities ---------------------------------------
    controller.init_players()

    for player in controller.state.players:
        if player.is_human:
            continue
        ai_manager.register_player(player.id, player.personality)

    # ---- 4. Create ReplayLogger ----------------------------------------------
    replay = ReplayLogger(game_id)

    # Store game config + player info for the replay header
    replay.set_game_info(
        config=config.model_dump() if hasattr(config, "model_dump") else {},
        players=replay._serialize_players(controller.state),
    )

    # ---- 5. Wire controller._get_ai_action -> AI manager --------------------
    _wire_ai_manager(controller, ai_manager, replay)

    # ---- 6. Wire event callbacks -> WS broadcast + replay logging -----------
    _wire_callbacks(controller, game_id, replay)

    # ---- 7. Track active instances ------------------------------------------
    _active_games[game_id] = controller
    _active_replays[game_id] = replay

    # ---- 8. Launch game loop as background task -----------------------------
    asyncio.create_task(_run_game(controller, game_id, replay))

    logger.info("Game '%s' started with %d players.", game_id, len(controller.state.players))

    return JSONResponse(
        content={"game_id": game_id, "message": "Game started"},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# API — Replays
# ---------------------------------------------------------------------------


@app.get("/api/replays")
async def list_replays() -> JSONResponse:
    """List all saved replay files.

    Returns an array of replay summaries sorted newest-first.
    """
    replays = ReplayPlayback.list_replays()
    return JSONResponse(content=replays)


@app.get("/api/replay/{replay_id}")
async def get_replay(replay_id: str) -> JSONResponse:
    """Load a specific replay by its ID (filename without ``.json``).

    Returns the full replay data including config, players, and hands.
    """
    filepath = str(_PROJECT_ROOT / "replays" / f"{replay_id}.json")
    try:
        data = ReplayPlayback.load(filepath)
        return JSONResponse(content=data)
    except FileNotFoundError:
        return JSONResponse(
            content={"error": "Replay not found"}, status_code=404
        )
    except Exception:
        return JSONResponse(
            content={"error": "Failed to load replay"}, status_code=500
        )


# ---------------------------------------------------------------------------
# WebSocket — Human player connection
# ---------------------------------------------------------------------------


@app.websocket("/ws/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
    """WebSocket endpoint for the human player to join a game.

    After connecting, the client receives full game-state broadcasts and
    ``your_turn`` messages.  The client sends ``player_action`` messages
    when it is their turn to act.

    Message format (client -> server)::
        { "type": "player_action", "action": "CALL", "amount": 0 }
    """
    controller = _active_games.get(game_id)

    await ws_manager.connect(game_id, websocket, is_human=True)

    # If the game exists and hasn't started yet, send initial state.
    if controller is not None:
        # Send initial game state so the client can render the table.
        state_dict = _serialize_state(controller.state)
        await websocket.send_json({"type": "game_state", "state": state_dict})

    try:
        while True:
            message = await ws_manager.receive_message(game_id, websocket)
            if message is None:
                continue

            msg_type = message.get("type", "")

            if msg_type == "player_action":
                action = message.get("action", "FOLD")
                amount = message.get("amount", 0)

                if controller is not None:
                    controller.submit_human_action(action, amount)
                else:
                    logger.warning(
                        "Received player_action for unknown game '%s'.", game_id
                    )

            elif msg_type == "new_game":
                # Client can also request a new game config via WS
                pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for game '%s'.", game_id)
    except Exception:
        logger.exception("Unexpected error in WS handler for game '%s'.", game_id)
    finally:
        ws_manager.disconnect(game_id, websocket)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------


@app.get("/")
async def serve_frontend() -> HTMLResponse:
    """Serve the frontend index page."""
    index_path = _FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return HTMLResponse(
            content=_FALLBACK_INDEX_HTML,
            status_code=200,
        )


# =========================================================================
# Wiring helpers
# =========================================================================


def _wire_ai_manager(
    controller: GameController,
    ai_manager: AIManager,
    replay: ReplayLogger,
) -> None:
    """Replace ``controller._get_ai_action`` with a wrapper that delegates
    to :class:`AIManager.get_decision`.

    The original method is stored so it can be used as a fallback on error.
    """
    _original_get_ai_action = controller._get_ai_action

    async def _ai_action_wrapper(player, betting):
        """Bridge between GameController and AIManager.

        * Emits ``ai_thinking`` to the frontend.
        * Delegates to :class:`AIManager.get_decision`.
        * Stores the decision source on the controller for replay logging.
        * Falls back to the original (random) AI on error.
        """
        # Emit thinking notification
        await controller._emit("ai_thinking", {
            "player_id": player.id,
            "player_name": player.name,
        })

        try:
            valid_actions = betting.get_valid_actions(player)
            action, amount, source = await ai_manager.get_decision(
                state=controller.state,
                player=player,
                valid_actions=valid_actions,
            )
            # Store source so the replay-logging callback can access it
            controller._last_ai_source = source
            return action, amount
        except Exception:
            logger.exception(
                "AI manager failed for player %s; falling back to random AI.",
                player.id,
            )
            return await _original_get_ai_action(player, betting)

    controller._get_ai_action = _ai_action_wrapper  # type: ignore[method-assign]
    controller._last_ai_source = "RULE"  # initial attribute


def _wire_callbacks(
    controller: GameController,
    game_id: str,
    replay: ReplayLogger,
) -> None:
    """Register event callbacks on the controller.

    Each event maps to one or both of:
    * WebSocket broadcast / human-targeted message.
    * Replay log recording.
    """

    # Track the last seen phase to detect hand-start transitions
    _last_phase: list[str] = ["SETUP"]

    async def on_game_state(data: GameState) -> None:
        nonlocal _last_phase
        current_phase = data.phase.value if hasattr(data.phase, "value") else str(data.phase)

        # Detect new hand: transition from HAND_END / SETUP / GAME_OVER into PRE_FLOP
        if current_phase == "PRE_FLOP" and _last_phase[0] not in ("PRE_FLOP", "FLOP", "TURN", "RIVER"):
            replay.start_hand(data)

        _last_phase[0] = current_phase

        state_dict = _serialize_state(data)
        await ws_manager.broadcast(game_id, {"type": "game_state", "state": state_dict})

    async def on_your_turn(data: dict) -> None:
        await ws_manager.send_to_human(game_id, {"type": "your_turn", **data})

    async def on_player_action(data: dict) -> None:
        # Source tracking: check controller._last_ai_source for AI players
        source = getattr(controller, "_last_ai_source", "RULE")
        replay.record_action(
            player_id=data.get("player_id", ""),
            action=data.get("action", ""),
            amount=data.get("amount", 0),
            source=source if data.get("player_id", "") != "human" else "HUMAN",
        )
        # Reset after consumption
        controller._last_ai_source = "RULE"

        await ws_manager.broadcast(game_id, {"type": "player_action", **data})

    async def on_ai_thinking(data: dict) -> None:
        await ws_manager.broadcast(game_id, {"type": "ai_thinking", **data})

    async def on_community_updated(data: list) -> None:
        # data is a list of Card objects
        replay.record_community(data)

    async def on_hand_result(data: dict) -> None:
        # data is {"winners": [...], "hands": {...}, "pot_distribution": [...]}
        replay.end_hand(controller.state, data)
        await ws_manager.broadcast(game_id, {"type": "hand_result", **data})

    async def on_game_over(data: dict) -> None:
        # Save replay on game over
        filepath = replay.save()
        data["replay_id"] = Path(filepath).stem
        await ws_manager.broadcast(game_id, {"type": "game_over", **data})

    # Register all callbacks
    controller.on("game_state", on_game_state)
    controller.on("your_turn", on_your_turn)
    controller.on("player_action", on_player_action)
    controller.on("ai_thinking", on_ai_thinking)
    controller.on("community_updated", on_community_updated)
    controller.on("hand_result", on_hand_result)
    controller.on("game_over", on_game_over)


# =========================================================================
# Background game runner
# =========================================================================


async def _run_game(
    controller: GameController,
    game_id: str,
    replay: ReplayLogger,
) -> None:
    """Run a game to completion and clean up afterwards.

    Wrapped in try/except so a single game crash doesn't bring down the
    server, and stale resources are always removed.
    """
    try:
        await controller.run()
    except Exception:
        logger.exception("Game '%s' crashed.", game_id)
    finally:
        # Cleanup: remove from active games after a short delay so the
        # frontend can pick up the final game_over message.
        await asyncio.sleep(2)
        _active_games.pop(game_id, None)
        _active_replays.pop(game_id, None)
        logger.info("Game '%s' cleaned up.", game_id)


# =========================================================================
# Helpers
# =========================================================================


def _serialize_state(state: GameState) -> dict:
    """Serialize a :class:`GameState` to a JSON-safe dict.

    Uses Pydantic's ``model_dump`` if available, with custom handling for
    enums and other non-serialisable types as a fallback.
    """
    if hasattr(state, "model_dump"):
        return state.model_dump()

    # Manual fallback serialisation
    result: dict[str, Any] = {
        "phase": state.phase.value if hasattr(state.phase, "value") else str(state.phase),
        "players": [],
        "community_cards": [],
        "pot": state.pot,
        "current_bet": state.current_bet,
        "dealer_index": state.dealer_index,
        "hand_number": state.hand_number,
    }

    for p in state.players:
        result["players"].append({
            "id": p.id,
            "name": p.name,
            "is_human": p.is_human,
            "chips": p.chips,
            "hole_cards": [c.to_dict() for c in p.hole_cards] if p.hole_cards else [],
            "position": p.position.value if p.position else None,
            "is_active": p.is_active,
            "is_all_in": p.is_all_in,
            "current_bet": p.current_bet,
            "total_bet_this_round": p.total_bet_this_round,
        })

    for c in state.community_cards:
        result["community_cards"].append(c.to_dict())

    if state.blinds:
        if hasattr(state.blinds, "model_dump"):
            result["blinds"] = state.blinds.model_dump()
        else:
            result["blinds"] = {
                "small": getattr(state.blinds, "small", 0),
                "big": getattr(state.blinds, "big", 0),
            }

    return result


# ---------------------------------------------------------------------------
# Fallback index.html (shown when frontend/index.html doesn't exist yet)
# ---------------------------------------------------------------------------

_FALLBACK_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Texas Hold'em Poker</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div id="app">
        <h1>Texas Hold'em Poker</h1>
        <p>Loading...</p>
    </div>
    <script src="/static/js/app.js" type="module"></script>
</body>
</html>
"""

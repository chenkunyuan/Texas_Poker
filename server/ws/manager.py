"""
WebSocket Connection Manager for Texas Hold'em Poker.

Manages WebSocket connections per game, routes messages between the server
and connected clients (browser UI), and tracks human-player sockets
separately for targeted delivery.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """Manages WebSocket connections grouped by game ID.

    Each game can have multiple spectators, but only one human player.
    The human WebSocket is tracked separately so the server can send
    turn-specific messages (valid actions, prompts) directly to that
    connection without broadcasting to spectators.

    Usage::

        manager = WSManager()
        await manager.connect(game_id, websocket, is_human=True)
        await manager.broadcast(game_id, {"type": "game_state", ...})
        await manager.send_to_human(game_id, {"type": "your_turn", ...})
        msg = await manager.receive_message(game_id, websocket)
        manager.disconnect(game_id, websocket)
    """

    def __init__(self) -> None:
        # game_id -> list of connected WebSocket instances
        self.connections: dict[str, list[WebSocket]] = {}
        # game_id -> the single human player's WebSocket (if connected)
        self.human_ws: dict[str, WebSocket] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        game_id: str,
        websocket: WebSocket,
        is_human: bool = False,
    ) -> None:
        """Accept a new WebSocket connection for *game_id*.

        Args:
            game_id: The game to join.
            websocket: The connected WebSocket instance.
            is_human: If ``True``, this socket is registered as the human
                player for *game_id* (replacing any previous registration).
        """
        await websocket.accept()

        previous_human = self.human_ws.get(game_id) if is_human else None
        if previous_human is not None and previous_human is not websocket:
            self.disconnect(game_id, previous_human)

        if game_id not in self.connections:
            self.connections[game_id] = []
        if websocket not in self.connections[game_id]:
            self.connections[game_id].append(websocket)

        if is_human:
            self.human_ws[game_id] = websocket

        if previous_human is not None and previous_human is not websocket:
            try:
                await previous_human.close(code=1000)
            except Exception:
                logger.debug(
                    "Failed to close replaced human WebSocket for game '%s'.",
                    game_id,
                )

        logger.info(
            "WebSocket connected to game '%s' (human=%s, total=%d)",
            game_id,
            is_human,
            len(self.connections.get(game_id, [])),
        )

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        """Remove *websocket* from *game_id* and clean up empty structures.

        Safe to call even if *game_id* or *websocket* is not tracked.
        """
        conns = self.connections.get(game_id)
        if conns and websocket in conns:
            conns.remove(websocket)

        # If this was the human socket, clear it
        human = self.human_ws.get(game_id)
        if human is websocket:
            del self.human_ws[game_id]

        # Prune empty lists
        if conns is not None and len(conns) == 0:
            del self.connections[game_id]

        logger.debug(
            "WebSocket disconnected from game '%s' (remaining=%d)",
            game_id,
            len(conns) if conns else 0,
        )

    def is_connected(self, game_id: str, websocket: WebSocket) -> bool:
        """Return whether *websocket* is still registered for *game_id*."""
        return websocket in self.connections.get(game_id, [])

    def is_current_human(self, game_id: str, websocket: WebSocket) -> bool:
        """Return whether *websocket* owns the human seat for *game_id*."""
        return self.human_ws.get(game_id) is websocket

    # ------------------------------------------------------------------
    # Message delivery
    # ------------------------------------------------------------------

    async def broadcast(self, game_id: str, message: dict) -> None:
        """Send a JSON message to **every** WebSocket connected to *game_id*.

        Disconnected / errored sockets are silently removed during iteration.
        """
        conns = self.connections.get(game_id)
        if not conns:
            return

        payload = json.dumps(message)
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(payload)
            except Exception:
                logger.debug(
                    "Failed to send to WebSocket in game '%s'; marking for removal.",
                    game_id,
                )
                dead.append(ws)

        for ws in dead:
            self.disconnect(game_id, ws)

    async def send_to_human(self, game_id: str, message: dict) -> None:
        """Send a JSON message **only** to the human player's WebSocket.

        Does nothing if no human is connected for *game_id*.
        """
        ws = self.human_ws.get(game_id)
        if ws is None:
            return

        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            logger.debug(
                "Failed to send to human WebSocket in game '%s'; removing.",
                game_id,
            )
            self.disconnect(game_id, ws)

    # ------------------------------------------------------------------
    # Message reception
    # ------------------------------------------------------------------

    async def receive_message(
        self, game_id: str, websocket: WebSocket
    ) -> Optional[dict]:
        """Receive a single JSON message from *websocket*.

        Returns:
            A parsed ``dict``, or ``None`` if the client disconnected or
            sent invalid JSON.
        """
        try:
            raw = await websocket.receive_text()
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Invalid JSON received from WebSocket in game '%s'.", game_id
            )
            return None
        except Exception:
            logger.debug(
                "WebSocket disconnected while receiving in game '%s'.", game_id
            )
            self.disconnect(game_id, websocket)
            return None

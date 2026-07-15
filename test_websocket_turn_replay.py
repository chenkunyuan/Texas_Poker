"""Regression tests for replaying an outstanding human turn on reconnect."""

import asyncio
import json
from unittest.mock import patch

from fastapi import WebSocketDisconnect

import server.main as server_main
from server.engine.game_controller import GameController
from server.models.schemas import GameConfig, Player, PlayerAction
from server.ws.manager import WSManager


class StubBettingRound:
    """Expose a small, deterministic human action set."""

    def get_valid_actions(self, player):
        return {
            "CHECK": {"action": PlayerAction.CHECK, "amount": 0},
            "RAISE": {"action": PlayerAction.RAISE, "min": 10, "max": 100},
        }


class DisconnectingManager:
    async def connect(self, game_id, websocket, is_human=False):
        await websocket.accept()

    async def receive_message(self, game_id, websocket):
        raise WebSocketDisconnect()

    def disconnect(self, game_id, websocket):
        return None


class RecordingWebSocket:
    def __init__(self):
        self.messages = []

    async def accept(self):
        return None

    async def send_json(self, message):
        self.messages.append(message)


class BlockingReplayWebSocket(RecordingWebSocket):
    def __init__(self):
        super().__init__()
        self.replay_started = asyncio.Event()
        self.release_replay = asyncio.Event()

    async def send_json(self, message):
        self.messages.append(message)
        if message["type"] == "your_turn":
            self.replay_started.set()
            await self.release_replay.wait()


class ScriptedWebSocket(RecordingWebSocket):
    def __init__(self, fail_on_type=None, fail_close=False):
        super().__init__()
        self.accepted = asyncio.Event()
        self.incoming = asyncio.Queue()
        self.closed = False
        self.fail_on_type = fail_on_type
        self.fail_close = fail_close

    async def accept(self):
        self.accepted.set()

    async def close(self, code=1000):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("failed to close socket")

    async def send_json(self, message):
        if message["type"] == self.fail_on_type:
            raise RuntimeError(f"failed to send {message['type']}")
        self.messages.append(message)

    async def receive_text(self):
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item


class SpyController:
    def __init__(self):
        self.state = make_controller().state
        self.actions = []

    async def replay_pending_human_turn(self, send, send_timeout=5.0):
        return False

    async def submit_human_action(self, action, amount=0):
        self.actions.append((action, amount))


def make_controller(game_id="test-game"):
    return GameController(GameConfig(ai_player_count=1), game_id)


def test_pending_human_turn_is_snapshot_and_clears_on_submit():
    async def scenario():
        controller = make_controller()
        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)

        pending = controller.pending_human_turn
        assert pending == {
            "valid_actions": {
                "CHECK": {"action": "CHECK", "amount": 0},
                "RAISE": {"action": "RAISE", "min": 10, "max": 100},
            },
            "min_raise": 10,
            "max_raise": 100,
            "call_amount": 0,
        }

        pending["valid_actions"]["CHECK"]["amount"] = 999
        assert controller.pending_human_turn["valid_actions"]["CHECK"]["amount"] == 0

        await controller.submit_human_action("CHECK")
        assert controller.pending_human_turn is None
        assert await asyncio.wait_for(action_task, timeout=1) == (
            PlayerAction.CHECK,
            0,
        )

    asyncio.run(scenario())


def test_only_first_action_is_accepted_for_pending_human_turn():
    async def scenario():
        controller = make_controller()

        assert await controller.submit_human_action("FOLD") is False
        assert controller._human_action is None
        assert not controller._human_action_event.is_set()

        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)

        first = await controller.submit_human_action("RAISE", 50)
        second = await controller.submit_human_action("FOLD")

        assert first is True
        assert second is False
        assert controller._human_action == {"action": "RAISE", "amount": 50}
        assert await asyncio.wait_for(action_task, timeout=1) == (
            PlayerAction.RAISE,
            50,
        )

    asyncio.run(scenario())


def test_immediate_human_response_during_turn_emit_is_not_lost():
    async def scenario():
        controller = make_controller()
        player = Player(id="human", name="You", is_human=True, chips=1000)

        async def on_your_turn(data):
            await controller.submit_human_action("CHECK")

        controller.on("your_turn", on_your_turn)
        result = await asyncio.wait_for(
            controller._get_human_action(StubBettingRound(), player), timeout=1
        )

        assert result == (PlayerAction.CHECK, 0)
        assert controller.pending_human_turn is None

    asyncio.run(scenario())


def test_failed_turn_delivery_does_not_leave_pending_replay():
    async def scenario():
        controller = make_controller()
        player = Player(id="human", name="You", is_human=True, chips=1000)

        async def on_your_turn(data):
            raise RuntimeError("delivery failed")

        controller.on("your_turn", on_your_turn)

        try:
            await controller._get_human_action(StubBettingRound(), player)
        except RuntimeError as error:
            assert str(error) == "delivery failed"
        else:
            raise AssertionError("turn delivery failure should propagate")

        assert controller.pending_human_turn is None

    asyncio.run(scenario())


def test_websocket_attach_sends_state_then_pending_turn():
    async def scenario():
        controller = make_controller()
        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)

        websocket = RecordingWebSocket()

        with (
            patch.object(server_main, "ws_manager", DisconnectingManager()),
            patch.object(
                server_main, "_active_games", {controller.game_id: controller}
            ),
        ):
            await server_main.websocket_endpoint(websocket, controller.game_id)

        assert [message["type"] for message in websocket.messages] == [
            "game_state",
            "your_turn",
        ]
        assert websocket.messages[1] == {
            "type": "your_turn",
            **controller.pending_human_turn,
        }

        await controller.submit_human_action("CHECK")
        await asyncio.wait_for(action_task, timeout=1)

    asyncio.run(scenario())


def test_websocket_does_not_replay_absent_or_consumed_turn():
    async def connect(controller):
        websocket = RecordingWebSocket()
        await server_main.websocket_endpoint(websocket, controller.game_id)
        return websocket.messages

    async def scenario():
        controller = make_controller()
        with (
            patch.object(server_main, "ws_manager", DisconnectingManager()),
            patch.object(
                server_main, "_active_games", {controller.game_id: controller}
            ),
        ):
            assert [message["type"] for message in await connect(controller)] == [
                "game_state"
            ]

        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)
        await controller.submit_human_action("CHECK")
        await asyncio.wait_for(action_task, timeout=1)

        with (
            patch.object(server_main, "ws_manager", DisconnectingManager()),
            patch.object(
                server_main, "_active_games", {controller.game_id: controller}
            ),
        ):
            assert [message["type"] for message in await connect(controller)] == [
                "game_state"
            ]

    asyncio.run(scenario())


def test_submit_waits_for_in_flight_pending_turn_replay():
    async def scenario():
        controller = make_controller()
        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)

        websocket = BlockingReplayWebSocket()
        with (
            patch.object(server_main, "ws_manager", DisconnectingManager()),
            patch.object(
                server_main, "_active_games", {controller.game_id: controller}
            ),
        ):
            endpoint_task = asyncio.create_task(
                server_main.websocket_endpoint(websocket, controller.game_id)
            )
            await asyncio.wait_for(websocket.replay_started.wait(), timeout=1)

            submit_task = asyncio.create_task(
                controller.submit_human_action("CHECK")
            )
            await asyncio.sleep(0)
            assert not submit_task.done()
            assert controller.pending_human_turn is not None

            websocket.release_replay.set()
            await asyncio.wait_for(endpoint_task, timeout=1)
            await asyncio.wait_for(submit_task, timeout=1)

        assert controller.pending_human_turn is None
        assert [message["type"] for message in websocket.messages] == [
            "game_state",
            "your_turn",
        ]
        assert await asyncio.wait_for(action_task, timeout=1) == (
            PlayerAction.CHECK,
            0,
        )

    asyncio.run(scenario())


def test_replaced_human_socket_cannot_submit_action():
    async def scenario():
        manager = WSManager()
        controller = SpyController()
        old_socket = ScriptedWebSocket()
        new_socket = ScriptedWebSocket()

        with (
            patch.object(server_main, "ws_manager", manager),
            patch.object(server_main, "_active_games", {"game": controller}),
        ):
            old_task = asyncio.create_task(
                server_main.websocket_endpoint(old_socket, "game")
            )
            await asyncio.wait_for(old_socket.accepted.wait(), timeout=1)

            new_task = asyncio.create_task(
                server_main.websocket_endpoint(new_socket, "game")
            )
            await asyncio.wait_for(new_socket.accepted.wait(), timeout=1)
            assert old_socket.closed
            assert manager.is_current_human("game", new_socket)

            await old_socket.incoming.put(json.dumps({
                "type": "player_action", "action": "RAISE", "amount": 90,
            }))
            await old_socket.incoming.put(RuntimeError("old disconnected"))
            await asyncio.wait_for(old_task, timeout=1)
            assert controller.actions == []

            await new_socket.incoming.put(json.dumps({
                "type": "player_action", "action": "CHECK", "amount": 0,
            }))
            await new_socket.incoming.put(RuntimeError("new disconnected"))
            await asyncio.wait_for(new_task, timeout=1)
            assert controller.actions == [("CHECK", 0)]

    asyncio.run(scenario())


def test_replacement_survives_old_socket_close_failure():
    async def scenario():
        manager = WSManager()
        old_socket = ScriptedWebSocket(fail_close=True)
        new_socket = ScriptedWebSocket()

        await manager.connect("game", old_socket, is_human=True)
        await manager.connect("game", new_socket, is_human=True)

        assert old_socket.closed
        assert not manager.is_connected("game", old_socket)
        assert manager.is_connected("game", new_socket)
        assert manager.is_current_human("game", new_socket)

    asyncio.run(scenario())


def test_initial_state_send_failure_disconnects_socket():
    async def scenario():
        manager = WSManager()
        controller = SpyController()
        websocket = ScriptedWebSocket(fail_on_type="game_state")

        with (
            patch.object(server_main, "ws_manager", manager),
            patch.object(server_main, "_active_games", {"game": controller}),
        ):
            await server_main.websocket_endpoint(websocket, "game")

        assert not manager.is_connected("game", websocket)
        assert not manager.is_current_human("game", websocket)

    asyncio.run(scenario())


def test_pending_replay_send_failure_disconnects_socket():
    async def scenario():
        manager = WSManager()
        controller = make_controller("game")
        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)
        websocket = ScriptedWebSocket(fail_on_type="your_turn")

        with (
            patch.object(server_main, "ws_manager", manager),
            patch.object(server_main, "_active_games", {"game": controller}),
        ):
            await server_main.websocket_endpoint(websocket, "game")

        assert not manager.is_connected("game", websocket)
        assert controller.pending_human_turn is not None
        await controller.submit_human_action("CHECK")
        await asyncio.wait_for(action_task, timeout=1)

    asyncio.run(scenario())


def test_pending_replay_timeout_releases_lock_and_preserves_turn():
    async def scenario():
        controller = make_controller()
        player = Player(id="human", name="You", is_human=True, chips=1000)
        emitted = asyncio.Event()
        send_cancelled = asyncio.Event()

        async def on_your_turn(data):
            emitted.set()

        async def blocked_send(data):
            try:
                await asyncio.Event().wait()
            finally:
                send_cancelled.set()

        controller.on("your_turn", on_your_turn)
        action_task = asyncio.create_task(
            controller._get_human_action(StubBettingRound(), player)
        )
        await asyncio.wait_for(emitted.wait(), timeout=1)

        try:
            await controller.replay_pending_human_turn(
                blocked_send, send_timeout=0.01
            )
        except TimeoutError:
            pass
        else:
            raise AssertionError("blocked replay should time out")

        assert send_cancelled.is_set()
        assert controller.pending_human_turn is not None
        await asyncio.wait_for(controller.submit_human_action("CHECK"), timeout=1)
        await asyncio.wait_for(action_task, timeout=1)
        assert controller.pending_human_turn is None

    asyncio.run(scenario())


if __name__ == "__main__":
    test_pending_human_turn_is_snapshot_and_clears_on_submit()
    test_only_first_action_is_accepted_for_pending_human_turn()
    test_immediate_human_response_during_turn_emit_is_not_lost()
    test_failed_turn_delivery_does_not_leave_pending_replay()
    test_websocket_attach_sends_state_then_pending_turn()
    test_websocket_does_not_replay_absent_or_consumed_turn()
    test_submit_waits_for_in_flight_pending_turn_replay()
    test_replaced_human_socket_cannot_submit_action()
    test_replacement_survives_old_socket_close_failure()
    test_initial_state_send_failure_disconnects_socket()
    test_pending_replay_send_failure_disconnects_socket()
    test_pending_replay_timeout_releases_lock_and_preserves_turn()
    print("All WebSocket turn replay tests passed!")

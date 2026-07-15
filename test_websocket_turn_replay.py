"""Regression tests for replaying an outstanding human turn on reconnect."""

import asyncio
from unittest.mock import patch

from fastapi import WebSocketDisconnect

import server.main as server_main
from server.engine.game_controller import GameController
from server.models.schemas import GameConfig, Player, PlayerAction


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


if __name__ == "__main__":
    test_pending_human_turn_is_snapshot_and_clears_on_submit()
    test_immediate_human_response_during_turn_emit_is_not_lost()
    test_failed_turn_delivery_does_not_leave_pending_replay()
    test_websocket_attach_sends_state_then_pending_turn()
    test_websocket_does_not_replay_absent_or_consumed_turn()
    test_submit_waits_for_in_flight_pending_turn_replay()
    print("All WebSocket turn replay tests passed!")

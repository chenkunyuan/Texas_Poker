import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from server.ai.manager import AIManager
from server.ai.prompts import build_poker_prompt
from server.models.schemas import GameState, Player, PlayerAction


class AIManagerLLMTests(unittest.IsolatedAsyncioTestCase):
    def _manager(self, client):
        manager = AIManager(llm_client=client)
        manager._apply_thinking_delay = AsyncMock()
        manager._trigger_config = {"confidence_threshold": 1.0}
        engine = MagicMock()
        engine.decide.return_value = (PlayerAction.CALL, 10, 0.1)
        manager.engines["ai-1"] = engine
        return manager

    async def test_llm_failure_preserves_rule_result(self):
        client = MagicMock()
        client.decide = AsyncMock(side_effect=RuntimeError("unavailable"))
        manager = self._manager(client)
        state = GameState(players=[Player(id="ai-1", name="AI", chips=100)])
        player = state.players[0]
        valid = {"CALL": {"action": PlayerAction.CALL, "amount": 10}}

        with patch("server.ai.manager.RuleEngine.should_use_llm", return_value=True):
            result = await manager.get_decision(state, player, valid)

        self.assertEqual(result, (PlayerAction.CALL, 10, "RULE"))

    async def test_prompt_contains_only_acting_players_cards(self):
        client = MagicMock()
        client.decide = AsyncMock(side_effect=RuntimeError("stop after capture"))
        manager = self._manager(client)
        actor = Player(id="ai-1", name="AI", chips=100)
        opponent = Player(id="ai-2", name="Other", chips=100)
        state = GameState(players=[actor, opponent])

        with patch("server.ai.manager.build_poker_prompt", return_value="safe") as build:
            with patch("server.ai.manager.RuleEngine.should_use_llm", return_value=True):
                await manager.get_decision(
                    state,
                    actor,
                    {"CHECK": {"action": PlayerAction.CHECK, "amount": 0}},
                )

        self.assertEqual(build.call_args.kwargs["hole_cards"], actor.hole_cards)
        self.assertNotIn("players", build.call_args.kwargs)

    def test_prompt_leaves_output_shape_to_structured_api(self):
        prompt = build_poker_prompt(
            personality=None,
            hole_cards=[],
            community_cards=[],
            pot=0,
            current_bet=0,
            player_chips=100,
            position=None,
            action_history=[],
        )

        self.assertNotIn("single JSON object", prompt)
        self.assertNotIn("```json", prompt)


if __name__ == "__main__":
    unittest.main()

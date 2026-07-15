# Frontend Smoke Test

- Browser: Codex In-app Browser (Chromium; runtime version and user agent unavailable).
- Method: Real FastAPI game sessions at `http://127.0.0.1:8765`, controlled through the in-app browser at exact 1024x768, 1366x768, and 1920x1080 CSS viewports.
- Automated: `node --test frontend/tests/*.test.mjs` - PASS (53/53).
- WebSocket replay regression: `python test_websocket_turn_replay.py` - PASS (12 scenarios).
- Backend regression: `python test_betting_and_pot.py` - PASS (11 scenarios).
- 1024x768 single viewport - PASS. Document width/height equaled the viewport, the dock occupied y=692-768, and no horizontal or vertical page scroll appeared.
- 1366x768 single viewport - PASS. Document width/height equaled the viewport, the dock occupied y=692-768, and no horizontal or vertical page scroll appeared.
- 1920x1080 single viewport - PASS. Document width/height equaled the viewport, the dock occupied y=1004-1080, and no horizontal or vertical page scroll appeared.
- Setup/game/actions/results flow - PASS. Covered validation, start, check, call, fold, all-in, invalid and valid raises, all three presets, results, play again, and replay JSON.
- Reconnect disables actions - PASS. Stopping the server showed `Disconnected`, then `Reconnecting...`; all controls stayed disabled. Restarting did not restore the expired in-memory game. Same-process state-and-turn replay is covered by the WebSocket regression script.
- Keyboard and ARIA - PASS. F/C/A/R/I worked for enabled actions, shortcuts were ignored in the raise input, and live regions and alert roles were present.
- Focus traversal - NOT DIRECTLY VERIFIED. The in-app Browser Tab attempt did not expose the active control.
- Reduced motion - RULE PRESENT, NOT EMULATED. CSSOM inspection and automated tests confirmed the `prefers-reduced-motion: reduce` media rule, but the preference was not forcibly emulated.
- Log and sound preferences - PASS. Sound defaulted off; sound and collapsed-log settings persisted across reloads with matching ARIA state.
- Visible regions - PASS at every viewport. The table, all seats, community cards, hand, action log, and enabled controls remained visible.

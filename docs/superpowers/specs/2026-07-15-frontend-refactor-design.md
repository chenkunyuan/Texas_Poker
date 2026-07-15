# Frontend Refactor Design

## Goal

Refactor the vanilla JavaScript frontend into a maintainable desktop poker client with a cohesive “Midnight Casino” visual system. Preserve existing game rules, HTTP endpoints, and WebSocket messages while improving information hierarchy, code boundaries, and common betting interactions.

## Scope

The refactor targets desktop viewports at 1024 px and wider. The complete game screen must fit within one browser viewport at 1024×768, 1366×768, and 1920×1080 without a page-level scrollbar. Mobile and tablet layouts are out of scope.

In scope:

- Restyle setup, game, and results views.
- Replace the three-column game layout with a table-first layout.
- Convert frontend scripts to native ES modules without a framework or build tool.
- Split the large table script and monolithic stylesheet into focused modules.
- Add half-pot, three-quarter-pot, and pot-size betting shortcuts.
- Add a collapsible action log and a sound toggle.
- Improve connection, validation, loading, and error feedback.

Out of scope:

- Backend API, WebSocket, game-rule, or AI-provider changes.
- Statistics dashboards, replay browsing, theme switching, or mobile support.

## Visual and Interaction Design

Use a dark green felt surface, restrained brass accents, and dark wood details. Warm off-white text provides contrast without making the interface look clinical. Motion is short and functional: card dealing, active-player emphasis, and state transitions only.

The game view uses three fixed vertical regions: a compact status bar, a flexible game stage, and a bottom action dock. The oval table occupies the center and scales from the available viewport height. Player seats surround the table. The community cards and pot remain visually central. A compact hand summary floats at lower left, and the collapsible action log floats at lower right. At narrower desktop sizes, these panels compress before the table does.

The bottom dock keeps fold, check, call, raise input, betting shortcuts, and the primary raise action visible at all times. Disabled and pending states prevent duplicate submissions. Player states always include text such as “thinking,” “called,” or “folded”; color is supplementary.

## Frontend Architecture

Keep `frontend/index.html` as the SPA shell and use native ES module entry points. Organize JavaScript by responsibility:

- `app.js`: application bootstrap and transitions between setup, game, and results.
- `setup/`: player configuration, validation, and game creation.
- `game/`: state normalization, table orchestration, seats, cards, hand summary, action log, and action controls.
- `results/`: hand results and restart behavior.
- `services/`: HTTP and WebSocket transport behind stable functions.
- `state/`: current game snapshot plus local UI preferences.
- `utils/`: pure formatting, seat mapping, and betting calculations.

Each view receives state and renders only its own DOM region. UI modules call service functions rather than constructing requests. The state flow is one-way:

`server message -> normalized state -> render(state) -> user action -> service request -> server message`

Use custom events or explicit function arguments for module communication. Do not introduce new global application objects.

Split CSS into design tokens, base rules, layout rules, reusable components, and view-specific styles. Colors, spacing, radii, shadows, and transition durations must use shared custom properties.

## Local UI State

Persist only the action-log collapsed state and sound preference in `localStorage`. Sound is off by default; when enabled, short local cues announce the player's turn and completed actions. Game state remains authoritative on the server and must not be reconstructed from local storage. Betting shortcuts derive legal values from the current pot and action constraints, then clamp or disable values that the server would reject.

## Errors and Accessibility

Show connection status in the top bar. During WebSocket loss, display a reconnecting state and disable game actions until state is synchronized. HTTP and AI failures retain the current game view and show a dismissible message. Invalid betting values show an inline explanation next to the input.

All controls must have visible keyboard focus and accessible names. Announce important game changes through an `aria-live` region. Respect `prefers-reduced-motion`. No status may rely on color alone.

## Testing and Acceptance

Store pure-function tests as `frontend/tests/*.test.mjs` and run them with `node --test`. Cover state normalization, seat mapping, and betting shortcut calculations. Existing backend tests must continue to pass. Complete browser smoke tests at 1024×768, 1366×768, and 1920×1080.

The smoke flow covers setup, game start, check, call, raise, fold, results, reconnect, action-log collapse, sound toggle, and preference persistence. Acceptance requires no page-level scrollbar at any target size, a continuously visible action dock, no duplicate actions while a request is pending, and no changes to existing backend contracts.

## Delivery Strategy

Implement in vertical slices: establish tokens and the viewport shell, migrate setup, build the table and seats, add hand/log panels, migrate action controls, migrate results, then remove legacy globals and styles. Validate each slice before continuing so regressions remain localized.

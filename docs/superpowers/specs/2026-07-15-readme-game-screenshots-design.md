# README Game Screenshots Design

## Goal

Add a compact visual overview of the real game experience to the README using
screenshots captured from the running local application.

## Screenshot Set

Capture three PNG images at a consistent 1366×768 CSS viewport:

1. `docs/images/game-setup.png` — the initial game configuration screen.
2. `docs/images/game-table.png` — an active hand with the table, players,
   community area, action log, and controls visible.
3. `docs/images/game-results.png` — the completed-game results view.

The screenshots must come from the actual application. Do not generate,
mock, composite, or manually alter the UI content. Avoid exposing API keys,
developer tools, browser chrome, or unrelated desktop content.

## README Layout

Insert a `Screenshots` section between `Features` and `Quick Start`. Present
the active table as the primary full-width image, followed by setup and results
as two labeled images. Use repository-relative Markdown paths so the images
render on GitHub and in local Markdown viewers.

## Capture Flow

Start the local Uvicorn server from the project `.venv`, open the game at
`http://127.0.0.1:8000/`, set the viewport to 1366×768, and capture the setup
screen. Start a short one-human-versus-one-AI game with small stacks and capture
the table after the UI becomes interactive. Complete the short game through
normal controls and capture the results screen.

## Verification

Verify that all three files are valid PNGs with identical 1366×768 dimensions,
visually inspect each image, confirm each README path resolves to a tracked
file, and run the existing frontend tests because the live capture also checks
the documented UI states.

# Player Hand Contributions Display Design

## Goal

Show every player's cumulative chip contribution for the current hand on the poker table.

## Data source

The frontend will render `player.total_bet_this_round`. Despite its legacy name,
the game engine initializes it with posted blinds and continues accumulating it
through every betting street. It is reset when a new hand begins, so it is the
authoritative per-hand contribution value.

## UI

Each `.player-seat` will retain its existing player name, stack, and status. A
new line directly below the stack will display `Hand in <amount>`. It will use a
muted gold treatment so the remaining stack remains the primary numeric value.
The row is displayed for every player, including players who have folded or are
all-in. Missing, invalid, or zero values render as `Hand in 0`.

## Scope

Only the browser renderer, its styles, and the frontend table rendering test
will change. The server protocol and game-engine betting calculations are
already sufficient and will remain unchanged.

## Verification

The table-rendering test will assert formatted cumulative contributions, zero
fallback behavior, and the existing seat/status behavior. The full frontend
test suite and the repository betting-and-pot test script will be run.

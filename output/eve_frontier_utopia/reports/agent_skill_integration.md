# Agent Skill Integration

The right way to expose these commands through an Agent is to split them into three lanes.

## Lane 1: Public Read Skills

- `/system find <name>`: safe to expose directly to all players. It only depends on the public World API plus the local system index.
- `/ship info <id>`: safe to expose directly to all players. It only depends on the public World API.

## Lane 2: Local Runtime Control Skills

- `/launcher status`: useful for operator tooling and local diagnostics.
- `/launcher focus`: useful for operator tooling on the same machine.
- `/launcher journey <journeyId>`: useful for local launcher state coordination.
- These should not be treated as remote player abilities. They are host-local bridge calls to `localhost:3275`.

## Lane 3: Logged-In Game Operation Skills

- `/jump-history`: keep disabled until a real World API bearer source is captured and verified.
- `/move <from> <to>`: keep behind a game-operation layer. This is not a plain HTTP lookup. It requires live `source_gate`, `destination_gate`, and `character` identifiers plus a working prepared/sponsored transaction execution path.
- `/launcher connect <singleUseToken>`: treat as operator-only. It depends on an official one-time token source and should not be exposed as a normal player command.

## Recommended Agent Contract

- Expose Lane 1 immediately as player-facing skills.
- Expose Lane 2 only to the local operator Agent running on the same machine as the launcher.
- Hold Lane 3 behind runtime guards that check login state, live entity resolution, and signing readiness before the Agent can call them.

## Current Readiness

- Ready now: `/system find`, `/ship info`, `/launcher status`, `/launcher focus`, `/launcher journey`.
- Blocked on auth mapping: `/jump-history`.
- Blocked on live IDs and transaction execution: `/move`.
- Sensitive operator bridge: `/launcher connect`.

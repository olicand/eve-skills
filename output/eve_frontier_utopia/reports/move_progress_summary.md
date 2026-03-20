# Move Skill Progress

## Current State

- `/move <from> <to>` already resolves source and destination solar systems from the public World API plus the local `system_search_index.json`.
- The current local runtime prerequisites are satisfied:
  - launcher running
  - Utopia client running
  - `zk_signer` running
- The command is still blocked before transaction preparation can become executable.

## What Is Already Proven

- The jump contract is `eve.assembly.gate.api.PrepareJumpTransactionRequest`.
- That contract requires three live identifiers:
  - `source_gate`
  - `destination_gate`
  - `character`
- The corresponding evidence events are:
  - `eve.assembly.gate.api.Linked`
  - `eve.assembly.gate.api.Jumped`
- Prepared jump responses return:
  - `prepared_transaction`
  - `prepared_transaction_attributes`
- Separate sponsored/prepared transaction contracts confirm that execution also needs user signing material.

## Current Blockers

- `source_system_has_no_static_gate_evidence`
- `destination_system_has_no_static_gate_evidence`
- `missing_live_gate_identifiers`
- `missing_character_identifier`

## Capture Status

- Local launcher and proxy captures already exist.
- A dedicated game-flow capture was recorded:
  - `output/eve_frontier_utopia/captures/game_jump_flow_20260320T175815.pcapng`
- A dedicated MachoNet cache watch completed with no observed updates during the window:
  - `output/eve_frontier_utopia/reports/machonet_activity_watch_live.json`
- This strongly suggests no successful in-game jump interaction occurred during that watch period.

## Practical Meaning For Agent Skills

- `/move` is not ready to expose as a player-facing autonomous skill yet.
- It should stay behind a guard that requires:
  - live entity resolution
  - authenticated game-operation context
  - signing/execution readiness
- The next milestone is to capture one successful in-game movement action so the live gate and character identifiers can be mapped.

---
name: eve-frontier-player-ops
description: Use when the user wants to run or integrate player-facing EVE Frontier Utopia commands such as system lookup, ship lookup, local launcher control, jump-history probing, or move transaction planning from this machine.
---

# EVE Frontier Player Ops

Use this skill when the goal is to expose or execute player-facing commands through the local EVE Frontier Utopia tooling in this repo.

## Primary Entry Point

Run:

```bash
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" ...
```

## Commands

- `/system find <name>`
- `/ship info <id>`
- `/jump-history`
- `/move <from> <to>`
- `/launcher status`
- `/launcher focus`
- `/launcher journey <journeyId>`
- `/launcher connect <singleUseToken>`

## Readiness Rules

- Safe to expose as player-facing skills now:
  - `/system find`
  - `/ship info`
- Safe only for a local operator Agent on the same machine:
  - `/launcher status`
  - `/launcher focus`
  - `/launcher journey`
- Keep guarded until runtime blockers are resolved:
  - `/jump-history`
  - `/move`
  - `/launcher connect`

Before claiming a command is ready, check:

- `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/metadata/player_skill_contracts.json`
- `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/agent_skill_integration.md`
- `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/move_progress_summary.md`

## Quick Usage

```bash
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /system find "A 2560"
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /ship info 81609
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /launcher status
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /jump-history
python3 "/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /move "A 2560" "M 974"
```

## Guardrails

- Prefer the existing logged-in local session. Do not ask the user for raw credentials.
- `/jump-history` is only ready if a bearer token is accepted by `/v2/characters/me/jumps`.
- `/move` is only ready if live `source_gate`, `destination_gate`, and `character` identifiers have been resolved and a prepared or sponsored transaction path is available.
- When `/move` is still blocked, return the blocker report instead of pretending to submit a transaction.

## When To Dig Deeper

If the user wants to push `/jump-history` or `/move` further, use:

- `/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/auth_session.py`
- `/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/machonet_cache_watch.py`
- `/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/capture_launcher_bridge.sh`
- `/Users/ocrand/Documents/New project/eve_skills/eve-frontier-utopia-analysis/scripts/capture_game_jump_flow.sh`

Then update the reports under:

- `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/`

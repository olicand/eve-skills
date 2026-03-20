# Player Commands

## Status

- `/system find <name>`: implemented and tested against the public `World API /v2/solarsystems` listing.
- `/ship info <id>`: implemented and tested against the public `World API /v2/ships/{id}` route.
- `/jump-history`: implemented as a local auth probe plus protected request. Current local session tokens do not satisfy `GET /v2/characters/me/jumps`; the command returns a structured auth failure report instead of a fake success.
- `/move <from> <to>`: implemented as a system resolver plus jump transaction contract planner. It reports the `PrepareJumpTransactionRequest` fields and current blockers, but does not claim submission readiness until live gate and character identifiers are available.

## Command Entrypoint

```bash
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /system find "A 2560"
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /ship info 81609
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /jump-history
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /move "A 2560" "A 2561"
```

## Supporting Files

- `metadata/system_search_index.json`: searchable solar system index with static gate hints from `mapObjects.db`.
- `metadata/player_skill_contracts.json`: command-level contract summary.
- `reports/world_api_smoke_test.json`: latest public/protected endpoint smoke test.
- `analysis/pb2/eveProto/generated/eve/assembly/gate/api/requests_pb2.json`: jump transaction request/response contract.
- `analysis/pb2/eveProto/generated/eve/assembly/gate/api/events_pb2.json`: linked/jumped event evidence for gate-to-system relationships.

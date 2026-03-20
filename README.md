# EVE Skills

This repository contains a local Codex skill and curated analysis artifacts for
reverse engineering the EVE Frontier `utopia` client cache without writing back
into the game install, plus a player command layer for public World API queries
and logged-in transaction planning.

## Contents

- `eve-frontier-utopia-analysis/`
  - Codex skill definition, scripts, and agent metadata.
- `output/eve_frontier_utopia/reports/`
  - Human-readable summaries, including the interactable inventory.
- `output/eve_frontier_utopia/metadata/`
  - Structured JSON summaries for module families and extracted artifacts.
- `output/eve_frontier_utopia/analysis/pb2/`
  - Reflected protobuf interface JSON for high-value gameplay systems.
- `output/eve_frontier_utopia/metadata/system_search_index.json`
  - Searchable solar system index with static gate hints.
- `output/eve_frontier_utopia/metadata/player_skill_contracts.json`
  - Contract summary for `/system find`, `/ship info`, `/jump-history`, and `/move`.

## Workflow

1. Extract client artifacts into the separate output folder:

```bash
python3 "eve-frontier-utopia-analysis/scripts/extract_utopia_artifacts.py" \
  --shared-cache "/Users/ocrand/Library/Application Support/EVE Frontier/SharedCache" \
  --output "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia"
```

2. Analyze selected Python 3.12 modules and protobuf interfaces:

```bash
/opt/homebrew/bin/python3.12 "eve-frontier-utopia-analysis/scripts/analyze_pyc312.py" \
  --extracted-root "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/code_ccp/extracted" \
  --output "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/analysis"
```

3. Build the combined interactable inventory:

```bash
python3 "eve-frontier-utopia-analysis/scripts/build_interactable_inventory.py" \
  --output-root "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia"
```

4. Smoke test the Utopia World API:

```bash
python3 "eve-frontier-utopia-analysis/scripts/test_world_api.py"
```

To test the protected character endpoint as well, pass a bearer token:

```bash
python3 "eve-frontier-utopia-analysis/scripts/test_world_api.py" \
  --bearer-token "YOUR_TOKEN"
```

5. Build the solar system search index used by player commands:

```bash
python3 "eve-frontier-utopia-analysis/scripts/build_system_search_index.py"
```

6. Inspect the local logged-in session and probe protected World API bearer candidates:

```bash
python3 "eve-frontier-utopia-analysis/scripts/auth_session.py"
```

7. Run the player-facing commands:

```bash
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /system find "A 2560"
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /ship info 81609
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /jump-history
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" /move "A 2560" "A 2561"
```

`/system find` and `/ship info` are fully public. `/jump-history` probes the local logged-in session and tests candidate bearer tokens against the protected endpoint. `/move` resolves systems and reports the jump transaction contract plus missing live identifiers; it does not fake a signed transaction when the auth or gate lookup path is still incomplete.

8. Write the player command contracts and markdown reports:

```bash
python3 "eve-frontier-utopia-analysis/scripts/player_skill_commands.py" write-contracts
```

9. Optional local capture helpers when `/jump-history` still cannot derive a valid World API bearer:

```bash
zsh "eve-frontier-utopia-analysis/scripts/capture_proxy_loopback.sh"
zsh "eve-frontier-utopia-analysis/scripts/launch_frontier_with_sslkeylog.sh"
```

The loopback capture watches the local ClashX proxy on `127.0.0.1:7890`. The TLS keylog launcher is aimed at Electron/Chromium-side traffic and is the best starting point when you want Wireshark to decrypt launcher/EVE Vault HTTPS.

9. If you need to inspect the official auth chain in the launcher or webview, use the local capture helpers:

```bash
"eve-frontier-utopia-analysis/scripts/launch_frontier_with_sslkeylog.sh"
"eve-frontier-utopia-analysis/scripts/capture_proxy_loopback.sh"
```

The first script launches the Electron app with `SSLKEYLOGFILE` so Wireshark can decrypt Chromium TLS. The second captures traffic on `lo0` for the current ClashX proxy path at `127.0.0.1:7890`.

## Tracked vs Ignored Data

This repo tracks curated outputs that are useful for review and reuse:

- skill files
- reports
- metadata summaries
- protobuf interface JSON
- World API smoke test reports
- player command reports
- system search index

This repo intentionally ignores large raw client artifacts:

- extracted `code_ccp/`
- copied `raw/`
- `samples/`
- `staticdata/`
- `pyc_disassembly/`
- `pyc_metadata/`

## Notes

- All extracted content stays under `output/eve_frontier_utopia/`.
- Nothing in this repo writes under the EVE Frontier game directory.
- The most useful starting point is `output/eve_frontier_utopia/reports/interactable_inventory.md`.
- Public command entrypoint: `eve-frontier-utopia-analysis/scripts/player_skill_commands.py`.
- Local auth/session probe: `eve-frontier-utopia-analysis/scripts/auth_session.py`.
- Capture helpers: `eve-frontier-utopia-analysis/scripts/capture_proxy_loopback.sh` and `eve-frontier-utopia-analysis/scripts/launch_frontier_with_sslkeylog.sh`.
- Auth and capture playbook: `output/eve_frontier_utopia/reports/move_auth_flow.md`.

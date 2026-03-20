# EVE Skills

This repository contains a local Codex skill and curated analysis artifacts for
reverse engineering the EVE Frontier `utopia` client cache without writing back
into the game install.

## Contents

- `eve-frontier-utopia-analysis/`
  - Codex skill definition, scripts, and agent metadata.
- `output/eve_frontier_utopia/reports/`
  - Human-readable summaries, including the interactable inventory.
- `output/eve_frontier_utopia/metadata/`
  - Structured JSON summaries for module families and extracted artifacts.
- `output/eve_frontier_utopia/analysis/pb2/`
  - Reflected protobuf interface JSON for high-value gameplay systems.

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

## Tracked vs Ignored Data

This repo tracks curated outputs that are useful for review and reuse:

- skill files
- reports
- metadata summaries
- protobuf interface JSON
- World API smoke test reports

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

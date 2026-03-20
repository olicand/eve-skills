---
name: eve-frontier-utopia-analysis
description: Use when analyzing a local EVE Frontier SharedCache/utopia client, extracting client code and static data into a separate output folder, and organizing interactable places, UI flows, and proto interfaces without writing under the game directory.
---

# EVE Frontier Utopia Analysis

Use this skill when the user wants to inspect a local EVE Frontier client cache, reverse engineer the `utopia` build, or turn the results into reusable notes/skills.

## Rules

- Treat the game cache as read-only.
- Never write under `~/Library/Application Support/EVE Frontier/...`.
- Put all outputs in a separate workspace folder. Default: `<workspace>/output/eve_frontier_utopia`.
- Prefer extracting from `build/code.ccp`, `index_utopia.txt`, `resfileindex*.txt`, `staticdata/mapObjects.db`, and targeted `ResFiles` resources before spending time on raw binary reversing.

## Quick Start

1. Run the extractor:

```bash
python3 /Users/ocrand/Documents/New\ project/eve_skills/eve-frontier-utopia-analysis/scripts/extract_utopia_artifacts.py \
  --shared-cache "/Users/ocrand/Library/Application Support/EVE Frontier/SharedCache" \
  --output "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia"
```

2. If `python3.12` is available, run the 3.12 analyzer:

```bash
/opt/homebrew/bin/python3.12 /Users/ocrand/Documents/New\ project/eve_skills/eve-frontier-utopia-analysis/scripts/analyze_pyc312.py \
  --extracted-root "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/code_ccp/extracted" \
  --output "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/analysis"
```

This analyzer uses the extracted code root and injects a minimal `uthread2` stub during pb2 reflection, so it can export gameplay schemas without needing the live client runtime.

3. Build the combined interactable inventory:

```bash
python3 /Users/ocrand/Documents/New\ project/eve_skills/eve-frontier-utopia-analysis/scripts/build_interactable_inventory.py \
  --output-root "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia"
```

4. Smoke test the World API:

```bash
python3 /Users/ocrand/Documents/New\ project/eve_skills/eve-frontier-utopia-analysis/scripts/test_world_api.py
```

Pass `--bearer-token ...` when you want to verify a protected route such as `/v2/characters/me/jumps`.

5. Use the generated files to organize:
- static world objects from `staticdata/mapObjects.db`
- interactable place families inferred from `frontier/...` client modules
- UI entry points under `eve/client/script/ui/...`
- proto/API schemas from `eveProto/generated/eve/...`
- combined reports in `reports/interactable_inventory.md` and `metadata/interactable_inventory.json`
- live World API smoke test results in `reports/world_api_smoke_test.json`

## Data Sources To Prioritize

- `build/code.ccp`: ZIP of `.pyc` modules. This is the main code source.
- `build/bin64/staticdata/mapObjects.db`: static celestials and NPC station positions.
- `index_utopia.txt`: maps app/resource paths to `ResFiles`.
- `build/resfileindex*.txt` and `build/resfiledependencies.yaml`: resource inventory and dependencies.
- `build/res/planetResources.pickle`: planet-resource related tuning data.
- `build/bin64/*Loader.so`: useful as naming/signpost sources, but lower priority than `code.ccp`.

## High-Value Module Families

- Station and undock flow:
  - `frontier/station_hud/undock/controller.pyc`
  - `frontier/station/common/undock.pyc`
  - `eve/client/script/ui/station/...`
- Smart assemblies and building:
  - `frontier/smart_assemblies/client/window/cargo.pyc`
  - `frontier/smart_assemblies/client/gate/operation.pyc`
  - `frontier/base_building/client/construction_site/ui/window.pyc`
- Travel and space objects:
  - `frontier/jump_drive/client/service.pyc`
  - `frontier/jump_drive/client/jump_drive.pyc`
  - `frontier/crdata/common/objects/cr_stargate.pyc`
- Scanning and signatures:
  - `frontier/signatures_and_scanning/client/scanning_service.pyc`
- Proto interfaces:
  - `eveProto/generated/eve/assembly/gate/api/requests_pb2.pyc`
  - `eveProto/generated/eve/character/hacking/container_pb2.pyc`
  - `eveProto/generated/eve/deadspace/datasite/data_site_pb2.pyc`
  - `eveProto/generated/eve/deadspace/relicsite/relic_site_pb2.pyc`
  - `eveProto/generated/eve/character/operation/operation_pb2.pyc`

## Interpretation Guidance

- When the user asks for "all interactable places", separate the answer into:
  - static world locations discovered from `mapObjects.db`
  - dynamic/instanced interaction families inferred from code and proto modules
  - UI-only interaction surfaces inferred from client UI modules
- Do not claim perfect completeness from static analysis alone. Call out where a category is inferred from client modules rather than confirmed from a live server payload.
- For pb2 files, prefer schema export over prose. The generated JSON is usually more useful than free-form summary.
- For non-pb2 gameplay modules, use `marshal + dis` analysis to collect imports, class names, method names, and disassembly. Full source decompilation is optional and not required for first-pass interface organization.

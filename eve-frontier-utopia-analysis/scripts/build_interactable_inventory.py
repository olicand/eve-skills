#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


FAMILY_CONFIG = {
    "station_flow": {
        "description": "Station HUD, docking/undocking, and station-side inventory or session transitions inferred from client modules.",
        "proto_prefixes": [],
    },
    "assembly_and_building": {
        "description": "Player-built structures, smart assemblies, hangars, cargo windows, and construction-site flows.",
        "proto_prefixes": [],
    },
    "gates_and_travel": {
        "description": "Stargates, gate linking/unlinking, jump-drive flows, and travel-related client services.",
        "proto_prefixes": [
            "eve/assembly/gate/",
        ],
    },
    "scanning_and_sites": {
        "description": "Signature scanning, hacking containers, and deadspace site interactions such as data and relic sites.",
        "proto_prefixes": [
            "eve/character/hacking/",
            "eve/deadspace/",
        ],
    },
    "operations_and_objectives": {
        "description": "Keeper/objective flows plus explicit character operation lifecycle events and requests.",
        "proto_prefixes": [
            "eve/character/operation/",
        ],
    },
    "planetary_and_resources": {
        "description": "Planets, pins, colonies, collectors, links, routes, factories, storage, and planet-resource data.",
        "proto_prefixes": [
            "eve/planet/",
            "eve/planetinteraction/",
            "eve/character/planetinteraction/",
            "eve/corporation/planetinteraction/",
        ],
    },
    "legacy_structure_ui": {
        "description": "Legacy structure browser, deployment, access groups, and structure-side UI entry points carried into Frontier.",
        "proto_prefixes": [],
    },
}

MODULE_TOKEN_WEIGHTS = {
    "controller": 12,
    "service": 12,
    "window": 10,
    "operation": 10,
    "undock": 10,
    "jump": 10,
    "scan": 10,
    "gate": 10,
    "cargo": 9,
    "construction": 9,
    "container": 8,
    "hud": 8,
    "browser": 8,
    "deployment": 8,
    "collector": 8,
    "factory": 8,
    "storage": 8,
    "colony": 8,
    "route": 7,
    "planet": 7,
    "pin": 7,
    "link": 7,
}

RAW_GROUP_ID_HINTS = {
    6: "Likely sun objects (one per solar system in this dump).",
    7: "Likely planets.",
    8: "Likely moons.",
    10: "Likely stargates / travel nodes.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a combined interactable-place inventory from extracted EVE Frontier Utopia artifacts."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Root output folder produced by extract_utopia_artifacts.py.",
    )
    return parser.parse_args()


def load_json(path: Path) -> object:
    return json.loads(path.read_text())


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def collect_pyc_metadata(output_root: Path) -> dict[str, dict[str, object]]:
    metadata_root = output_root / "analysis" / "pyc_metadata"
    pyc_metadata: dict[str, dict[str, object]] = {}
    if not metadata_root.exists():
        return pyc_metadata

    for path in sorted(metadata_root.rglob("*.json")):
        if path.name.endswith(".error.json"):
            continue
        payload = load_json(path)
        rel_module_path = payload.get("path")
        if isinstance(rel_module_path, str):
            pyc_metadata[rel_module_path] = payload
    return pyc_metadata


def collect_pb2_descriptors(output_root: Path) -> list[dict[str, object]]:
    pb2_root = output_root / "analysis" / "pb2"
    descriptors: list[dict[str, object]] = []
    if not pb2_root.exists():
        return descriptors

    for path in sorted(pb2_root.rglob("*.json")):
        if path.name.endswith("_error.json"):
            continue
        payload = load_json(path)
        rel = path.relative_to(pb2_root).with_suffix("")
        import_name = ".".join(rel.parts)
        descriptors.append(
            {
                "import_name": import_name,
                "proto_file": payload.get("name"),
                "package": payload.get("package"),
                "messages": [message.get("name") for message in payload.get("messages", []) if message.get("name")],
                "path": str(path.relative_to(output_root)),
            }
        )
    return descriptors


def unique_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def interesting_symbols(pyc_payload: dict[str, object], limit: int = 8) -> list[str]:
    code_objects = pyc_payload.get("code_objects", [])
    names = [
        code_obj.get("qualname")
        for code_obj in code_objects
        if isinstance(code_obj, dict) and code_obj.get("qualname") and code_obj.get("qualname") != "<module>"
    ]
    return unique_ordered([name for name in names if isinstance(name, str)])[:limit]


def module_score(module_path: str, analyzed_paths: set[str]) -> tuple[int, int, str]:
    score = 0
    if module_path in analyzed_paths:
        score += 100
    if module_path.endswith("__init__.pyc"):
        score -= 20
    for token, weight in MODULE_TOKEN_WEIGHTS.items():
        if token in module_path:
            score += weight
    return (-score, len(module_path), module_path)


def choose_key_modules(module_paths: list[str], analyzed_paths: set[str], limit: int = 10) -> list[str]:
    return sorted(module_paths, key=lambda item: module_score(item, analyzed_paths))[:limit]


def descriptors_for_family(
    family_name: str,
    descriptors: list[dict[str, object]],
) -> list[dict[str, object]]:
    prefixes = FAMILY_CONFIG[family_name]["proto_prefixes"]
    if not prefixes:
        return []

    matches = []
    for descriptor in descriptors:
        proto_file = descriptor.get("proto_file")
        if not isinstance(proto_file, str):
            continue
        if any(proto_file.startswith(prefix) for prefix in prefixes):
            matches.append(descriptor)
    return matches


def build_inventory(output_root: Path) -> dict[str, object]:
    group_data = load_json(output_root / "metadata" / "interactable_module_groups.json")
    map_summary = load_json(output_root / "staticdata" / "mapObjects" / "summary.json")
    planet_resources = load_json(output_root / "metadata" / "planet_resources_summary.json")
    analysis_summary = load_json(output_root / "analysis" / "summary.json")
    pyc_metadata = collect_pyc_metadata(output_root)
    pb2_descriptors = collect_pb2_descriptors(output_root)
    analyzed_paths = set(pyc_metadata)

    families: list[dict[str, object]] = []
    for family_name, module_paths in group_data.items():
        if family_name not in FAMILY_CONFIG:
            continue
        key_modules = choose_key_modules(module_paths, analyzed_paths)
        symbol_highlights = []
        for module_path in key_modules:
            payload = pyc_metadata.get(module_path)
            if not payload:
                continue
            symbols = interesting_symbols(payload)
            if symbols:
                symbol_highlights.append({"module": module_path, "symbols": symbols})

        family_descriptors = descriptors_for_family(family_name, pb2_descriptors)
        families.append(
            {
                "family": family_name,
                "description": FAMILY_CONFIG[family_name]["description"],
                "module_count": len(module_paths),
                "key_modules": key_modules,
                "symbol_highlights": symbol_highlights,
                "pb2_interfaces": family_descriptors,
            }
        )

    static_world = {
        "celestials_count": map_summary.get("celestials_count"),
        "celestials_system_count": map_summary.get("celestials_system_count"),
        "npc_station_count": map_summary.get("npc_station_count"),
        "npc_station_system_count": map_summary.get("npc_station_system_count"),
        "npc_station_type_counts": map_summary.get("npc_station_type_counts", []),
        "celestial_group_counts": [
            {
                "groupID": entry.get("groupID"),
                "count": entry.get("count"),
                "hint": RAW_GROUP_ID_HINTS.get(entry.get("groupID"), "No local label resolved yet."),
            }
            for entry in map_summary.get("celestial_group_counts", [])
        ],
    }

    return {
        "output_root": str(output_root),
        "analysis_root": str(output_root / "analysis"),
        "analysis_summary": {
            "python": analysis_summary.get("python"),
            "pyc_modules_attempted": len(analysis_summary.get("module_results", [])),
            "pb2_modules_attempted": len(analysis_summary.get("pb2_results", [])),
            "pb2_modules_ok": sum(1 for item in analysis_summary.get("pb2_results", []) if item.get("status") == "ok"),
        },
        "static_world": static_world,
        "planet_resources": {
            "found": planet_resources.get("found"),
            "pickle_type": planet_resources.get("pickle_type"),
            "keys": planet_resources.get("keys", []),
        },
        "families": families,
        "notes": [
            "Static world counts come from mapObjects.db and confirm where coordinates/IDs exist in the client cache.",
            "Module families come from local client code and indicate interaction surfaces even when no pb2 schema is exported yet.",
            "pb2 interfaces are confirmed from Python 3.12 imports against the extracted code, with a minimal uthread2 stub during analysis.",
            "Raw celestial group IDs still need full Frontier static-data name resolution before treating them as final labels.",
        ],
    }


def render_markdown(inventory: dict[str, object]) -> str:
    static_world = inventory["static_world"]
    families = inventory["families"]
    lines = [
        "# EVE Frontier Utopia Interactable Inventory",
        "",
        "## Scope",
        "",
        f"- Output root: `{inventory['output_root']}`",
        f"- Analysis root: `{inventory['analysis_root']}`",
        f"- Pyc modules analyzed: `{inventory['analysis_summary']['pyc_modules_attempted']}`",
        f"- Pb2 modules exported: `{inventory['analysis_summary']['pb2_modules_ok']}` / `{inventory['analysis_summary']['pb2_modules_attempted']}`",
        "",
        "## Static World Evidence",
        "",
        f"- Celestials: `{static_world['celestials_count']}` across `{static_world['celestials_system_count']}` solar systems.",
        f"- NPC stations: `{static_world['npc_station_count']}` across `{static_world['npc_station_system_count']}` solar systems.",
        "- Dominant raw celestial groups:",
    ]

    for entry in static_world["celestial_group_counts"]:
        lines.append(f"  - `groupID {entry['groupID']}`: `{entry['count']}` objects. {entry['hint']}")

    lines.extend(
        [
            "",
            "## Planet Resource Data",
            "",
            f"- Found: `{inventory['planet_resources']['found']}`",
            f"- Pickle type: `{inventory['planet_resources']['pickle_type']}`",
            f"- Keys: `{inventory['planet_resources']['keys']}`",
            "",
            "## Interaction Families",
            "",
        ]
    )

    for family in families:
        lines.extend(
            [
                f"### {family['family']}",
                "",
                f"- Summary: {family['description']}",
                f"- Module count: `{family['module_count']}`",
                "- Key modules:",
            ]
        )
        for module_path in family["key_modules"]:
            lines.append(f"  - `{module_path}`")

        if family["symbol_highlights"]:
            lines.append("- Symbol highlights:")
            for entry in family["symbol_highlights"]:
                joined = ", ".join(f"`{symbol}`" for symbol in entry["symbols"])
                lines.append(f"  - `{entry['module']}` -> {joined}")
        else:
            lines.append("- Symbol highlights: no targeted Python 3.12 metadata export for this family yet.")

        if family["pb2_interfaces"]:
            lines.append("- Confirmed pb2 interfaces:")
            for descriptor in family["pb2_interfaces"]:
                messages = ", ".join(f"`{name}`" for name in descriptor["messages"]) or "`<none>`"
                lines.append(
                    f"  - `{descriptor['proto_file']}` ({descriptor['package']}) -> {messages} "
                    f"[`{descriptor['path']}`]"
                )
        else:
            lines.append("- Confirmed pb2 interfaces: none in the current exported set.")

        lines.append("")

    lines.extend(
        [
            "## Notes",
            "",
        ]
    )
    for note in inventory["notes"]:
        lines.append(f"- {note}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_root = args.output_root.expanduser().resolve()
    inventory = build_inventory(output_root)
    write_json(output_root / "metadata" / "interactable_inventory.json", inventory)
    write_text(output_root / "reports" / "interactable_inventory.md", render_markdown(inventory))
    print(f"Wrote interactable inventory to: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

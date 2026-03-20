#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pickle
import re
import shutil
import sqlite3
import sys
import textwrap
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterable


CATEGORY_PREFIXES = {
    "space_hud": ("frontier/hud/",),
    "station": (
        "frontier/station/",
        "frontier/station_hud/",
        "eve/client/script/ui/station/",
    ),
    "building": (
        "frontier/base_building/",
        "frontier/smart_assemblies/",
    ),
    "navigation": (
        "frontier/warping/",
        "frontier/jump_drive/",
        "frontier/navigation/",
        "frontier/signatures_and_scanning/",
    ),
    "world_objects": (
        "frontier/crdata/common/objects/",
        "frontier/crdata/common/components/",
    ),
    "proto_interfaces": ("eveProto/generated/eve/",),
    "legacy_ui": ("eve/client/script/ui/",),
}

INTERACTABLE_GROUPS = {
    "station_flow": (
        "frontier/station/",
        "frontier/station_hud/",
        "eve/client/script/ui/station/",
    ),
    "assembly_and_building": (
        "frontier/base_building/",
        "frontier/smart_assemblies/",
    ),
    "gates_and_travel": (
        "frontier/jump_drive/",
        "frontier/warping/",
        "frontier/crdata/common/objects/cr_stargate.pyc",
        "eveProto/generated/eve/assembly/gate/",
    ),
    "scanning_and_sites": (
        "frontier/signatures_and_scanning/",
        "eveProto/generated/eve/deadspace/",
        "eveProto/generated/eve/dungeon/",
        "eveProto/generated/eve/character/hacking/",
    ),
    "operations_and_objectives": (
        "eveProto/generated/eve/character/operation/",
        "eveProto/generated/eve/operation/",
        "frontier/keeper/",
    ),
    "planetary_and_resources": (
        "eveProto/generated/eve/planetinteraction/",
        "eveProto/generated/eve/planet/",
    ),
    "legacy_structure_ui": ("eve/client/script/ui/structure/",),
}

HIGH_VALUE_MODULES = [
    "frontier/station_hud/undock/controller.pyc",
    "frontier/smart_assemblies/client/window/cargo.pyc",
    "frontier/base_building/client/construction_site/ui/window.pyc",
    "frontier/signatures_and_scanning/client/scanning_service.pyc",
    "frontier/jump_drive/client/service.pyc",
    "frontier/jump_drive/client/jump_drive.pyc",
    "frontier/smart_assemblies/client/gate/operation.pyc",
    "frontier/crdata/common/objects/cr_stargate.pyc",
    "eveProto/generated/eve/assembly/gate/api/requests_pb2.pyc",
    "eveProto/generated/eve/character/hacking/container_pb2.pyc",
    "eveProto/generated/eve/deadspace/datasite/data_site_pb2.pyc",
    "eveProto/generated/eve/deadspace/relicsite/relic_site_pb2.pyc",
    "eveProto/generated/eve/character/operation/operation_pb2.pyc",
    "eve/client/script/ui/station/stationServiceConst.pyc",
    "eve/client/script/ui/station/agents/agentDialogueWindow.pyc",
    "eve/client/script/ui/structure/structuremenu.pyc",
]

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{2,}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract EVE Frontier utopia client artifacts into a separate output folder."
    )
    parser.add_argument(
        "--shared-cache",
        type=Path,
        default=Path.home() / "Library/Application Support/EVE Frontier/SharedCache",
        help="Path to the EVE Frontier SharedCache directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Separate output folder. This script never writes under the game directory.",
    )
    parser.add_argument(
        "--code-extract",
        choices=("full", "high-value", "none"),
        default="full",
        help="How much of code.ccp to extract. Default: full.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite extracted files that already exist.",
    )
    return parser.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def category_for_path(path_str: str) -> str:
    for category, prefixes in CATEGORY_PREFIXES.items():
        if any(path_str.startswith(prefix) for prefix in prefixes):
            return category
    return "other"


def parse_index(index_path: Path) -> dict[str, dict[str, object]]:
    lookup: dict[str, dict[str, object]] = {}
    with index_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or "," not in line:
                continue
            parts = line.split(",")
            if len(parts) < 2:
                continue
            lookup[parts[0]] = {
                "path": parts[0],
                "res_rel": parts[1],
                "hash": parts[2] if len(parts) > 2 else None,
                "size": int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None,
                "compressed_size": int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None,
                "build": parts[5] if len(parts) > 5 else None,
            }
    return lookup


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def export_sqlite_table(conn: sqlite3.Connection, table: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cur = conn.execute(f"SELECT * FROM {table}")
    headers = [col[0] for col in cur.description]
    with dst.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(cur.fetchall())


def summarize_map_objects(db_path: Path, output_root: Path) -> dict[str, object]:
    conn = sqlite3.connect(db_path)
    try:
        export_sqlite_table(conn, "celestials", output_root / "staticdata/mapObjects/celestials.csv")
        export_sqlite_table(conn, "npcStations", output_root / "staticdata/mapObjects/npcStations.csv")

        celestials_count, celestials_systems = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT solarSystemID) FROM celestials"
        ).fetchone()
        stations_count, station_systems = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT solarSystemID) FROM npcStations"
        ).fetchone()

        group_counts = [
            {"groupID": group_id, "count": count}
            for group_id, count in conn.execute(
                "SELECT groupID, COUNT(*) FROM celestials GROUP BY groupID ORDER BY COUNT(*) DESC"
            ).fetchall()
        ]
        station_type_counts = [
            {"typeID": type_id, "count": count}
            for type_id, count in conn.execute(
                "SELECT typeID, COUNT(*) FROM npcStations GROUP BY typeID ORDER BY COUNT(*) DESC"
            ).fetchall()
        ]
        summary = {
            "celestials_count": celestials_count,
            "celestials_system_count": celestials_systems,
            "npc_station_count": stations_count,
            "npc_station_system_count": station_systems,
            "celestial_group_counts": group_counts,
            "npc_station_type_counts": station_type_counts,
        }
        write_json(output_root / "staticdata/mapObjects/summary.json", summary)
        return summary
    finally:
        conn.close()


def extract_printable_strings(data: bytes, limit: int = 120) -> list[str]:
    values = [match.decode("latin1", errors="ignore") for match in PRINTABLE_RE.findall(data)]
    return dedupe(values)[:limit]


def high_value_module_metadata(zip_file: zipfile.ZipFile) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    archive_names = set(zip_file.namelist())
    for rel_path in HIGH_VALUE_MODULES:
        if rel_path not in archive_names:
            continue
        data = zip_file.read(rel_path)
        strings = extract_printable_strings(data)
        identifiers = [value for value in strings if IDENTIFIER_RE.match(value)]
        dotted_symbols = [value for value in identifiers if "." in value]
        source_path = next(
            (
                value
                for value in strings
                if value.endswith(".py") and ("/packages/" in value or value.startswith("/Users/"))
            ),
            None,
        )
        results.append(
            {
                "path": rel_path,
                "embedded_source_path": source_path,
                "identifier_strings": identifiers[:80],
                "dotted_symbols": dotted_symbols[:40],
                "class_like_strings": [value for value in identifiers if value[:1].isupper()][:20],
            }
        )
    return results


def build_module_catalog(zip_file: zipfile.ZipFile) -> tuple[list[dict[str, object]], dict[str, int]]:
    catalog: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    for info in zip_file.infolist():
        if not info.filename.endswith(".pyc"):
            continue
        category = category_for_path(info.filename)
        counts[category] += 1
        catalog.append(
            {
                "path": info.filename,
                "size": info.file_size,
                "category": category,
                "is_high_value": info.filename in HIGH_VALUE_MODULES,
            }
        )
    return catalog, dict(counts)


def select_code_entries(zip_file: zipfile.ZipFile, mode: str) -> list[str]:
    names = zip_file.namelist()
    if mode == "none":
        return []
    if mode == "high-value":
        selected = set(HIGH_VALUE_MODULES)
        selected.update(name for name in names if name.startswith("eveProto/generated/eve/"))
        return [name for name in names if name in selected]
    return names


def extract_code(zip_file: zipfile.ZipFile, output_root: Path, mode: str, overwrite: bool) -> dict[str, object]:
    selected = select_code_entries(zip_file, mode)
    extracted_root = output_root / "code_ccp/extracted"
    extracted = 0
    skipped = 0

    for name in selected:
        target = extracted_root / name
        if target.exists() and not overwrite:
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zip_file.open(name, "r") as src_handle, target.open("wb") as dst_handle:
            shutil.copyfileobj(src_handle, dst_handle)
        extracted += 1

    stats = {
        "mode": mode,
        "selected_entries": len(selected),
        "extracted_entries": extracted,
        "skipped_existing_entries": skipped,
        "output_root": str(extracted_root),
    }
    write_json(output_root / "metadata/code_extraction_stats.json", stats)
    return stats


def group_interactable_modules(catalog: list[dict[str, object]]) -> dict[str, list[str]]:
    paths = [entry["path"] for entry in catalog]
    grouped: dict[str, list[str]] = {}
    for group_name, prefixes in INTERACTABLE_GROUPS.items():
        matches = [
            path
            for path in paths
            if any(path.startswith(prefix) or path == prefix for prefix in prefixes)
        ]
        grouped[group_name] = matches
    return grouped


def summarize_planet_resources(index_lookup: dict[str, dict[str, object]], shared_cache: Path, output_root: Path) -> dict[str, object]:
    key = "app:/EVE.app/Contents/Resources/build/res/planetResources.pickle"
    record = index_lookup.get(key)
    if not record:
        summary = {"found": False}
        write_json(output_root / "metadata/planet_resources_summary.json", summary)
        return summary

    res_rel = str(record["res_rel"])
    res_path = shared_cache / "ResFiles" / res_rel
    summary: dict[str, object] = {
        "found": True,
        "res_rel": res_rel,
        "size": res_path.stat().st_size if res_path.exists() else None,
    }

    if not res_path.exists():
        summary["error"] = f"Missing resource file: {res_path}"
        write_json(output_root / "metadata/planet_resources_summary.json", summary)
        return summary

    copy_if_exists(res_path, output_root / "raw/planetResources.pickle")
    raw = res_path.read_bytes()
    try:
        obj = pickle.loads(raw, encoding="latin1")
        summary["pickle_type"] = type(obj).__name__
        if isinstance(obj, dict):
            summary["keys"] = list(obj.keys())
            summary["value_types"] = {key_name: type(value).__name__ for key_name, value in obj.items()}
            if isinstance(obj.get("depletionTemplates"), list):
                depletion_templates = obj["depletionTemplates"]
                summary["depletion_template_count"] = len(depletion_templates)
                summary["depletion_template_item_type"] = (
                    type(depletion_templates[0]).__name__ if depletion_templates else None
                )
            if "depletionStdDevMax" in obj:
                summary["depletionStdDevMax"] = obj["depletionStdDevMax"]
            if "depletionStdDevStepSize" in obj:
                summary["depletionStdDevStepSize"] = obj["depletionStdDevStepSize"]
    except Exception as exc:  # pragma: no cover - defensive fallback
        summary["error"] = str(exc)

    write_json(output_root / "metadata/planet_resources_summary.json", summary)
    return summary


def write_overview(
    output_root: Path,
    shared_cache: Path,
    build_root: Path,
    category_counts: dict[str, int],
    interactable_groups: dict[str, list[str]],
    map_summary: dict[str, object],
    planet_summary: dict[str, object],
    extraction_stats: dict[str, object],
) -> None:
    group_lines = []
    for group_name, modules in interactable_groups.items():
        preview = "\n".join(f"- `{module}`" for module in modules[:10])
        if len(modules) > 10:
            preview += f"\n- ... and {len(modules) - 10} more"
        group_lines.append(f"## {group_name}\n\nCount: {len(modules)}\n\n{preview or '- No matches'}")

    category_lines = "\n".join(
        f"- `{category}`: {count}" for category, count in sorted(category_counts.items())
    )

    text = textwrap.dedent(
        f"""\
        # EVE Frontier Utopia Extraction

        ## Source

        - SharedCache: `{shared_cache}`
        - Build root: `{build_root}`
        - Output root: `{output_root}`
        - Code extract mode: `{extraction_stats['mode']}`
        - Selected code entries: {extraction_stats['selected_entries']}
        - Extracted code entries: {extraction_stats['extracted_entries']}

        ## Module Categories

        {category_lines}

        ## Static Data

        - Celestials: {map_summary['celestials_count']} across {map_summary['celestials_system_count']} solar systems
        - NPC stations: {map_summary['npc_station_count']} across {map_summary['npc_station_system_count']} solar systems

        ## Planet Resources

        - Found: {planet_summary.get('found', False)}
        - Pickle type: {planet_summary.get('pickle_type')}
        - Keys: {planet_summary.get('keys', [])}

        ## Interactable Module Groups

        {chr(10).join(group_lines)}

        ## Notes

        - `mapObjects.db` gives static IDs and positions, not resolved names for every group/type.
        - `code.ccp` is the most useful code source and contains 3.12 `.pyc` modules.
        - `eveProto/generated/eve/...` can be reflected into JSON schemas with `python3.12` and `protobuf==3.20.x`.
        - Full source decompilation is optional; `marshal + dis` is enough for a first-pass interface inventory.
        """
    )
    write_text(output_root / "reports/summary.md", text)


def main() -> int:
    args = parse_args()
    shared_cache = args.shared_cache.expanduser().resolve()
    output_root = args.output.expanduser().resolve()
    build_root = shared_cache / "utopia/EVE.app/Contents/Resources/build"
    code_ccp_path = build_root / "code.ccp"
    index_utopia_path = shared_cache / "index_utopia.txt"
    map_objects_db = build_root / "bin64/staticdata/mapObjects.db"

    ensure_exists(shared_cache, "SharedCache")
    ensure_exists(build_root, "Build root")
    ensure_exists(code_ccp_path, "code.ccp")
    ensure_exists(index_utopia_path, "index_utopia.txt")
    ensure_exists(map_objects_db, "mapObjects.db")

    output_root.mkdir(parents=True, exist_ok=True)
    for subdir in ("metadata", "raw", "reports", "staticdata/mapObjects"):
        (output_root / subdir).mkdir(parents=True, exist_ok=True)

    copy_if_exists(index_utopia_path, output_root / "raw/index_utopia.txt")
    copy_if_exists(build_root / "resfileindex.txt", output_root / "raw/resfileindex.txt")
    copy_if_exists(build_root / "resfileindex_macOS.txt", output_root / "raw/resfileindex_macOS.txt")
    copy_if_exists(build_root / "resfileindex_prefetch.txt", output_root / "raw/resfileindex_prefetch.txt")
    copy_if_exists(build_root / "resfiledependencies.yaml", output_root / "raw/resfiledependencies.yaml")
    copy_if_exists(build_root / "start.ini", output_root / "raw/start.ini")
    copy_if_exists(map_objects_db, output_root / "raw/mapObjects.db")

    index_lookup = parse_index(index_utopia_path)
    write_json(output_root / "metadata/index_utopia_lookup.json", index_lookup)

    with zipfile.ZipFile(code_ccp_path) as zip_file:
        catalog, category_counts = build_module_catalog(zip_file)
        write_json(output_root / "metadata/code_ccp_catalog.json", catalog)
        write_json(output_root / "metadata/code_ccp_category_counts.json", category_counts)
        write_json(output_root / "metadata/high_value_modules.json", high_value_module_metadata(zip_file))
        extraction_stats = extract_code(zip_file, output_root, args.code_extract, args.overwrite)

    interactable_groups = group_interactable_modules(catalog)
    write_json(output_root / "metadata/interactable_module_groups.json", interactable_groups)

    map_summary = summarize_map_objects(map_objects_db, output_root)
    planet_summary = summarize_planet_resources(index_lookup, shared_cache, output_root)

    write_overview(
        output_root=output_root,
        shared_cache=shared_cache,
        build_root=build_root,
        category_counts=category_counts,
        interactable_groups=interactable_groups,
        map_summary=map_summary,
        planet_summary=planet_summary,
        extraction_stats=extraction_stats,
    )

    print(f"Wrote extraction output to: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

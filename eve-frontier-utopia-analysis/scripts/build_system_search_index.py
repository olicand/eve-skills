#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from world_api_client import (
    DEFAULT_SYSTEM_INDEX_PATH,
    DEFAULT_WORLD_API_BASE_URL,
    WorldApiClient,
    alnum_key,
    normalize_name,
    tokenize_name,
)


DEFAULT_MAP_OBJECTS_DB = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/raw/mapObjects.db"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a searchable solar system index from the public Utopia World API.")
    parser.add_argument("--base-url", default=DEFAULT_WORLD_API_BASE_URL, help="World API base URL.")
    parser.add_argument("--page-size", type=int, default=1000, help="Pagination size for /v2/solarsystems.")
    parser.add_argument("--map-objects-db", type=Path, default=DEFAULT_MAP_OBJECTS_DB, help="Path to mapObjects.db for static gate hints.")
    parser.add_argument("--output", type=Path, default=DEFAULT_SYSTEM_INDEX_PATH, help="Output JSON path.")
    return parser.parse_args()


def fetch_gate_hints(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}

    query = """
        SELECT
            solarSystemID,
            COUNT(*) AS static_gate_count,
            GROUP_CONCAT(DISTINCT typeID) AS gate_type_ids
        FROM celestials
        WHERE groupID = 10
        GROUP BY solarSystemID
    """
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(query).fetchall()
    finally:
        connection.close()

    result: dict[int, dict[str, Any]] = {}
    for solar_system_id, gate_count, raw_type_ids in rows:
        type_ids = sorted(
            int(part)
            for part in (raw_type_ids or "").split(",")
            if part
        )
        result[int(solar_system_id)] = {
            "static_gate_count": int(gate_count),
            "static_gate_type_ids": type_ids,
            "has_static_gate_evidence": int(gate_count) > 0,
        }
    return result


def build_system_index(base_url: str, *, page_size: int, map_objects_db: Path) -> dict[str, Any]:
    client = WorldApiClient(base_url=base_url)
    gate_hints = fetch_gate_hints(map_objects_db)
    systems = []
    for item in client.iter_collection("/v2/solarsystems", page_size=page_size):
        system_id = int(item["id"])
        name = str(item["name"])
        hint = gate_hints.get(system_id, {})
        systems.append(
            {
                "id": system_id,
                "name": name,
                "normalized_name": normalize_name(name),
                "alnum_name": alnum_key(name),
                "tokens": tokenize_name(name),
                "constellation_id": int(item["constellationId"]),
                "region_id": int(item["regionId"]),
                "location": item.get("location"),
                "static_gate_count": int(hint.get("static_gate_count", 0)),
                "static_gate_type_ids": list(hint.get("static_gate_type_ids", [])),
                "has_static_gate_evidence": bool(hint.get("has_static_gate_evidence", False)),
            }
        )

    systems.sort(key=lambda item: item["id"])
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url.rstrip("/"),
        "system_count": len(systems),
        "map_objects_db": str(map_objects_db),
        "systems": systems,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def main() -> int:
    args = parse_args()
    payload = build_system_index(args.base_url, page_size=args.page_size, map_objects_db=args.map_objects_db.expanduser().resolve())
    write_json(args.output.expanduser().resolve(), payload)
    print(json.dumps({"output": str(args.output.expanduser().resolve()), "system_count": payload["system_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

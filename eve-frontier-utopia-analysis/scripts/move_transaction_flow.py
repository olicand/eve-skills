#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from auth_session import resolve_world_api_auth
from build_system_search_index import build_system_index
from world_api_client import DEFAULT_SYSTEM_INDEX_PATH, load_system_index, search_system_index


DEFAULT_GATE_REQUESTS_PATH = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/analysis/pb2/eveProto/generated/eve/assembly/gate/api/requests_pb2.json"
)
DEFAULT_GATE_EVENTS_PATH = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/analysis/pb2/eveProto/generated/eve/assembly/gate/api/events_pb2.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a /move transaction plan from source and destination system names.")
    parser.add_argument("source", help="Source solar system name.")
    parser.add_argument("destination", help="Destination solar system name.")
    parser.add_argument("--system-index", type=Path, default=DEFAULT_SYSTEM_INDEX_PATH, help="Path to system_search_index.json.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def summarize_gate_contracts() -> dict[str, Any]:
    request_spec = load_json(DEFAULT_GATE_REQUESTS_PATH)
    event_spec = load_json(DEFAULT_GATE_EVENTS_PATH)

    request_map = {message["name"]: message for message in request_spec.get("messages", [])}
    event_map = {message["name"]: message for message in event_spec.get("messages", [])}

    jump_request = request_map["PrepareJumpTransactionRequest"]
    jump_response = request_map["PrepareJumpTransactionResponse"]
    linked_event = event_map["Linked"]
    jumped_event = event_map["Jumped"]

    return {
        "prepare_jump_request": {
            "full_name": jump_request["full_name"],
            "required_fields": [
                {"name": field["name"], "type_name": field["type_name"], "type": field["type"]}
                for field in jump_request.get("fields", [])
            ],
        },
        "prepare_jump_response": {
            "full_name": jump_response["full_name"],
            "fields": [
                {"name": field["name"], "type_name": field["type_name"], "type": field["type"]}
                for field in jump_response.get("fields", [])
            ],
        },
        "evidence_events": {
            "linked": {
                "full_name": linked_event["full_name"],
                "fields": [field["name"] for field in linked_event.get("fields", [])],
            },
            "jumped": {
                "full_name": jumped_event["full_name"],
                "fields": [field["name"] for field in jumped_event.get("fields", [])],
            },
        },
    }


def pick_best_match(matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    return matches[0] if matches else None


def summarize_match(match: dict[str, Any] | None) -> dict[str, Any] | None:
    if not match:
        return None
    return {
        "id": match["id"],
        "name": match["name"],
        "score": match["score"],
        "constellation_id": match["constellation_id"],
        "region_id": match["region_id"],
        "static_gate_count": match["static_gate_count"],
        "static_gate_type_ids": match["static_gate_type_ids"],
        "has_static_gate_evidence": match["has_static_gate_evidence"],
    }


def build_move_plan(source: str, destination: str, *, system_index_path: Path) -> dict[str, Any]:
    if system_index_path.exists():
        index_payload = load_system_index(system_index_path)
    else:
        index_payload = build_system_index(
            "https://world-api-utopia.uat.pub.evefrontier.com",
            page_size=1000,
            map_objects_db=Path("/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/raw/mapObjects.db"),
        )
    source_matches = search_system_index(index_payload, source, limit=5)
    destination_matches = search_system_index(index_payload, destination, limit=5)
    source_match = pick_best_match(source_matches)
    destination_match = pick_best_match(destination_matches)

    _, auth_report = resolve_world_api_auth(probe_world_api=False)
    runtime = auth_report.get("runtime", {})
    contracts = summarize_gate_contracts()

    blocked_by = []
    if not source_match:
        blocked_by.append("source_system_not_resolved")
    if not destination_match:
        blocked_by.append("destination_system_not_resolved")
    if source_match and source_match.get("static_gate_count", 0) <= 0:
        blocked_by.append("source_system_has_no_static_gate_evidence")
    if destination_match and destination_match.get("static_gate_count", 0) <= 0:
        blocked_by.append("destination_system_has_no_static_gate_evidence")

    blocked_by.extend(
        [
            "missing_live_gate_identifiers",
            "missing_character_identifier",
        ]
    )
    if not runtime.get("utopia_client_running"):
        blocked_by.append("utopia_client_not_running")
    if not runtime.get("zk_signer_running"):
        blocked_by.append("zk_signer_not_running")

    ready_for_prepared_transaction = not {
        "source_system_not_resolved",
        "destination_system_not_resolved",
    } & set(blocked_by)

    return {
        "command": {
            "name": "/move",
            "source_query": source,
            "destination_query": destination,
        },
        "resolution": {
            "source": summarize_match(source_match),
            "destination": summarize_match(destination_match),
            "source_candidates": [summarize_match(match) for match in source_matches],
            "destination_candidates": [summarize_match(match) for match in destination_matches],
        },
        "runtime": runtime,
        "contracts": contracts,
        "readiness": {
            "ready_for_system_resolution": source_match is not None and destination_match is not None,
            "ready_for_prepared_transaction_lookup": ready_for_prepared_transaction,
            "ready_for_submission": False,
        },
        "blocked_by": blocked_by,
        "next_step": "Use the official logged-in wallet flow or a captured live API exchange to resolve source_gate, destination_gate, and character identifiers before calling PrepareJumpTransactionRequest.",
    }


def main() -> int:
    args = parse_args()
    result = build_move_plan(args.source, args.destination, system_index_path=args.system_index.expanduser().resolve())
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

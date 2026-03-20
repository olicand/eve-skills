#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auth_session import resolve_world_api_auth
from build_system_search_index import build_system_index
from move_transaction_flow import build_move_plan
from world_api_client import (
    DEFAULT_SYSTEM_INDEX_PATH,
    DEFAULT_WORLD_API_BASE_URL,
    WorldApiClient,
    load_system_index,
    search_system_index,
)


DEFAULT_CONTRACTS_OUTPUT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/metadata/player_skill_contracts.json"
)
DEFAULT_PLAYER_COMMANDS_REPORT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/player_commands.md"
)
DEFAULT_MOVE_AUTH_REPORT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/move_auth_flow.md"
)


def get_player_skill_contracts() -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "commands": [
            {
                "name": "/system find",
                "parameters": ["name"],
                "public": True,
                "auth_required": False,
                "dependencies": ["/v2/solarsystems", "system_search_index.json"],
                "output": "Matched solar systems with static gate hints.",
            },
            {
                "name": "/ship info",
                "parameters": ["id"],
                "public": True,
                "auth_required": False,
                "dependencies": ["/v2/ships/{id}"],
                "output": "Ship detail JSON from the public World API.",
            },
            {
                "name": "/jump-history",
                "parameters": [],
                "public": False,
                "auth_required": True,
                "dependencies": ["/v2/characters/me/jumps", "World API bearer token"],
                "output": "Current character jump history.",
            },
            {
                "name": "/move",
                "parameters": ["from", "to"],
                "public": False,
                "auth_required": True,
                "dependencies": [
                    "system_search_index.json",
                    "eve.assembly.gate.api.PrepareJumpTransactionRequest",
                    "live source_gate/destination_gate identifiers",
                    "character identifier",
                    "wallet or sponsored transaction signing flow",
                ],
                "output": "Prepared jump transaction plan or a blocked-by report.",
            },
        ],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def translate_skill_argv(argv: list[str]) -> list[str]:
    if len(argv) >= 2 and argv[0] == "/system" and argv[1] == "find":
        return ["system-find", *argv[2:]]
    if len(argv) >= 2 and argv[0] == "/ship" and argv[1] == "info":
        return ["ship-info", *argv[2:]]
    if len(argv) >= 1 and argv[0] == "/jump-history":
        return ["jump-history", *argv[1:]]
    if len(argv) >= 1 and argv[0] == "/move":
        return ["move", *argv[1:]]
    return argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Player-facing EVE Frontier skill commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    system_find = subparsers.add_parser("system-find", help="Resolve solar systems by name.")
    system_find.add_argument("name", nargs="+", help="Solar system name to search.")
    system_find.add_argument("--base-url", default=DEFAULT_WORLD_API_BASE_URL, help="World API base URL.")
    system_find.add_argument("--system-index", type=Path, default=DEFAULT_SYSTEM_INDEX_PATH, help="system_search_index.json path.")
    system_find.add_argument("--rebuild-index", action="store_true", help="Refresh the local system index from the public World API.")
    system_find.add_argument("--limit", type=int, default=10, help="Maximum matches to return.")

    ship_info = subparsers.add_parser("ship-info", help="Get a public ship detail.")
    ship_info.add_argument("ship_id", type=int, help="Ship type ID.")
    ship_info.add_argument("--base-url", default=DEFAULT_WORLD_API_BASE_URL, help="World API base URL.")

    jump_history = subparsers.add_parser("jump-history", help="Get jump history with local auth probing.")
    jump_history.add_argument("--base-url", default=DEFAULT_WORLD_API_BASE_URL, help="World API base URL.")
    jump_history.add_argument("--bearer-token", default="", help="Explicit World API bearer token override.")

    move = subparsers.add_parser("move", help="Build a jump transaction plan.")
    move.add_argument("source", help="Source solar system name.")
    move.add_argument("destination", help="Destination solar system name.")
    move.add_argument("--system-index", type=Path, default=DEFAULT_SYSTEM_INDEX_PATH, help="system_search_index.json path.")

    contracts = subparsers.add_parser("write-contracts", help="Write player_skill_contracts.json.")
    contracts.add_argument("--output", type=Path, default=DEFAULT_CONTRACTS_OUTPUT, help="Output JSON path.")
    contracts.add_argument(
        "--commands-report",
        type=Path,
        default=DEFAULT_PLAYER_COMMANDS_REPORT,
        help="Markdown report path for player commands.",
    )
    contracts.add_argument(
        "--move-auth-report",
        type=Path,
        default=DEFAULT_MOVE_AUTH_REPORT,
        help="Markdown report path for move/jump auth notes.",
    )

    return parser


def ensure_system_index(path: Path, *, base_url: str, rebuild: bool) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if rebuild or not resolved.exists():
        payload = build_system_index(base_url, page_size=1000, map_objects_db=Path("/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/raw/mapObjects.db"))
        write_json(resolved, payload)
        return payload
    return load_system_index(resolved)


def handle_system_find(args: argparse.Namespace) -> dict[str, Any]:
    query = " ".join(args.name)
    index_payload = ensure_system_index(args.system_index, base_url=args.base_url, rebuild=args.rebuild_index)
    matches = search_system_index(index_payload, query, limit=args.limit)
    return {
        "command": "/system find",
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }


def handle_ship_info(args: argparse.Namespace) -> dict[str, Any]:
    client = WorldApiClient(base_url=args.base_url)
    return {
        "command": "/ship info",
        "ship_id": args.ship_id,
        "ship": client.get_ship(args.ship_id),
    }


def handle_jump_history(args: argparse.Namespace) -> dict[str, Any]:
    bearer_token, auth_report = resolve_world_api_auth(
        base_url=args.base_url,
        explicit_bearer_token=args.bearer_token,
        probe_world_api=True,
    )
    if not bearer_token:
        return {
            "command": "/jump-history",
            "ok": False,
            "reason": "no_valid_world_api_bearer",
            "auth_report": auth_report,
        }

    client = WorldApiClient(base_url=args.base_url, bearer_token=bearer_token)
    return {
        "command": "/jump-history",
        "ok": True,
        "jump_history": client.get_jump_history(),
        "auth_report": auth_report,
    }


def handle_move(args: argparse.Namespace) -> dict[str, Any]:
    ensure_system_index(args.system_index, base_url=DEFAULT_WORLD_API_BASE_URL, rebuild=False)
    return build_move_plan(args.source, args.destination, system_index_path=args.system_index.expanduser().resolve())


def handle_write_contracts(args: argparse.Namespace) -> dict[str, Any]:
    payload = get_player_skill_contracts()
    output_path = args.output.expanduser().resolve()
    commands_report_path = args.commands_report.expanduser().resolve()
    move_auth_report_path = args.move_auth_report.expanduser().resolve()

    write_json(output_path, payload)

    commands_report_path.parent.mkdir(parents=True, exist_ok=True)
    commands_report_path.write_text(
        "# Player Commands\n\n"
        "These are the current player-facing skill commands bundled in this repo.\n\n"
        "- `/system find <name>`: public World API lookup plus local system index.\n"
        "- `/ship info <id>`: public World API ship detail lookup.\n"
        "- `/jump-history`: protected World API path, currently dependent on discovering a valid World API bearer.\n"
        "- `/move <from> <to>`: system resolution plus jump transaction contract summary; still blocked on live gate and character identifiers.\n"
    )

    move_auth_report_path.parent.mkdir(parents=True, exist_ok=True)
    move_auth_report_path.write_text(
        "# Move And Auth Flow\n\n"
        "- The local Frontier client session can expose an SSO token and refresh token.\n"
        "- Refresh-token exchange currently succeeds, but the resulting OAuth tokens are still rejected by `GET /v2/characters/me/jumps`.\n"
        "- `/move` can already resolve systems and load `PrepareJumpTransactionRequest`, but it still needs live `source_gate`, `destination_gate`, and `character` identifiers.\n"
        "- The next capture target is the official browser or launcher flow that converts the logged-in session into the World API-specific bearer or transaction signing context.\n"
    )

    return {
        "command": "write-contracts",
        "output": str(output_path),
        "commands_report": str(commands_report_path),
        "move_auth_report": str(move_auth_report_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(translate_skill_argv(list(argv or __import__("sys").argv[1:])))

    if args.command == "system-find":
        result = handle_system_find(args)
    elif args.command == "ship-info":
        result = handle_ship_info(args)
    elif args.command == "jump-history":
        result = handle_jump_history(args)
    elif args.command == "move":
        result = handle_move(args)
    elif args.command == "write-contracts":
        result = handle_write_contracts(args)
    else:
        raise SystemExit(f"Unknown command {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

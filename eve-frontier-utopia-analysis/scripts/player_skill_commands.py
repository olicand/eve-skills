#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auth_session import resolve_world_api_auth
from build_system_search_index import build_system_index
from launcher_local_api import (
    DEFAULT_LOCAL_LAUNCHER_BASE_URL,
    DEFAULT_SIGNUP_SERVICE_BASE_URL,
    LauncherLocalApiClient,
    exchange_signup_single_use_token,
    mask_identifier,
)
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
DEFAULT_AGENT_INTEGRATION_REPORT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/agent_skill_integration.md"
)
DEFAULT_USER_SKILL_CATALOG_OUTPUT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/metadata/user_skill_catalog.json"
)
DEFAULT_USER_SKILL_DELIVERY_REPORT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/user_skill_delivery.md"
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
                "execution_tier": "public_read",
                "recommended_agent_exposure": "enable_for_all_players",
                "status": "ready_now",
                "dependencies": ["/v2/solarsystems", "system_search_index.json"],
                "runtime_requirements": ["World API reachable", "local system index present or rebuildable"],
                "output": "Matched solar systems with static gate hints.",
            },
            {
                "name": "/ship info",
                "parameters": ["id"],
                "public": True,
                "auth_required": False,
                "execution_tier": "public_read",
                "recommended_agent_exposure": "enable_for_all_players",
                "status": "ready_now",
                "dependencies": ["/v2/ships/{id}"],
                "runtime_requirements": ["World API reachable", "valid ship identifier"],
                "output": "Ship detail JSON from the public World API.",
            },
            {
                "name": "/jump-history",
                "parameters": [],
                "public": False,
                "auth_required": True,
                "execution_tier": "protected_read",
                "recommended_agent_exposure": "hold_until_world_api_bearer_source_is_confirmed",
                "status": "blocked_on_auth_mapping",
                "dependencies": ["/v2/characters/me/jumps", "World API bearer token"],
                "runtime_requirements": [
                    "running logged-in Utopia session",
                    "World API bearer accepted by /v2/characters/me/jumps",
                ],
                "output": "Current character jump history.",
            },
            {
                "name": "/move",
                "parameters": ["from", "to"],
                "public": False,
                "auth_required": True,
                "execution_tier": "in_game_transaction",
                "recommended_agent_exposure": "gate_behind_live_entity_resolution_and_signing",
                "status": "blocked_on_live_ids_and_transaction_execution",
                "dependencies": [
                    "system_search_index.json",
                    "eve.assembly.gate.api.PrepareJumpTransactionRequest",
                    "live source_gate/destination_gate identifiers",
                    "character identifier",
                    "wallet or sponsored transaction signing flow",
                ],
                "runtime_requirements": [
                    "running Utopia client",
                    "running zk_signer",
                    "resolved source gate identifier",
                    "resolved destination gate identifier",
                    "resolved character identifier",
                    "prepared or sponsored transaction execution path",
                ],
                "output": "Prepared jump transaction plan or a blocked-by report.",
            },
            {
                "name": "/launcher status",
                "parameters": [],
                "public": True,
                "auth_required": False,
                "execution_tier": "local_runtime_control",
                "recommended_agent_exposure": "enable_for_local_operator_tools",
                "status": "ready_now",
                "dependencies": ["http://localhost:3275/status"],
                "runtime_requirements": ["Frontier launcher running on localhost:3275"],
                "output": "Live EVE Frontier launcher status from the local HTTP bridge.",
            },
            {
                "name": "/launcher focus",
                "parameters": [],
                "public": True,
                "auth_required": False,
                "execution_tier": "local_runtime_control",
                "recommended_agent_exposure": "enable_for_local_operator_tools",
                "status": "ready_now",
                "dependencies": ["http://localhost:3275/focus"],
                "runtime_requirements": ["Frontier launcher running on localhost:3275"],
                "output": "Bring the launcher window to the foreground via the local HTTP bridge.",
            },
            {
                "name": "/launcher journey",
                "parameters": ["journeyId"],
                "public": True,
                "auth_required": False,
                "execution_tier": "local_runtime_control",
                "recommended_agent_exposure": "enable_for_local_operator_tools",
                "status": "ready_now",
                "dependencies": ["http://localhost:3275/journey"],
                "runtime_requirements": ["Frontier launcher running on localhost:3275", "journeyId value"],
                "output": "Submit a journey ID into the local launcher state.",
            },
            {
                "name": "/launcher connect",
                "parameters": ["singleUseToken"],
                "public": False,
                "auth_required": True,
                "execution_tier": "launcher_auth_bridge",
                "recommended_agent_exposure": "operator_only_and_one_time_token_sensitive",
                "status": "needs_official_connect_token_source",
                "dependencies": [
                    "http://localhost:3275/connect",
                    "https://signup.eveonline.com/api/v2/token/launcher",
                    "official connect/signup single-use token",
                ],
                "runtime_requirements": [
                    "Frontier launcher running on localhost:3275",
                    "official single-use connect token",
                ],
                "output": "Forward a single-use token into the launcher bridge and optionally probe the exchanged access token against World API auth.",
            },
        ],
    }


def get_user_skill_catalog() -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "skills": [
            {
                "skill_id": "system_find",
                "display_name": "System Find",
                "user_goal": "Find a solar system by player-facing name.",
                "agent_entrypoint": "/system find <name>",
                "status": "ready_now",
                "player_exposure": "public",
                "requires_login": False,
                "requires_live_game_context": False,
                "examples": [
                    "/system find A 2560",
                    "/system find M 974",
                ],
                "notes": [
                    "Uses the public World API plus the local system index.",
                    "Safe to expose directly to players.",
                ],
            },
            {
                "skill_id": "ship_info",
                "display_name": "Ship Info",
                "user_goal": "Look up a ship by identifier.",
                "agent_entrypoint": "/ship info <id>",
                "status": "ready_now",
                "player_exposure": "public",
                "requires_login": False,
                "requires_live_game_context": False,
                "examples": [
                    "/ship info 81609",
                ],
                "notes": [
                    "Uses the public World API.",
                    "Safe to expose directly to players.",
                ],
            },
            {
                "skill_id": "jump_history",
                "display_name": "Jump History",
                "user_goal": "Read the logged-in character jump history.",
                "agent_entrypoint": "/jump-history",
                "status": "blocked_on_auth_mapping",
                "player_exposure": "disabled_until_bearer_source_is_verified",
                "requires_login": True,
                "requires_live_game_context": True,
                "examples": [
                    "/jump-history",
                ],
                "notes": [
                    "Needs a World API bearer accepted by /v2/characters/me/jumps.",
                    "Current local SSO and OAuth tokens are rejected by the endpoint.",
                ],
            },
            {
                "skill_id": "move",
                "display_name": "Move",
                "user_goal": "Move between systems through the in-game jump transaction flow.",
                "agent_entrypoint": "/move <from> <to>",
                "status": "blocked_on_live_ids_and_transaction_execution",
                "player_exposure": "disabled_until_live_entity_resolution_is_ready",
                "requires_login": True,
                "requires_live_game_context": True,
                "examples": [
                    "/move A 2560 M 974",
                ],
                "notes": [
                    "Needs live source_gate, destination_gate, and character identifiers.",
                    "Also needs a prepared or sponsored transaction signing path.",
                ],
            },
            {
                "skill_id": "launcher_status",
                "display_name": "Launcher Status",
                "user_goal": "Read the local launcher state on this machine.",
                "agent_entrypoint": "/launcher status",
                "status": "ready_now",
                "player_exposure": "operator_only",
                "requires_login": False,
                "requires_live_game_context": False,
                "examples": [
                    "/launcher status",
                ],
                "notes": [
                    "This is a localhost bridge call, not a remote player capability.",
                ],
            },
            {
                "skill_id": "launcher_focus",
                "display_name": "Launcher Focus",
                "user_goal": "Bring the local launcher to the foreground.",
                "agent_entrypoint": "/launcher focus",
                "status": "ready_now",
                "player_exposure": "operator_only",
                "requires_login": False,
                "requires_live_game_context": False,
                "examples": [
                    "/launcher focus",
                ],
                "notes": [
                    "This is a localhost bridge call, not a remote player capability.",
                ],
            },
            {
                "skill_id": "launcher_journey",
                "display_name": "Launcher Journey",
                "user_goal": "Write a journey identifier into the local launcher state.",
                "agent_entrypoint": "/launcher journey <journeyId>",
                "status": "ready_now",
                "player_exposure": "operator_only",
                "requires_login": False,
                "requires_live_game_context": False,
                "examples": [
                    "/launcher journey <journeyId>",
                ],
                "notes": [
                    "This is a localhost bridge call, not a remote player capability.",
                ],
            },
            {
                "skill_id": "launcher_connect",
                "display_name": "Launcher Connect",
                "user_goal": "Forward an official one-time connect token to the local launcher bridge.",
                "agent_entrypoint": "/launcher connect <singleUseToken>",
                "status": "needs_official_connect_token_source",
                "player_exposure": "operator_only_sensitive",
                "requires_login": True,
                "requires_live_game_context": False,
                "examples": [
                    "/launcher connect <singleUseToken>",
                ],
                "notes": [
                    "Depends on an official one-time token source.",
                    "Should not be exposed as a normal player-facing skill.",
                ],
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
    if len(argv) >= 2 and argv[0] == "/launcher" and argv[1] == "status":
        return ["launcher-status", *argv[2:]]
    if len(argv) >= 2 and argv[0] == "/launcher" and argv[1] == "focus":
        return ["launcher-focus", *argv[2:]]
    if len(argv) >= 2 and argv[0] == "/launcher" and argv[1] == "journey":
        return ["launcher-journey", *argv[2:]]
    if len(argv) >= 2 and argv[0] == "/launcher" and argv[1] == "connect":
        return ["launcher-connect", *argv[2:]]
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

    launcher_status = subparsers.add_parser("launcher-status", help="Read the live local launcher HTTP status.")
    launcher_status.add_argument(
        "--launcher-base-url",
        default=DEFAULT_LOCAL_LAUNCHER_BASE_URL,
        help="Local launcher API base URL.",
    )

    launcher_focus = subparsers.add_parser("launcher-focus", help="Focus the launcher via the local HTTP bridge.")
    launcher_focus.add_argument(
        "--launcher-base-url",
        default=DEFAULT_LOCAL_LAUNCHER_BASE_URL,
        help="Local launcher API base URL.",
    )

    launcher_journey = subparsers.add_parser("launcher-journey", help="Submit a journey ID to the local launcher bridge.")
    launcher_journey.add_argument("journey_id", help="Journey ID to submit to /journey.")
    launcher_journey.add_argument(
        "--launcher-base-url",
        default=DEFAULT_LOCAL_LAUNCHER_BASE_URL,
        help="Local launcher API base URL.",
    )

    launcher_connect = subparsers.add_parser(
        "launcher-connect",
        help="POST a single-use token into the local launcher and optionally probe the signup token exchange.",
    )
    launcher_connect.add_argument("single_use_token", help="Official single-use token for the launcher connect flow.")
    launcher_connect.add_argument("--journey-id", default="", help="Optional journeyId to forward to the launcher.")
    launcher_connect.add_argument(
        "--launcher-base-url",
        default=DEFAULT_LOCAL_LAUNCHER_BASE_URL,
        help="Local launcher API base URL.",
    )
    launcher_connect.add_argument(
        "--signup-base-url",
        default=DEFAULT_SIGNUP_SERVICE_BASE_URL,
        help="Signup service base URL used for token exchange probing.",
    )
    launcher_connect.add_argument(
        "--world-api-base-url",
        default=DEFAULT_WORLD_API_BASE_URL,
        help="World API base URL for optional bearer probing.",
    )
    launcher_connect.add_argument(
        "--skip-local-connect",
        action="store_true",
        help="Do not POST to the live launcher /connect route.",
    )
    launcher_connect.add_argument(
        "--exchange-signup-token",
        action="store_true",
        help="Directly exchange the single-use token against the signup service. This may consume one-time tokens before the live launcher does.",
    )
    launcher_connect.add_argument(
        "--skip-world-api-probe",
        action="store_true",
        help="When exchanging the single-use token, do not probe the resulting access token against /v2/characters/me/jumps.",
    )

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
    contracts.add_argument(
        "--agent-integration-report",
        type=Path,
        default=DEFAULT_AGENT_INTEGRATION_REPORT,
        help="Markdown report path for Agent-facing skill integration guidance.",
    )
    contracts.add_argument(
        "--user-skill-catalog-output",
        type=Path,
        default=DEFAULT_USER_SKILL_CATALOG_OUTPUT,
        help="Output JSON path for the user-facing skill catalog.",
    )
    contracts.add_argument(
        "--user-skill-delivery-report",
        type=Path,
        default=DEFAULT_USER_SKILL_DELIVERY_REPORT,
        help="Markdown report path for user-facing skill delivery guidance.",
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


def handle_launcher_status(args: argparse.Namespace) -> dict[str, Any]:
    client = LauncherLocalApiClient(base_url=args.launcher_base_url)
    status = client.get_status()
    return {
        "command": "/launcher status",
        "launcher": {
            "name": status.get("name"),
            "version": status.get("version"),
            "uptime": status.get("uptime"),
            "creationTime": status.get("creationTime"),
            "journey_id": mask_identifier(status.get("journey")),
        },
    }


def handle_launcher_focus(args: argparse.Namespace) -> dict[str, Any]:
    client = LauncherLocalApiClient(base_url=args.launcher_base_url)
    return {
        "command": "/launcher focus",
        "result": client.focus(),
    }


def handle_launcher_journey(args: argparse.Namespace) -> dict[str, Any]:
    client = LauncherLocalApiClient(base_url=args.launcher_base_url)
    return {
        "command": "/launcher journey",
        "journey_id": mask_identifier(args.journey_id),
        "result": client.submit_journey(args.journey_id),
    }


def handle_launcher_connect(args: argparse.Namespace) -> dict[str, Any]:
    result: dict[str, Any] = {
        "command": "/launcher connect",
        "journey_id": mask_identifier(args.journey_id) if args.journey_id else None,
        "local_connect": None,
        "signup_exchange": None,
    }

    if not args.skip_local_connect:
        client = LauncherLocalApiClient(base_url=args.launcher_base_url)
        result["local_connect"] = client.connect(args.single_use_token, journey_id=args.journey_id)

    if args.exchange_signup_token:
        result["signup_exchange"] = exchange_signup_single_use_token(
            args.single_use_token,
            signup_base_url=args.signup_base_url,
            world_api_base_url=args.world_api_base_url,
            probe_world_api=not args.skip_world_api_probe,
        )

    if args.skip_local_connect and not args.exchange_signup_token:
        result["note"] = "Nothing was executed because both local connect and signup exchange were disabled."

    return result


def handle_write_contracts(args: argparse.Namespace) -> dict[str, Any]:
    payload = get_player_skill_contracts()
    user_skill_catalog = get_user_skill_catalog()
    output_path = args.output.expanduser().resolve()
    commands_report_path = args.commands_report.expanduser().resolve()
    move_auth_report_path = args.move_auth_report.expanduser().resolve()
    agent_integration_report_path = args.agent_integration_report.expanduser().resolve()
    user_skill_catalog_output_path = args.user_skill_catalog_output.expanduser().resolve()
    user_skill_delivery_report_path = args.user_skill_delivery_report.expanduser().resolve()

    write_json(output_path, payload)
    write_json(user_skill_catalog_output_path, user_skill_catalog)

    commands_report_path.parent.mkdir(parents=True, exist_ok=True)
    commands_report_path.write_text(
        "# Player Commands\n\n"
        "These are the current player-facing skill commands bundled in this repo.\n\n"
        "- `/system find <name>`: public World API lookup plus local system index.\n"
        "- `/ship info <id>`: public World API ship detail lookup.\n"
        "- `/jump-history`: protected World API path, currently dependent on discovering a valid World API bearer.\n"
        "- `/move <from> <to>`: system resolution plus jump transaction contract summary; still blocked on live gate and character identifiers.\n"
        "- `/launcher status`: read the local Frontier launcher status from `http://localhost:3275/status`.\n"
        "- `/launcher focus`: bring the launcher window to the foreground via `http://localhost:3275/focus`.\n"
        "- `/launcher journey <journeyId>`: submit a journey identifier to `http://localhost:3275/journey`.\n"
        "- `/launcher connect <singleUseToken>`: forward a one-time signup/connect token to `http://localhost:3275/connect`.\n"
    )

    move_auth_report_path.parent.mkdir(parents=True, exist_ok=True)
    move_auth_report_path.write_text(
        "# Move And Auth Flow\n\n"
        "- The local Frontier client session can expose an SSO token and refresh token.\n"
        "- Refresh-token exchange currently succeeds, but the resulting OAuth tokens are still rejected by `GET /v2/characters/me/jumps`.\n"
        "- The launcher also exposes a local HTTP bridge on `http://localhost:3275` with `/status`, `/focus`, `/journey`, and `/connect`.\n"
        "- `POST /connect` accepts a `singleUseToken` and dispatches `signup/exchange-token` inside the launcher.\n"
        "- The launcher resolves that one-time token through `https://signup.eveonline.com/api/v2/token/launcher`, which returns an access/refresh/id token trio for launcher auth.\n"
        "- One-time signup/connect tokens may be consumed when exchanged, so test scripts should not assume the same token can be replayed safely against both the live launcher and a direct probe.\n"
        "- `/move` can already resolve systems and load `PrepareJumpTransactionRequest`, but it still needs live `source_gate`, `destination_gate`, and `character` identifiers.\n"
        "- The next capture target is the official browser or launcher flow that converts the logged-in session into the World API-specific bearer or transaction signing context.\n"
    )

    agent_integration_report_path.parent.mkdir(parents=True, exist_ok=True)
    agent_integration_report_path.write_text(
        "# Agent Skill Integration\n\n"
        "The right way to expose these commands through an Agent is to split them into three lanes.\n\n"
        "## Lane 1: Public Read Skills\n\n"
        "- `/system find <name>`: safe to expose directly to all players. It only depends on the public World API plus the local system index.\n"
        "- `/ship info <id>`: safe to expose directly to all players. It only depends on the public World API.\n\n"
        "## Lane 2: Local Runtime Control Skills\n\n"
        "- `/launcher status`: useful for operator tooling and local diagnostics.\n"
        "- `/launcher focus`: useful for operator tooling on the same machine.\n"
        "- `/launcher journey <journeyId>`: useful for local launcher state coordination.\n"
        "- These should not be treated as remote player abilities. They are host-local bridge calls to `localhost:3275`.\n\n"
        "## Lane 3: Logged-In Game Operation Skills\n\n"
        "- `/jump-history`: keep disabled until a real World API bearer source is captured and verified.\n"
        "- `/move <from> <to>`: keep behind a game-operation layer. This is not a plain HTTP lookup. It requires live `source_gate`, `destination_gate`, and `character` identifiers plus a working prepared/sponsored transaction execution path.\n"
        "- `/launcher connect <singleUseToken>`: treat as operator-only. It depends on an official one-time token source and should not be exposed as a normal player command.\n\n"
        "## Recommended Agent Contract\n\n"
        "- Expose Lane 1 immediately as player-facing skills.\n"
        "- Expose Lane 2 only to the local operator Agent running on the same machine as the launcher.\n"
        "- Hold Lane 3 behind runtime guards that check login state, live entity resolution, and signing readiness before the Agent can call them.\n\n"
        "## Current Readiness\n\n"
        "- Ready now: `/system find`, `/ship info`, `/launcher status`, `/launcher focus`, `/launcher journey`.\n"
        "- Blocked on auth mapping: `/jump-history`.\n"
        "- Blocked on live IDs and transaction execution: `/move`.\n"
        "- Sensitive operator bridge: `/launcher connect`.\n"
    )

    user_skill_delivery_report_path.parent.mkdir(parents=True, exist_ok=True)
    user_skill_delivery_report_path.write_text(
        "# User Skill Delivery\n\n"
        "The product goal is to expose EVE Frontier abilities as user-facing skills, not to expose raw transport or token plumbing.\n\n"
        "## Skills Ready For Players Now\n\n"
        "- `/system find <name>`: public lookup skill.\n"
        "- `/ship info <id>`: public lookup skill.\n\n"
        "## Skills Ready Only For Local Operator Agents\n\n"
        "- `/launcher status`\n"
        "- `/launcher focus`\n"
        "- `/launcher journey <journeyId>`\n"
        "- These are host-local bridge calls and should stay internal.\n\n"
        "## Skills Not Ready To Expose Yet\n\n"
        "- `/jump-history`: blocked on a World API bearer source that the endpoint actually accepts.\n"
        "- `/move <from> <to>`: blocked on live gate and character identifiers plus transaction execution readiness.\n"
        "- `/launcher connect <singleUseToken>`: depends on an official one-time token source and should stay operator-only.\n\n"
        "## Product Guidance\n\n"
        "- Build the player experience around intent-level commands.\n"
        "- Keep raw auth exchange, localhost bridge calls, and token-sensitive flows behind internal tooling.\n"
        "- Only expose action skills after runtime guards and entity-resolution checks are proven.\n"
    )

    return {
        "command": "write-contracts",
        "output": str(output_path),
        "commands_report": str(commands_report_path),
        "move_auth_report": str(move_auth_report_path),
        "agent_integration_report": str(agent_integration_report_path),
        "user_skill_catalog_output": str(user_skill_catalog_output_path),
        "user_skill_delivery_report": str(user_skill_delivery_report_path),
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
    elif args.command == "launcher-status":
        result = handle_launcher_status(args)
    elif args.command == "launcher-focus":
        result = handle_launcher_focus(args)
    elif args.command == "launcher-journey":
        result = handle_launcher_journey(args)
    elif args.command == "launcher-connect":
        result = handle_launcher_connect(args)
    elif args.command == "write-contracts":
        result = handle_write_contracts(args)
    else:
        raise SystemExit(f"Unknown command {args.command}")

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

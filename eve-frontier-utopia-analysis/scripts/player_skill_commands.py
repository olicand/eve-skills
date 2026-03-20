#!/usr/bin/env python3
"""Player-facing EVE Frontier skill commands — cloud-based, login required.

ALL skills are cloud-based and require authentication before use.
Every command checks for valid credentials before executing.

Interfaces (ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world):
- Write path:  Sui TypeScript SDK → build Transaction → sign via EVE Vault → submit
- Read path:   World API REST / Sui GraphQL / gRPC → query on-chain state
- Auth:        EVE Vault browser extension + SSO OAuth2 bearer
- Sandbox:     /moveme, /giveitem are in-game chat commands only
               (ref: https://docs.evefrontier.com/troubleshooting/sandbox-access)

No local process detection, no localhost calls, no AppleScript.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from auth_flow import (
    AuthFlowClient,
    mask_identifier,
    resolve_world_api_auth,
    summarize_claims,
)
from game_api_client import (
    DEFAULT_ENV,
    AuthenticationRequired,
    GameClient,
    WorldApiClient,
    get_env_config,
    request_json,
)
from smart_assembly_api import (
    build_jump_transaction_plan,
    build_move_plan_remote,
    list_smart_assemblies,
    list_smart_gates,
    list_smart_storage_units,
    list_smart_turrets,
    query_character,
    query_jump_events,
    query_kill_events,
    query_killmails,
    query_smart_assembly,
    query_smart_gate,
)
from world_api_client import (
    DEFAULT_SYSTEM_INDEX_PATH,
    load_system_index,
    normalize_name,
    search_system_index,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CONTRACTS_OUTPUT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/metadata/player_skill_contracts.json"
)
DEFAULT_USER_SKILL_CATALOG_OUTPUT = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/metadata/user_skill_catalog.json"
)

COMMON_SANDBOX_ITEMS = {
    "carbon weave": 84210,
    "thermal composites": 88561,
    "printed circuits": 84180,
    "reinforced alloys": 84182,
    "feldspar crystals": 77800,
    "hydrated sulfide matrix": 77811,
    "building foam": 89089,
}


# ---------------------------------------------------------------------------
# Skill contract / catalog generators
# ---------------------------------------------------------------------------

def get_player_skill_contracts() -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "cloud_based_login_required",
        "auth_methods": [
            "EVE Vault browser extension (wallet: --wallet / EVE_FRONTIER_WALLET)",
            "SSO OAuth2 bearer token (--bearer-token / EVE_FRONTIER_BEARER)",
            "Refresh token exchange (EVE_FRONTIER_REFRESH_TOKEN + EVE_FRONTIER_CLIENT_ID)",
        ],
        "interfaces": {
            "write": "Sui TypeScript SDK -> build Transaction -> sign via EVE Vault -> submit",
            "read": "World API REST / Sui GraphQL / gRPC -> query on-chain state",
            "sandbox": "In-game chat commands only (/moveme, /giveitem)",
        },
        "references": {
            "interfacing": "https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world",
            "sandbox_access": "https://docs.evefrontier.com/troubleshooting/sandbox-access",
            "eve_vault": "https://docs.evefrontier.com/eve-vault/browser-extension",
            "world_api_docs": "https://world-api-utopia.uat.pub.evefrontier.com/docs/index.html",
            "graphql_ide": "https://graphql.testnet.sui.io/graphql",
        },
        "commands": [
            {
                "name": "/moveme",
                "auth_required": True,
                "execution_tier": "sandbox_chat_command",
                "interface": "message_bridge + in-game chat",
                "doc": "https://docs.evefrontier.com/troubleshooting/sandbox-access",
            },
            {
                "name": "/giveitem",
                "parameters": ["item", "quantity"],
                "auth_required": True,
                "execution_tier": "sandbox_chat_command",
                "interface": "message_bridge + in-game chat",
                "doc": "https://docs.evefrontier.com/troubleshooting/sandbox-access",
            },
            {
                "name": "/system find",
                "parameters": ["name"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/solarsystems)",
            },
            {
                "name": "/system info",
                "parameters": ["system_id"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/solarsystems/{id} — includes gateLinks)",
            },
            {
                "name": "/ship info",
                "parameters": ["id"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/ships/{id} — detailed stats)",
            },
            {
                "name": "/ship list",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/ships)",
            },
            {
                "name": "/type search",
                "parameters": ["name"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/types — 390 items/modules)",
            },
            {
                "name": "/type info",
                "parameters": ["type_id"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/types/{id} — with attributes)",
            },
            {
                "name": "/type list",
                "parameters": ["--category", "--limit", "--offset"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/types)",
            },
            {
                "name": "/constellation find",
                "parameters": ["name"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/constellations — 2213 total)",
            },
            {
                "name": "/constellation info",
                "parameters": ["constellation_id"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/constellations/{id} — with solarSystems)",
            },
            {
                "name": "/tribe list",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/tribes)",
            },
            {
                "name": "/tribe info",
                "parameters": ["tribe_id"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/tribes/{id} — tax, URL)",
            },
            {
                "name": "/jump-history",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/characters/me/jumps, bearer required)",
            },
            {
                "name": "/jump detail",
                "parameters": ["jump_id", "--format json|pod"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST /v2/characters/me/jumps/{id}, supports POD)",
            },
            {
                "name": "/pod verify",
                "parameters": ["pod_json"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (POST /v2/pod/verify)",
            },
            {
                "name": "/move",
                "parameters": ["from", "to", "--source-gate", "--dest-gate", "--character"],
                "auth_required": True,
                "execution_tier": "write",
                "interface": "Sui GraphQL (read) + Sui Transaction (write via EVE Vault)",
                "doc": "https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world",
            },
            {
                "name": "/gate info",
                "parameters": ["address"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "SuiGraphQLClient",
            },
            {
                "name": "/gate list",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "SuiGraphQLClient",
            },
            {
                "name": "/assembly info",
                "parameters": ["address"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient + SuiGraphQLClient",
            },
            {
                "name": "/assembly list",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST)",
            },
            {
                "name": "/character info",
                "parameters": ["wallet_address"],
                "auth_required": True,
                "execution_tier": "read",
                "interface": "SuiGraphQLClient",
                "doc": "https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world",
            },
            {
                "name": "/events jumps",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "SuiGraphQLClient (events)",
            },
            {
                "name": "/events kills",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "SuiGraphQLClient (events)",
            },
            {
                "name": "/killmails",
                "auth_required": True,
                "execution_tier": "read",
                "interface": "WorldApiClient (REST)",
            },
            {
                "name": "/launcher status",
                "auth_required": True,
                "execution_tier": "gateway",
                "interface": "GatewayRpcClient (ConnectRPC)",
            },
            {
                "name": "/launcher focus",
                "auth_required": True,
                "execution_tier": "gateway",
                "interface": "GatewayRpcClient (ConnectRPC)",
            },
            {
                "name": "/launcher journey",
                "parameters": ["journeyId"],
                "auth_required": True,
                "execution_tier": "gateway",
                "interface": "GatewayRpcClient (ConnectRPC)",
            },
            {
                "name": "/launcher connect",
                "parameters": ["singleUseToken"],
                "auth_required": True,
                "execution_tier": "gateway",
                "interface": "GatewayRpcClient (ConnectRPC)",
            },
            {
                "name": "/auth resolve",
                "auth_required": False,
                "execution_tier": "auth",
                "interface": "AuthFlowClient (SSO + Auth Companion)",
            },
        ],
    }


def get_user_skill_catalog() -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "remote_api_only",
        "skills": [
            {
                "skill_id": "moveme",
                "display_name": "Move Me",
                "user_goal": "Send /moveme to the game via message bridge.",
                "agent_entrypoint": "/moveme",
                "status": "ready_via_message_bridge",
                "interface": "message_bridge",
            },
            {
                "skill_id": "giveitem",
                "display_name": "Give Item",
                "user_goal": "Send /giveitem to the game via message bridge.",
                "agent_entrypoint": "/giveitem <item> <quantity>",
                "status": "ready_via_message_bridge",
                "interface": "message_bridge",
            },
            {
                "skill_id": "system_find",
                "display_name": "System Find",
                "user_goal": "Find a solar system by name via World API.",
                "agent_entrypoint": "/system find <name>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "system_info",
                "display_name": "System Info",
                "user_goal": "Get detailed solar system info including gate links.",
                "agent_entrypoint": "/system info <id>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "ship_info",
                "display_name": "Ship Info",
                "user_goal": "Look up a ship by ID — detailed stats, slots, resistances.",
                "agent_entrypoint": "/ship info <id>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "ship_list",
                "display_name": "Ship List",
                "user_goal": "List all available ships (11 total).",
                "agent_entrypoint": "/ship list",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "type_search",
                "display_name": "Type Search",
                "user_goal": "Search items/modules by name (390 types total).",
                "agent_entrypoint": "/type search <name>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "type_info",
                "display_name": "Type Info",
                "user_goal": "Get detailed type info with attributes.",
                "agent_entrypoint": "/type info <id>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "type_list",
                "display_name": "Type List",
                "user_goal": "List all types, optionally filtered by category.",
                "agent_entrypoint": "/type list [--category Module]",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "constellation_find",
                "display_name": "Constellation Find",
                "user_goal": "Search constellations by name/ID (2213 total).",
                "agent_entrypoint": "/constellation find <name>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "constellation_info",
                "display_name": "Constellation Info",
                "user_goal": "Get constellation detail with its solar systems.",
                "agent_entrypoint": "/constellation info <id>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "tribe_list",
                "display_name": "Tribe List",
                "user_goal": "List all tribes in the game.",
                "agent_entrypoint": "/tribe list",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "tribe_info",
                "display_name": "Tribe Info",
                "user_goal": "Get tribe detail including tax rate and URL.",
                "agent_entrypoint": "/tribe info <id>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "jump_history",
                "display_name": "Jump History",
                "user_goal": "Read character jump history via World API (bearer required).",
                "agent_entrypoint": "/jump-history",
                "status": "ready_with_bearer",
                "interface": "world_api",
            },
            {
                "skill_id": "jump_detail",
                "display_name": "Jump Detail",
                "user_goal": "Get a single jump by ID (supports POD format).",
                "agent_entrypoint": "/jump detail <id> [--format pod]",
                "status": "ready_with_bearer",
                "interface": "world_api",
            },
            {
                "skill_id": "pod_verify",
                "display_name": "POD Verify",
                "user_goal": "Verify a Provable Object Datatype.",
                "agent_entrypoint": "/pod verify <json>",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "move",
                "display_name": "Move",
                "user_goal": "Build a Sui jump transaction from source to destination gate.",
                "agent_entrypoint": "/move <from> <to>",
                "status": "ready_with_chain_ids",
                "interface": "sui_graphql + world_api",
            },
            {
                "skill_id": "gate_info",
                "display_name": "Gate Info",
                "user_goal": "Query Smart Gate on-chain state.",
                "agent_entrypoint": "/gate info <address>",
                "status": "ready",
                "interface": "sui_graphql",
            },
            {
                "skill_id": "gate_list",
                "display_name": "Gate List",
                "user_goal": "List Smart Gates from the blockchain.",
                "agent_entrypoint": "/gate list",
                "status": "ready",
                "interface": "sui_graphql",
            },
            {
                "skill_id": "assembly_info",
                "display_name": "Assembly Info",
                "user_goal": "Query Smart Assembly details.",
                "agent_entrypoint": "/assembly info <address>",
                "status": "ready",
                "interface": "world_api + sui_graphql",
            },
            {
                "skill_id": "assembly_list",
                "display_name": "Assembly List",
                "user_goal": "List Smart Assemblies from World API.",
                "agent_entrypoint": "/assembly list",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "character_info",
                "display_name": "Character Info",
                "user_goal": "Query character by wallet address on-chain.",
                "agent_entrypoint": "/character info <wallet>",
                "status": "ready",
                "interface": "sui_graphql",
            },
            {
                "skill_id": "events_jumps",
                "display_name": "Jump Events",
                "user_goal": "Query recent Smart Gate jump events.",
                "agent_entrypoint": "/events jumps",
                "status": "ready",
                "interface": "sui_graphql",
            },
            {
                "skill_id": "events_kills",
                "display_name": "Kill Events",
                "user_goal": "Query recent Smart Turret kill events.",
                "agent_entrypoint": "/events kills",
                "status": "ready",
                "interface": "sui_graphql",
            },
            {
                "skill_id": "killmails",
                "display_name": "Killmails",
                "user_goal": "List killmails from World API.",
                "agent_entrypoint": "/killmails",
                "status": "ready",
                "interface": "world_api",
            },
            {
                "skill_id": "launcher_status",
                "display_name": "Launcher Status",
                "user_goal": "Get launcher status via gateway RPC.",
                "agent_entrypoint": "/launcher status",
                "status": "ready_via_gateway",
                "interface": "gateway_rpc",
            },
            {
                "skill_id": "launcher_focus",
                "display_name": "Launcher Focus",
                "user_goal": "Focus launcher via gateway RPC.",
                "agent_entrypoint": "/launcher focus",
                "status": "ready_via_gateway",
                "interface": "gateway_rpc",
            },
            {
                "skill_id": "launcher_journey",
                "display_name": "Launcher Journey",
                "user_goal": "Submit journey ID via gateway RPC.",
                "agent_entrypoint": "/launcher journey <journeyId>",
                "status": "ready_via_gateway",
                "interface": "gateway_rpc",
            },
            {
                "skill_id": "launcher_connect",
                "display_name": "Launcher Connect",
                "user_goal": "Forward single-use token via gateway RPC.",
                "agent_entrypoint": "/launcher connect <token>",
                "status": "ready_via_gateway",
                "interface": "gateway_rpc",
            },
            {
                "skill_id": "auth_resolve",
                "display_name": "Auth Resolve",
                "user_goal": "Resolve a valid bearer token via remote auth flow.",
                "agent_entrypoint": "/auth resolve",
                "status": "ready",
                "interface": "auth_companion",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Sandbox item resolution
# ---------------------------------------------------------------------------

def resolve_sandbox_item(item_parts: list[str]) -> dict[str, Any]:
    raw_item = " ".join(item_parts).strip()
    if raw_item.isdigit():
        item_id = int(raw_item)
        resolved_name = next(
            (name.title() for name, value in COMMON_SANDBOX_ITEMS.items() if value == item_id),
            None,
        )
        return {
            "input": raw_item,
            "mode": "item_id",
            "item_id": item_id,
            "item_name": resolved_name,
            "chat_argument": raw_item,
        }
    normalized = raw_item.strip("\"' ").lower()
    item_id = COMMON_SANDBOX_ITEMS.get(normalized)
    clean_name = raw_item.strip("\"'")
    return {
        "input": raw_item,
        "mode": "item_name",
        "item_id": item_id,
        "item_name": clean_name,
        "chat_argument": f'"{clean_name}"',
    }


# ---------------------------------------------------------------------------
# Slash-command to subcommand translation
# ---------------------------------------------------------------------------

def translate_skill_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    mapping = {
        "/moveme": ["sandbox-moveme"],
        "/giveitem": ["sandbox-giveitem"],
        "/jump-history": ["jump-history"],
        "/move": ["move"],
        "/killmails": ["killmails"],
    }
    two_word = {
        ("/system", "find"): ["system-find"],
        ("/system", "info"): ["system-info"],
        ("/ship", "info"): ["ship-info"],
        ("/ship", "list"): ["ship-list"],
        ("/gate", "info"): ["gate-info"],
        ("/gate", "list"): ["gate-list"],
        ("/assembly", "info"): ["assembly-info"],
        ("/assembly", "list"): ["assembly-list"],
        ("/character", "info"): ["character-info"],
        ("/events", "jumps"): ["events-jumps"],
        ("/events", "kills"): ["events-kills"],
        ("/launcher", "status"): ["launcher-status"],
        ("/launcher", "focus"): ["launcher-focus"],
        ("/launcher", "journey"): ["launcher-journey"],
        ("/launcher", "connect"): ["launcher-connect"],
        ("/auth", "resolve"): ["auth-resolve"],
        ("/type", "search"): ["type-search"],
        ("/type", "info"): ["type-info"],
        ("/type", "list"): ["type-list"],
        ("/constellation", "find"): ["constellation-find"],
        ("/constellation", "info"): ["constellation-info"],
        ("/tribe", "list"): ["tribe-list"],
        ("/tribe", "info"): ["tribe-info"],
        ("/jump", "detail"): ["jump-detail"],
        ("/pod", "verify"): ["pod-verify"],
    }
    if argv[0] in mapping:
        return mapping[argv[0]] + argv[1:]
    if len(argv) >= 2:
        key = (argv[0], argv[1])
        if key in two_word:
            return two_word[key] + argv[2:]
    return argv


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", default=DEFAULT_ENV, choices=["utopia", "stillness"], help="Game environment.")
    parser.add_argument("--bearer-token", default="", help="SSO/OAuth2 bearer token.")
    parser.add_argument("--wallet", default="", help="EVE Vault Sui wallet address (0x...).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Player-facing EVE Frontier skill commands (remote API).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- Sandbox commands (via message bridge) --
    p = subparsers.add_parser("sandbox-moveme", help="Send /moveme via message bridge.")
    add_common_args(p)

    p = subparsers.add_parser("sandbox-giveitem", help="Send /giveitem via message bridge.")
    p.add_argument("item", nargs="+", help="Item ID or name.")
    p.add_argument("quantity", type=int, help="Quantity to spawn.")
    add_common_args(p)

    # -- World API reads --
    p = subparsers.add_parser("system-find", help="Resolve solar systems by name.")
    p.add_argument("name", nargs="+", help="Solar system name.")
    p.add_argument("--system-index", type=Path, default=DEFAULT_SYSTEM_INDEX_PATH)
    p.add_argument("--rebuild-index", action="store_true")
    p.add_argument("--limit", type=int, default=10)
    add_common_args(p)

    p = subparsers.add_parser("ship-info", help="Get a ship detail from World API.")
    p.add_argument("ship_id", type=int, help="Ship type ID.")
    add_common_args(p)

    p = subparsers.add_parser("jump-history", help="Get character jump history.")
    add_common_args(p)

    p = subparsers.add_parser("killmails", help="List killmails from World API.")
    p.add_argument("--limit", type=int, default=25)
    add_common_args(p)

    p = subparsers.add_parser("ship-list", help="List all ships from World API.")
    add_common_args(p)

    p = subparsers.add_parser("system-info", help="Get detailed solar system info (with gateLinks).")
    p.add_argument("system_id", type=int, help="Solar system ID.")
    add_common_args(p)

    # -- Types (items, modules, commodities) --
    p = subparsers.add_parser("type-search", help="Search item/module types by name.")
    p.add_argument("name", nargs="+", help="Type name to search.")
    p.add_argument("--limit", type=int, default=20)
    add_common_args(p)

    p = subparsers.add_parser("type-info", help="Get detailed type info by ID.")
    p.add_argument("type_id", type=int, help="Type ID.")
    add_common_args(p)

    p = subparsers.add_parser("type-list", help="List all types (items/modules).")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--category", default="", help="Filter by category name.")
    add_common_args(p)

    # -- Constellations --
    p = subparsers.add_parser("constellation-find", help="Search constellations by name/ID.")
    p.add_argument("name", nargs="+", help="Constellation name or ID prefix.")
    p.add_argument("--limit", type=int, default=10)
    add_common_args(p)

    p = subparsers.add_parser("constellation-info", help="Get constellation detail with systems.")
    p.add_argument("constellation_id", type=int, help="Constellation ID.")
    add_common_args(p)

    # -- Tribes --
    p = subparsers.add_parser("tribe-list", help="List all tribes.")
    add_common_args(p)

    p = subparsers.add_parser("tribe-info", help="Get tribe detail by ID.")
    p.add_argument("tribe_id", type=int, help="Tribe ID.")
    add_common_args(p)

    # -- Jump detail (single jump by ID, supports POD) --
    p = subparsers.add_parser("jump-detail", help="Get a single jump by ID.")
    p.add_argument("jump_id", help="Jump ID (UNIX ms timestamp).")
    p.add_argument("--format", dest="fmt", default="json", choices=["json", "pod"])
    add_common_args(p)

    # -- POD verify --
    p = subparsers.add_parser("pod-verify", help="Verify a Provable Object Datatype.")
    p.add_argument("pod_json", help="Path to POD JSON file or inline JSON string.")
    add_common_args(p)

    # -- Move / jump transaction --
    p = subparsers.add_parser("move", help="Build a jump transaction plan.")
    p.add_argument("source", help="Source solar system name.")
    p.add_argument("destination", help="Destination solar system name.")
    p.add_argument("--source-gate", default="", help="Source gate on-chain address.")
    p.add_argument("--dest-gate", default="", help="Destination gate on-chain address.")
    p.add_argument("--character", default="", help="Character on-chain address.")
    p.add_argument("--system-index", type=Path, default=DEFAULT_SYSTEM_INDEX_PATH)
    add_common_args(p)

    # -- Smart Assembly / Gate queries (Sui GraphQL + World API) --
    p = subparsers.add_parser("gate-info", help="Query a Smart Gate by on-chain address.")
    p.add_argument("address", help="Smart Gate on-chain address.")
    add_common_args(p)

    p = subparsers.add_parser("gate-list", help="List Smart Gates from the blockchain.")
    p.add_argument("--limit", type=int, default=50)
    add_common_args(p)

    p = subparsers.add_parser("assembly-info", help="Query a Smart Assembly.")
    p.add_argument("address", help="Assembly address or ID.")
    add_common_args(p)

    p = subparsers.add_parser("assembly-list", help="List Smart Assemblies from World API.")
    p.add_argument("--limit", type=int, default=100)
    add_common_args(p)

    # -- Character queries --
    p = subparsers.add_parser("character-info", help="Query character by wallet address.")
    p.add_argument("wallet", help="Sui wallet address.")
    add_common_args(p)

    # -- Event queries --
    p = subparsers.add_parser("events-jumps", help="Query recent Smart Gate jump events.")
    p.add_argument("--limit", type=int, default=25)
    add_common_args(p)

    p = subparsers.add_parser("events-kills", help="Query recent Smart Turret kill events.")
    p.add_argument("--limit", type=int, default=25)
    add_common_args(p)

    # -- Gateway RPC (replaces localhost launcher calls) --
    p = subparsers.add_parser("launcher-status", help="Get launcher status via gateway RPC.")
    add_common_args(p)

    p = subparsers.add_parser("launcher-focus", help="Focus launcher via gateway RPC.")
    add_common_args(p)

    p = subparsers.add_parser("launcher-journey", help="Submit journey ID via gateway RPC.")
    p.add_argument("journey_id", help="Journey ID.")
    add_common_args(p)

    p = subparsers.add_parser("launcher-connect", help="Forward connect token via gateway RPC.")
    p.add_argument("single_use_token", help="Single-use connect token.")
    add_common_args(p)

    # -- Auth --
    p = subparsers.add_parser("auth-resolve", help="Resolve a valid bearer token via remote auth.")
    p.add_argument("--refresh-token", default="")
    p.add_argument("--client-id", default="")
    p.add_argument("--skip-validation", action="store_true")
    add_common_args(p)

    # -- Contract generation --
    p = subparsers.add_parser("write-contracts", help="Write player_skill_contracts.json.")
    p.add_argument("--output", type=Path, default=DEFAULT_CONTRACTS_OUTPUT)
    p.add_argument("--catalog-output", type=Path, default=DEFAULT_USER_SKILL_CATALOG_OUTPUT)
    add_common_args(p)

    return parser


# ---------------------------------------------------------------------------
# Client factory + auth gate
# ---------------------------------------------------------------------------

AUTH_NOT_REQUIRED = {"write-contracts", "auth-resolve"}


def make_client(args: argparse.Namespace) -> GameClient:
    return GameClient(
        env=getattr(args, "env", DEFAULT_ENV),
        bearer_token=getattr(args, "bearer_token", ""),
        wallet_address=getattr(args, "wallet", ""),
    )


def require_auth(args: argparse.Namespace) -> GameClient:
    """Create a GameClient and enforce authentication.

    ALL skills are cloud-based and require login.
    Raises AuthenticationRequired if no credentials are present.
    """
    client = make_client(args)
    client.ensure_authenticated()
    return client


def auth_error_response(command: str) -> dict[str, Any]:
    return {
        "command": command,
        "ok": False,
        "error": "authentication_required",
        "message": (
            "All skills are cloud-based and require login. "
            "Authenticate via one of the following methods:\n"
            "  1. EVE Vault browser extension: --wallet 0x... or EVE_FRONTIER_WALLET env var\n"
            "  2. SSO bearer token: --bearer-token ... or EVE_FRONTIER_BEARER env var\n"
            "  3. Refresh token: EVE_FRONTIER_REFRESH_TOKEN + EVE_FRONTIER_CLIENT_ID env vars\n"
            "Ref: https://docs.evefrontier.com/eve-vault/browser-extension"
        ),
    }


# ---------------------------------------------------------------------------
# System index helper (World API remote rebuild)
# ---------------------------------------------------------------------------

def ensure_system_index(
    path: Path, *, client: GameClient, rebuild: bool,
) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not rebuild and resolved.exists():
        return load_system_index(resolved)

    from build_system_search_index import build_system_index
    payload = build_system_index(
        client.world.base_url,
        page_size=1000,
        map_objects_db=Path("/dev/null"),
    )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
    return payload


# ---------------------------------------------------------------------------
# Command handlers — all remote
# ---------------------------------------------------------------------------

def handle_sandbox_moveme(args: argparse.Namespace) -> dict[str, Any]:
    """Send /moveme — in-game sandbox chat command.

    Per official docs (https://docs.evefrontier.com/troubleshooting/sandbox-access):
    /moveme displays a list of star systems for instant travel.
    This is a server-side slash command entered in the in-game chat window.
    """
    client = require_auth(args)
    bridge_result = client.bridge.send_command("/moveme")
    return {
        "command": "/moveme",
        "interface": "message_bridge",
        "auth": "authenticated",
        "chat_command": "/moveme",
        "bridge_response": bridge_result,
        "in_game_instruction": (
            "Enter /moveme in the in-game chat window. "
            "This displays a list of star systems you can move to instantly. "
            "Ref: https://docs.evefrontier.com/troubleshooting/sandbox-access"
        ),
    }


def handle_sandbox_giveitem(args: argparse.Namespace) -> dict[str, Any]:
    """Send /giveitem — in-game sandbox chat command.

    Per official docs (https://docs.evefrontier.com/troubleshooting/sandbox-access):
    /giveitem <itemid> <quantity> spawns items into the ship cargo.
    Can also use /giveitem "<item name>" <quantity>.
    WARNING: Can overload ship cargo and prevent warping.
    """
    client = require_auth(args)
    resolved_item = resolve_sandbox_item(args.item)
    chat_command = f"/giveitem {resolved_item['chat_argument']} {args.quantity}"
    bridge_result = client.bridge.send_command(chat_command)
    return {
        "command": "/giveitem",
        "interface": "message_bridge",
        "auth": "authenticated",
        "quantity": args.quantity,
        "item": resolved_item,
        "chat_command": chat_command,
        "bridge_response": bridge_result,
        "in_game_instruction": (
            f"Enter {chat_command} in the in-game chat window. "
            "WARNING: Can overload ship cargo and prevent warping. "
            "Move excess to a storage unit or jettison it. "
            "Ref: https://docs.evefrontier.com/troubleshooting/sandbox-access"
        ),
        "common_items_ref": "https://world-api-utopia.uat.pub.evefrontier.com/docs/index.html",
    }


def handle_system_find(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    query = " ".join(args.name)
    index_payload = ensure_system_index(args.system_index, client=client, rebuild=args.rebuild_index)
    matches = search_system_index(index_payload, query, limit=args.limit)
    return {
        "command": "/system find",
        "interface": "world_api",
        "auth": "authenticated",
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }


def handle_ship_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    return {
        "command": "/ship info",
        "interface": "world_api",
        "auth": "authenticated",
        "ship_id": args.ship_id,
        "ship": client.world.get_ship(args.ship_id),
    }


def handle_jump_history(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    return {
        "command": "/jump-history",
        "interface": "world_api",
        "auth": "authenticated",
        "ok": True,
        "jump_history": client.world.get_character_jumps(),
    }


def handle_move(args: argparse.Namespace) -> dict[str, Any]:
    """Build a jump transaction plan — write path via Sui.

    Ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world
    Requires EVE Vault wallet for transaction signing.
    """
    client = require_auth(args)
    result = build_move_plan_remote(
        client,
        source_system=args.source,
        destination_system=args.destination,
        source_gate=args.source_gate,
        destination_gate=args.dest_gate,
        character_address=args.character,
    )
    result["auth"] = "authenticated"

    if args.source_gate and args.dest_gate and args.character:
        result["sui_transaction"] = client.build_gate_jump_tx(
            source_gate=args.source_gate,
            destination_gate=args.dest_gate,
            character_id=args.character,
        )
    return result


def handle_gate_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = query_smart_gate(client, args.address)
    result["command"] = "/gate info"
    result["interface"] = "sui_graphql"
    result["auth"] = "authenticated"
    return result


def handle_gate_list(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = list_smart_gates(client, limit=args.limit)
    result["command"] = "/gate list"
    result["interface"] = "sui_graphql"
    result["auth"] = "authenticated"
    return result


def handle_assembly_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = query_smart_assembly(client, args.address)
    result["command"] = "/assembly info"
    result["auth"] = "authenticated"
    return result


def handle_assembly_list(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = list_smart_assemblies(client, limit=args.limit)
    result["command"] = "/assembly list"
    result["auth"] = "authenticated"
    return result


def handle_character_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = query_character(client, args.wallet)
    result["command"] = "/character info"
    result["interface"] = "sui_graphql"
    result["auth"] = "authenticated"
    return result


def handle_events_jumps(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = query_jump_events(client, limit=args.limit)
    result["command"] = "/events jumps"
    result["interface"] = "sui_graphql"
    result["auth"] = "authenticated"
    return result


def handle_events_kills(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = query_kill_events(client, limit=args.limit)
    result["command"] = "/events kills"
    result["interface"] = "sui_graphql"
    result["auth"] = "authenticated"
    return result


def handle_killmails(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = query_killmails(client, limit=args.limit)
    result["command"] = "/killmails"
    result["auth"] = "authenticated"
    return result


def handle_ship_list(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.list_ships(limit=100)
    return {
        "command": "/ship list",
        "interface": "world_api",
        "auth": "authenticated",
        "total": data.get("metadata", {}).get("total"),
        "ships": data.get("data", []),
    }


def handle_system_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.get_solarsystem(args.system_id)
    return {
        "command": "/system info",
        "interface": "world_api",
        "auth": "authenticated",
        "system_id": args.system_id,
        "system": data,
    }


def handle_type_search(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    query = " ".join(args.name)
    matches = client.world.search_types(query, limit=args.limit)
    return {
        "command": "/type search",
        "interface": "world_api",
        "auth": "authenticated",
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }


def handle_type_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.get_type(args.type_id)
    return {
        "command": "/type info",
        "interface": "world_api",
        "auth": "authenticated",
        "type_id": args.type_id,
        "type": data,
    }


def handle_type_list(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.list_types(limit=args.limit, offset=args.offset)
    items = data.get("data", [])
    if args.category:
        cat = args.category.lower()
        items = [t for t in items if cat in t.get("categoryName", "").lower()]
    return {
        "command": "/type list",
        "interface": "world_api",
        "auth": "authenticated",
        "total": data.get("metadata", {}).get("total"),
        "category_filter": args.category or None,
        "count": len(items),
        "types": items,
    }


def handle_constellation_find(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    query = " ".join(args.name)
    matches = client.world.search_constellations(query, limit=args.limit)
    return {
        "command": "/constellation find",
        "interface": "world_api",
        "auth": "authenticated",
        "query": query,
        "match_count": len(matches),
        "matches": matches,
    }


def handle_constellation_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.get_constellation(args.constellation_id)
    return {
        "command": "/constellation info",
        "interface": "world_api",
        "auth": "authenticated",
        "constellation_id": args.constellation_id,
        "constellation": data,
    }


def handle_tribe_list(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.list_tribes(limit=100)
    return {
        "command": "/tribe list",
        "interface": "world_api",
        "auth": "authenticated",
        "total": data.get("metadata", {}).get("total"),
        "tribes": data.get("data", []),
    }


def handle_tribe_info(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.get_tribe(args.tribe_id)
    return {
        "command": "/tribe info",
        "interface": "world_api",
        "auth": "authenticated",
        "tribe_id": args.tribe_id,
        "tribe": data,
    }


def handle_jump_detail(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    data = client.world.get_character_jump(args.jump_id, fmt=args.fmt)
    return {
        "command": "/jump detail",
        "interface": "world_api",
        "auth": "authenticated",
        "jump_id": args.jump_id,
        "format": args.fmt,
        "jump": data,
    }


def handle_pod_verify(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    pod_input = args.pod_json
    if os.path.isfile(pod_input):
        with open(pod_input) as f:
            pod_data = json.load(f)
    else:
        pod_data = json.loads(pod_input)
    result = client.world.try_request("/v2/pod/verify", method="POST", body=pod_data)
    return {
        "command": "/pod verify",
        "interface": "world_api",
        "auth": "authenticated",
        "ok": result["ok"],
        "status": result["status"],
        "result": result["body"],
    }


def handle_launcher_status(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = client.gateway.get_status()
    return {
        "command": "/launcher status",
        "interface": "gateway_rpc",
        "auth": "authenticated",
        "gateway_response": result,
    }


def handle_launcher_focus(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = client.gateway.request_focus()
    return {
        "command": "/launcher focus",
        "interface": "gateway_rpc",
        "auth": "authenticated",
        "gateway_response": result,
    }


def handle_launcher_journey(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = client.gateway.submit_journey(args.journey_id)
    return {
        "command": "/launcher journey",
        "interface": "gateway_rpc",
        "auth": "authenticated",
        "journey_id": mask_identifier(args.journey_id),
        "gateway_response": result,
    }


def handle_launcher_connect(args: argparse.Namespace) -> dict[str, Any]:
    client = require_auth(args)
    result = client.gateway.connect_token(args.single_use_token)
    return {
        "command": "/launcher connect",
        "interface": "gateway_rpc",
        "auth": "authenticated",
        "gateway_response": result,
    }


def handle_auth_resolve(args: argparse.Namespace) -> dict[str, Any]:
    auth = AuthFlowClient(env=args.env)
    token, report = auth.resolve_bearer(
        explicit_token=args.bearer_token,
        refresh_token=args.refresh_token,
        client_id=args.client_id,
        validate=not args.skip_validation,
    )
    return {
        "command": "/auth resolve",
        "interface": "auth_companion",
        "ok": token is not None,
        "token_masked": mask_identifier(token) if token else None,
        "report": report,
    }


def handle_write_contracts(args: argparse.Namespace) -> dict[str, Any]:
    contracts = get_player_skill_contracts()
    catalog = get_user_skill_catalog()
    output = args.output.expanduser().resolve()
    catalog_output = args.catalog_output.expanduser().resolve()

    for path, data in [(output, contracts), (catalog_output, catalog)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")

    return {
        "command": "write-contracts",
        "output": str(output),
        "catalog_output": str(catalog_output),
        "command_count": len(contracts["commands"]),
        "skill_count": len(catalog["skills"]),
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

HANDLERS = {
    "sandbox-moveme": handle_sandbox_moveme,
    "sandbox-giveitem": handle_sandbox_giveitem,
    "system-find": handle_system_find,
    "system-info": handle_system_info,
    "ship-info": handle_ship_info,
    "ship-list": handle_ship_list,
    "jump-history": handle_jump_history,
    "move": handle_move,
    "gate-info": handle_gate_info,
    "gate-list": handle_gate_list,
    "assembly-info": handle_assembly_info,
    "assembly-list": handle_assembly_list,
    "character-info": handle_character_info,
    "events-jumps": handle_events_jumps,
    "events-kills": handle_events_kills,
    "killmails": handle_killmails,
    "type-search": handle_type_search,
    "type-info": handle_type_info,
    "type-list": handle_type_list,
    "constellation-find": handle_constellation_find,
    "constellation-info": handle_constellation_info,
    "tribe-list": handle_tribe_list,
    "tribe-info": handle_tribe_info,
    "jump-detail": handle_jump_detail,
    "pod-verify": handle_pod_verify,
    "launcher-status": handle_launcher_status,
    "launcher-focus": handle_launcher_focus,
    "launcher-journey": handle_launcher_journey,
    "launcher-connect": handle_launcher_connect,
    "auth-resolve": handle_auth_resolve,
    "write-contracts": handle_write_contracts,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw = list(argv or __import__("sys").argv[1:])
    translated = translate_skill_argv(raw)
    args = parser.parse_args(translated)
    handler = HANDLERS.get(args.command)
    if not handler:
        raise SystemExit(f"Unknown command {args.command}")

    try:
        result = handler(args)
    except AuthenticationRequired:
        result = auth_error_response(args.command)

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result.get("ok", True) is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())

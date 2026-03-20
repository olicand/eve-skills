#!/usr/bin/env python3
"""Smart Assembly interaction API for EVE Frontier.

High-level interfaces for interacting with Smart Assemblies (Gates, Turrets,
Storage Units) on the Sui blockchain.  All interactions are cloud-based and
require authentication.

Write path (ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world):
  Sui TypeScript SDK → build Transaction → sign via EVE Vault → submit
  Pattern: borrow OwnerCap → call function → return OwnerCap

Read path:
  World API REST → /v2/smartassemblies (primary, server-indexed)
  Sui GraphQL   → on-chain object queries (real-time)
  Sui JSON-RPC  → event streams

Auth (ref: https://docs.evefrontier.com/eve-vault/browser-extension):
  EVE Vault browser extension for transaction signing
  SSO bearer token for API access
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game_api_client import GameClient, get_env_config


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class AssemblyInfo:
    address: str
    type_name: str
    owner: str | None
    is_online: bool
    raw: dict[str, Any]

    @classmethod
    def from_graphql(cls, address: str, node: dict[str, Any]) -> AssemblyInfo:
        contents = node.get("asMoveObject", {}).get("contents", {})
        json_data = contents.get("json", {})
        type_repr = contents.get("type", {}).get("repr", "")
        return cls(
            address=address,
            type_name=type_repr,
            owner=json_data.get("owner"),
            is_online=json_data.get("is_online", False),
            raw=json_data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "type_name": self.type_name,
            "owner": self.owner,
            "is_online": self.is_online,
            "raw": self.raw,
        }


@dataclass
class CharacterInfo:
    address: str
    name: str
    wallet: str
    raw: dict[str, Any]

    @classmethod
    def from_graphql(cls, address: str, node: dict[str, Any]) -> CharacterInfo:
        json_data = node.get("asMoveObject", {}).get("contents", {}).get("json", {})
        return cls(
            address=address,
            name=json_data.get("name", ""),
            wallet=json_data.get("wallet", ""),
            raw=json_data,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "name": self.name,
            "wallet": self.wallet,
            "raw": self.raw,
        }


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def query_smart_assembly(client: GameClient, assembly_address: str) -> dict[str, Any]:
    """Query a Smart Assembly by address, trying World API first, then GraphQL."""
    result = client.world.try_request(f"/v2/smartassemblies/{assembly_address}")
    if result["ok"]:
        return {"ok": True, "source": "world_api", "assembly": result["body"]}

    data = client.graphql.get_object(assembly_address)
    obj = data.get("object")
    if not obj:
        return {"ok": False, "error": f"Assembly {assembly_address} not found on-chain"}
    return {
        "ok": True,
        "source": "graphql",
        "assembly": AssemblyInfo.from_graphql(assembly_address, obj).to_dict(),
    }


def list_smart_assemblies(client: GameClient, *, limit: int = 100) -> dict[str, Any]:
    """List Smart Assemblies via World API."""
    result = client.world.try_request(f"/v2/smartassemblies?limit={limit}&offset=0")
    if result["ok"]:
        body = result["body"]
        return {
            "ok": True,
            "source": "world_api",
            "count": len(body.get("data", [])),
            "total": body.get("metadata", {}).get("total"),
            "assemblies": body.get("data", []),
        }
    return {"ok": False, "error": "World API /v2/smartassemblies unavailable", "body": result["body"]}


def query_smart_gate(client: GameClient, gate_address: str) -> dict[str, Any]:
    """Query a specific Smart Gate by on-chain address."""
    data = client.graphql.get_object(gate_address)
    obj = data.get("object")
    if not obj:
        return {"ok": False, "error": f"Gate {gate_address} not found on-chain"}
    return {
        "ok": True,
        "gate": AssemblyInfo.from_graphql(gate_address, obj).to_dict(),
    }


def list_smart_gates(client: GameClient, *, limit: int = 50) -> dict[str, Any]:
    """List all Smart Gates from the Sui blockchain."""
    data = client.graphql.get_smart_gates(first=limit)
    objects = data.get("objects", {})
    nodes = objects.get("nodes", [])
    gates = [AssemblyInfo.from_graphql(n.get("address", ""), n).to_dict() for n in nodes]
    return {
        "ok": True,
        "count": len(gates),
        "has_next_page": objects.get("pageInfo", {}).get("hasNextPage", False),
        "gates": gates,
    }


def list_smart_storage_units(client: GameClient, *, limit: int = 50) -> dict[str, Any]:
    """List Smart Storage Units from the Sui blockchain."""
    data = client.graphql.get_smart_storage_units(first=limit)
    objects = data.get("objects", {})
    nodes = objects.get("nodes", [])
    units = [AssemblyInfo.from_graphql(n.get("address", ""), n).to_dict() for n in nodes]
    return {
        "ok": True,
        "count": len(units),
        "has_next_page": objects.get("pageInfo", {}).get("hasNextPage", False),
        "storage_units": units,
    }


def list_smart_turrets(client: GameClient, *, limit: int = 50) -> dict[str, Any]:
    """List Smart Turrets from the Sui blockchain."""
    data = client.graphql.get_smart_turrets(first=limit)
    objects = data.get("objects", {})
    nodes = objects.get("nodes", [])
    turrets = [AssemblyInfo.from_graphql(n.get("address", ""), n).to_dict() for n in nodes]
    return {
        "ok": True,
        "count": len(turrets),
        "has_next_page": objects.get("pageInfo", {}).get("hasNextPage", False),
        "turrets": turrets,
    }


def query_character(client: GameClient, wallet_address: str) -> dict[str, Any]:
    """Query a character's PlayerProfile by wallet address."""
    data = client.graphql.get_character(wallet_address)
    addr_data = data.get("address", {})
    nodes = addr_data.get("objects", {}).get("nodes", [])
    if not nodes:
        return {"ok": False, "error": f"No character found for wallet {wallet_address}"}
    characters = [CharacterInfo.from_graphql(n.get("address", ""), n).to_dict() for n in nodes]
    return {"ok": True, "characters": characters}


# ---------------------------------------------------------------------------
# Event queries
# ---------------------------------------------------------------------------

def query_jump_events(client: GameClient, *, limit: int = 25) -> dict[str, Any]:
    """Query recent Smart Gate jump events from the blockchain."""
    data = client.graphql.get_jump_events(limit=limit)
    events = data.get("events", {}).get("nodes", [])
    return {"ok": True, "count": len(events), "events": events}


def query_kill_events(client: GameClient, *, limit: int = 25) -> dict[str, Any]:
    """Query recent Smart Turret kill events from the blockchain."""
    data = client.graphql.get_kill_events(limit=limit)
    events = data.get("events", {}).get("nodes", [])
    return {"ok": True, "count": len(events), "events": events}


def query_killmails(client: GameClient, *, limit: int = 25) -> dict[str, Any]:
    """Query killmails from the World API."""
    result = client.world.try_request(f"/v2/killmails?limit={limit}&offset=0")
    if result["ok"]:
        body = result["body"]
        return {
            "ok": True,
            "source": "world_api",
            "count": len(body.get("data", [])),
            "killmails": body.get("data", []),
        }
    return {"ok": False, "error": "World API /v2/killmails unavailable", "body": result["body"]}


# ---------------------------------------------------------------------------
# Jump transaction planning (remote-only)
# ---------------------------------------------------------------------------

def build_jump_transaction_plan(
    client: GameClient,
    *,
    source_gate: str,
    destination_gate: str,
    character_address: str,
) -> dict[str, Any]:
    """Build a jump transaction plan by querying on-chain gate and character data.

    Follows the official write path pattern:
      Sui TypeScript SDK → build Transaction → sign via EVE Vault → submit
    Ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world

    For sponsored transactions (server-side validation like distance checks):
      tx.setSender(playerAddress)
      tx.setGasOwner(adminAddress)
    """
    env_config = client.env_config()
    world_package = env_config["world_package"]
    gate_config = env_config["gate_config"]

    blocked_by: list[str] = []

    source_result = client.graphql.get_object(source_gate)
    source_obj = source_result.get("object")
    if not source_obj:
        blocked_by.append("source_gate_not_found_on_chain")

    dest_result = client.graphql.get_object(destination_gate)
    dest_obj = dest_result.get("object")
    if not dest_obj:
        blocked_by.append("destination_gate_not_found_on_chain")

    char_result = client.graphql.get_object(character_address)
    char_obj = char_result.get("object")
    if not char_obj:
        blocked_by.append("character_not_found_on_chain")

    source_info = AssemblyInfo.from_graphql(source_gate, source_obj).to_dict() if source_obj else None
    dest_info = AssemblyInfo.from_graphql(destination_gate, dest_obj).to_dict() if dest_obj else None

    if blocked_by:
        return {
            "ok": False,
            "blocked_by": blocked_by,
            "transaction": None,
            "source_gate": source_info,
            "destination_gate": dest_info,
        }

    return {
        "ok": True,
        "blocked_by": [],
        "transaction": {
            "write_path": "Sui TypeScript SDK -> EVE Vault sign -> submit",
            "sui_move_call": {
                "target": f"{world_package}::smart_gate::jump",
                "typeArguments": [],
                "arguments": [
                    f"tx.object('{source_gate}')",
                    f"tx.object('{destination_gate}')",
                    f"tx.object('{character_address}')",
                    f"tx.object('{gate_config}')",
                ],
            },
            "typescript_example": (
                "const tx = new Transaction();\n"
                "tx.moveCall({\n"
                f"  target: '{world_package}::smart_gate::jump',\n"
                "  arguments: [\n"
                f"    tx.object('{source_gate}'),\n"
                f"    tx.object('{destination_gate}'),\n"
                f"    tx.object('{character_address}'),\n"
                f"    tx.object('{gate_config}'),\n"
                "  ],\n"
                "});\n"
                "// Sign via EVE Vault: dAppKit.signAndExecuteTransaction(tx)"
            ),
            "sponsored_transaction_note": (
                "For sponsored transactions:\n"
                "  tx.setSender(playerAddress);\n"
                "  tx.setGasOwner(adminAddress);\n"
                "Ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world"
            ),
        },
        "source_gate": source_info,
        "destination_gate": dest_info,
    }


def build_move_plan_remote(
    client: GameClient,
    *,
    source_system: str,
    destination_system: str,
    source_gate: str = "",
    destination_gate: str = "",
    character_address: str = "",
) -> dict[str, Any]:
    """Build a complete move plan using only remote APIs.

    Steps:
    1. Resolve source/destination systems via World API system index
    2. If gate addresses provided, validate on-chain
    3. Build transaction plan
    """
    from world_api_client import search_system_index, load_system_index, DEFAULT_SYSTEM_INDEX_PATH

    blocked_by: list[str] = []

    index_path = DEFAULT_SYSTEM_INDEX_PATH.expanduser().resolve()
    if index_path.exists():
        index_payload = load_system_index(index_path)
    else:
        systems: list[dict[str, Any]] = []
        for item in client.world.iter_collection("/v2/solarsystems", page_size=1000):
            systems.append(item)
        index_payload = {"systems": systems}

    source_matches = search_system_index(index_payload, source_system, limit=5)
    dest_matches = search_system_index(index_payload, destination_system, limit=5)

    source_match = source_matches[0] if source_matches else None
    dest_match = dest_matches[0] if dest_matches else None

    if not source_match:
        blocked_by.append("source_system_not_resolved")
    if not dest_match:
        blocked_by.append("destination_system_not_resolved")

    if not source_gate:
        blocked_by.append("source_gate_address_not_provided")
    if not destination_gate:
        blocked_by.append("destination_gate_address_not_provided")
    if not character_address:
        blocked_by.append("character_address_not_provided")

    tx_plan = None
    if source_gate and destination_gate and character_address:
        tx_plan = build_jump_transaction_plan(
            client,
            source_gate=source_gate,
            destination_gate=destination_gate,
            character_address=character_address,
        )
        blocked_by.extend(tx_plan.get("blocked_by", []))

    return {
        "command": "/move",
        "source_query": source_system,
        "destination_query": destination_system,
        "resolution": {
            "source": source_match,
            "destination": dest_match,
            "source_candidates": source_matches,
            "destination_candidates": dest_matches,
        },
        "transaction_plan": tx_plan,
        "readiness": {
            "systems_resolved": source_match is not None and dest_match is not None,
            "gates_provided": bool(source_gate and destination_gate),
            "character_provided": bool(character_address),
            "ready_for_submission": not blocked_by,
        },
        "blocked_by": blocked_by,
        "next_step": (
            "Provide source_gate, destination_gate, and character on-chain addresses "
            "to build a submittable Sui transaction."
            if blocked_by else
            "Transaction plan is ready. Sign and submit via dApp Kit or Sui TypeScript SDK."
        ),
    }

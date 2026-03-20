#!/usr/bin/env python3
"""AI Agent tool definitions for EVE Frontier Skills.

Converts all 31 player skill commands into OpenAI-compatible function calling
definitions. These can be used with any LLM that supports function/tool calling
(OpenAI, Claude, Gemini, local models via LiteLLM, etc.).

Architecture:
    User (Telegram/Chat) → AI Agent → tool_call → execute_skill() → GameClient → World API
                                                                                → Sui GraphQL
                                                                                → Message Bridge
                                                                                → Gateway RPC

Each tool definition includes:
- name: skill function name
- description: what it does (for the AI to decide when to use it)
- parameters: JSON Schema for the arguments
"""
from __future__ import annotations

from typing import Any


SKILL_TOOLS: list[dict[str, Any]] = [
    # ====== Universe Exploration ======
    {
        "type": "function",
        "function": {
            "name": "system_find",
            "description": "Search for solar systems by name in the EVE Frontier universe. Returns matching systems with IDs, constellation and region info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Solar system name to search (partial match supported), e.g. 'A 2560'"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 10},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get detailed solar system info by ID, including position coordinates and gate links to connected systems.",
            "parameters": {
                "type": "object",
                "properties": {
                    "system_id": {"type": "integer", "description": "Solar system ID, e.g. 30000001"},
                },
                "required": ["system_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constellation_find",
            "description": "Search for constellations by name or ID. Returns constellation info with region and contained solar systems.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Constellation name or ID to search"},
                    "limit": {"type": "integer", "description": "Max results", "default": 10},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "constellation_info",
            "description": "Get detailed constellation info by ID, including all solar systems within it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "constellation_id": {"type": "integer", "description": "Constellation ID, e.g. 20000001"},
                },
                "required": ["constellation_id"],
            },
        },
    },

    # ====== Ships ======
    {
        "type": "function",
        "function": {
            "name": "ship_list",
            "description": "List all available ships in EVE Frontier (11 ships total). Shows name, class and ID.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ship_info",
            "description": "Get detailed ship stats by ID: slots (high/mid/low), health (shield/armor/structure), physics (mass/velocity), fuel capacity, CPU, powergrid, capacitor, damage resistances.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ship_id": {"type": "integer", "description": "Ship type ID, e.g. 81609 (USV), 81611 (Chumaq)"},
                },
                "required": ["ship_id"],
            },
        },
    },

    # ====== Items / Types ======
    {
        "type": "function",
        "function": {
            "name": "type_search",
            "description": "Search for item/module types by name, category or group. EVE Frontier has 390 types including modules, commodities, asteroids, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Type name to search, e.g. 'Laser', 'Hull', 'Carbon'"},
                    "limit": {"type": "integer", "description": "Max results", "default": 20},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_info",
            "description": "Get detailed info for a specific item/module type by ID, including mass, volume, attributes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_id": {"type": "integer", "description": "Type ID, e.g. 72960 (Hull Repairer), 77800 (Feldspar Crystals)"},
                },
                "required": ["type_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_list",
            "description": "List item/module types with optional category filter. Categories include: Module, Commodity, Asteroid, Ship, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category name, e.g. 'Module', 'Commodity'"},
                    "limit": {"type": "integer", "description": "Max results per page", "default": 100},
                    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
                },
            },
        },
    },

    # ====== Tribes ======
    {
        "type": "function",
        "function": {
            "name": "tribe_list",
            "description": "List all tribes (player organizations) in EVE Frontier. Shows name, short name, tax rate.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tribe_info",
            "description": "Get detailed tribe info by ID: name, description, tax rate, tribe URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tribe_id": {"type": "integer", "description": "Tribe ID, e.g. 98000001 (Reality Anchor)"},
                },
                "required": ["tribe_id"],
            },
        },
    },

    # ====== Smart Assemblies (On-chain) ======
    {
        "type": "function",
        "function": {
            "name": "gate_list",
            "description": "List all Smart Gates deployed on the Sui blockchain. Shows address, owner, online status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max gates to return", "default": 50},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gate_info",
            "description": "Query a specific Smart Gate's on-chain state by its Sui address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Smart Gate on-chain address (0x...)"},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assembly_list",
            "description": "List Smart Assemblies (Gates, Turrets, Storage Units) from the World API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max assemblies to return", "default": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assembly_info",
            "description": "Query a specific Smart Assembly by address. Tries World API first, falls back to Sui GraphQL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Assembly address or ID"},
                },
                "required": ["address"],
            },
        },
    },

    # ====== Character ======
    {
        "type": "function",
        "function": {
            "name": "character_info",
            "description": "Query a player character's on-chain profile by their Sui wallet address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "wallet": {"type": "string", "description": "Player's Sui wallet address (0x...)"},
                },
                "required": ["wallet"],
            },
        },
    },

    # ====== Jump History & Events ======
    {
        "type": "function",
        "function": {
            "name": "jump_history",
            "description": "Get the current authenticated user's gate jump history. Requires bearer token auth.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "jump_detail",
            "description": "Get details of a specific jump by ID. Supports POD (Provable Object Datatype) format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jump_id": {"type": "string", "description": "Jump ID (UNIX millisecond timestamp)"},
                    "format": {"type": "string", "enum": ["json", "pod"], "description": "Response format", "default": "json"},
                },
                "required": ["jump_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "events_jumps",
            "description": "Query recent Smart Gate jump events from the Sui blockchain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max events to return", "default": 25},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "events_kills",
            "description": "Query recent Smart Turret kill events from the Sui blockchain.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max events to return", "default": 25},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "killmails",
            "description": "List killmails (PvP kill records) from the World API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max killmails to return", "default": 25},
                },
            },
        },
    },

    # ====== Movement / Transaction ======
    {
        "type": "function",
        "function": {
            "name": "move",
            "description": "Plan a jump between two solar systems. Resolves systems, validates gates, and builds a Sui transaction for EVE Vault signing. Requires gate addresses and character address for transaction submission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source solar system name"},
                    "destination": {"type": "string", "description": "Destination solar system name"},
                    "source_gate": {"type": "string", "description": "Source gate on-chain address (0x...)"},
                    "dest_gate": {"type": "string", "description": "Destination gate on-chain address (0x...)"},
                    "character": {"type": "string", "description": "Character on-chain address (0x...)"},
                },
                "required": ["source", "destination"],
            },
        },
    },

    # ====== Sandbox Commands ======
    {
        "type": "function",
        "function": {
            "name": "sandbox_moveme",
            "description": "Send /moveme command — displays a list of star systems for instant teleportation. This is a sandbox/testing command.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sandbox_giveitem",
            "description": "Send /giveitem command — spawns items into ship cargo. WARNING: can overload cargo and prevent warping.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "Item name or ID, e.g. 'Carbon Weave' or 84210"},
                    "quantity": {"type": "integer", "description": "Quantity to spawn"},
                },
                "required": ["item", "quantity"],
            },
        },
    },

    # ====== Launcher Control ======
    {
        "type": "function",
        "function": {
            "name": "launcher_status",
            "description": "Get the EVE Frontier launcher status via gateway RPC.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launcher_focus",
            "description": "Request focus on the EVE Frontier launcher window.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launcher_journey",
            "description": "Submit a journey ID to the launcher via gateway RPC.",
            "parameters": {
                "type": "object",
                "properties": {
                    "journey_id": {"type": "string", "description": "Journey identifier"},
                },
                "required": ["journey_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launcher_connect",
            "description": "Send a single-use connect token to the launcher.",
            "parameters": {
                "type": "object",
                "properties": {
                    "single_use_token": {"type": "string", "description": "Single-use authentication token"},
                },
                "required": ["single_use_token"],
            },
        },
    },

    # ====== POD ======
    {
        "type": "function",
        "function": {
            "name": "pod_verify",
            "description": "Verify a Provable Object Datatype (POD) — checks if a POD's cryptographic signature is valid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pod_json": {"type": "string", "description": "POD data as JSON string"},
                },
                "required": ["pod_json"],
            },
        },
    },

    # ====== Auth ======
    {
        "type": "function",
        "function": {
            "name": "auth_status",
            "description": "Check the current user's authentication status. Returns whether they are logged in and token info.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "auth_login",
            "description": "Generate a login URL for the user to authenticate with EVE Frontier SSO. Returns a URL to open in browser.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return all skill tool definitions for AI function calling."""
    return SKILL_TOOLS


def get_tool_names() -> list[str]:
    """Return all available tool/function names."""
    return [t["function"]["name"] for t in SKILL_TOOLS]


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """Look up a single tool definition by function name."""
    for t in SKILL_TOOLS:
        if t["function"]["name"] == name:
            return t
    return None

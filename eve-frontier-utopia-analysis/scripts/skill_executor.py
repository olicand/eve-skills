#!/usr/bin/env python3
"""Skill executor — bridges AI tool calls to GameClient actions.

This is the core execution layer that:
1. Receives a tool_call (function name + arguments) from the AI
2. Looks up the corresponding skill handler
3. Executes it against the authenticated GameClient
4. Returns structured results back to the AI

Used by any AI agent frontend (Telegram bot, web chat, CLI, etc.).

Architecture:
    AI decides tool_call → SkillExecutor.execute(session, name, args) → GameClient → API → result
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game_api_client import GameClient
from session_manager import SessionManager, UserSession
from smart_assembly_api import (
    build_move_plan_remote,
    list_smart_assemblies,
    list_smart_gates,
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
    search_system_index,
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


class SkillExecutor:
    """Executes skill tool calls against an authenticated GameClient.

    Usage:
        executor = SkillExecutor(session_manager)
        result = executor.execute("user123", "ship_list", {})
    """

    def __init__(self, session_mgr: SessionManager) -> None:
        self.session_mgr = session_mgr

    def execute(self, user_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a skill tool call for a given user.

        Returns a structured result dict. If the user is not authenticated,
        returns an auth_required response with a login URL.
        """
        if tool_name == "auth_status":
            return self._handle_auth_status(user_id)
        if tool_name == "auth_login":
            return self._handle_auth_login(user_id)

        session = self.session_mgr.get_session(user_id)
        client = self.session_mgr.ensure_authenticated(session)

        if client is None:
            return {
                "ok": False,
                "error": "not_authenticated",
                "message": "You need to log in first. Use the auth_login tool or set a token.",
                "action_required": "login",
            }

        handler = self._HANDLERS.get(tool_name)
        if not handler:
            return {"ok": False, "error": f"Unknown skill: {tool_name}"}

        try:
            return handler(self, client, arguments)
        except Exception as e:
            return {"ok": False, "error": str(e), "tool": tool_name}

    # -- Auth handlers (no GameClient needed) --

    def _handle_auth_status(self, user_id: str) -> dict[str, Any]:
        session = self.session_mgr.get_session(user_id)
        return {"ok": True, "tool": "auth_status", **session.summary()}

    def _handle_auth_login(self, user_id: str) -> dict[str, Any]:
        session = self.session_mgr.get_session(user_id)
        result = self.session_mgr.start_login(session)
        result["tool"] = "auth_login"
        return result

    # -- Universe --

    def _system_find(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        name = args["name"]
        limit = args.get("limit", 10)
        index_path = DEFAULT_SYSTEM_INDEX_PATH.expanduser().resolve()
        if index_path.exists():
            index = load_system_index(index_path)
        else:
            systems = list(client.world.iter_collection("/v2/solarsystems", page_size=1000))
            index = {"systems": systems}
        matches = search_system_index(index, name, limit=limit)
        return {"ok": True, "tool": "system_find", "query": name, "count": len(matches), "matches": matches}

    def _system_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.get_solarsystem(args["system_id"])
        return {"ok": True, "tool": "system_info", "system": data}

    def _constellation_find(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        matches = client.world.search_constellations(args["name"], limit=args.get("limit", 10))
        return {"ok": True, "tool": "constellation_find", "count": len(matches), "matches": matches}

    def _constellation_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.get_constellation(args["constellation_id"])
        return {"ok": True, "tool": "constellation_info", "constellation": data}

    # -- Ships --

    def _ship_list(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.list_ships(limit=100)
        return {"ok": True, "tool": "ship_list", "total": data["metadata"]["total"], "ships": data["data"]}

    def _ship_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.get_ship(args["ship_id"])
        return {"ok": True, "tool": "ship_info", "ship": data}

    # -- Types --

    def _type_search(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        matches = client.world.search_types(args["name"], limit=args.get("limit", 20))
        return {"ok": True, "tool": "type_search", "count": len(matches), "matches": matches}

    def _type_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.get_type(args["type_id"])
        return {"ok": True, "tool": "type_info", "type": data}

    def _type_list(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)
        data = client.world.list_types(limit=limit, offset=offset)
        items = data.get("data", [])
        category = args.get("category", "")
        if category:
            items = [t for t in items if category.lower() in t.get("categoryName", "").lower()]
        return {"ok": True, "tool": "type_list", "total": data["metadata"]["total"], "count": len(items), "types": items}

    # -- Tribes --

    def _tribe_list(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.list_tribes(limit=100)
        return {"ok": True, "tool": "tribe_list", "total": data["metadata"]["total"], "tribes": data["data"]}

    def _tribe_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.get_tribe(args["tribe_id"])
        return {"ok": True, "tool": "tribe_info", "tribe": data}

    # -- Assemblies --

    def _gate_list(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return list_smart_gates(client, limit=args.get("limit", 50))

    def _gate_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return query_smart_gate(client, args["address"])

    def _assembly_list(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return list_smart_assemblies(client, limit=args.get("limit", 100))

    def _assembly_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return query_smart_assembly(client, args["address"])

    # -- Character --

    def _character_info(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return query_character(client, args["wallet"])

    # -- Jumps & Events --

    def _jump_history(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        data = client.world.get_character_jumps()
        return {"ok": True, "tool": "jump_history", "jumps": data}

    def _jump_detail(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        fmt = args.get("format", "json")
        data = client.world.get_character_jump(args["jump_id"], fmt=fmt)
        return {"ok": True, "tool": "jump_detail", "jump": data}

    def _events_jumps(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return query_jump_events(client, limit=args.get("limit", 25))

    def _events_kills(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return query_kill_events(client, limit=args.get("limit", 25))

    def _killmails(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return query_killmails(client, limit=args.get("limit", 25))

    # -- Move --

    def _move(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        result = build_move_plan_remote(
            client,
            source_system=args["source"],
            destination_system=args["destination"],
            source_gate=args.get("source_gate", ""),
            destination_gate=args.get("dest_gate", ""),
            character_address=args.get("character", ""),
        )
        if args.get("source_gate") and args.get("dest_gate") and args.get("character"):
            result["sui_transaction"] = client.build_gate_jump_tx(
                source_gate=args["source_gate"],
                destination_gate=args["dest_gate"],
                character_id=args["character"],
            )
        return result

    # -- Sandbox --

    def _sandbox_moveme(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        bridge = client.bridge.send_command("/moveme")
        return {
            "ok": True,
            "tool": "sandbox_moveme",
            "bridge_response": bridge,
            "instruction": "You can also type /moveme in the in-game chat window.",
        }

    def _sandbox_giveitem(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        item_raw = str(args["item"])
        qty = args["quantity"]
        if item_raw.isdigit():
            chat_arg = item_raw
        else:
            item_id = COMMON_SANDBOX_ITEMS.get(item_raw.lower())
            chat_arg = f'"{item_raw}"' if not item_id else str(item_id)
        cmd = f"/giveitem {chat_arg} {qty}"
        bridge = client.bridge.send_command(cmd)
        return {
            "ok": True,
            "tool": "sandbox_giveitem",
            "chat_command": cmd,
            "bridge_response": bridge,
            "instruction": f"You can also type {cmd} in the in-game chat window.",
        }

    # -- Launcher --

    def _launcher_status(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "tool": "launcher_status", "response": client.gateway.get_status()}

    def _launcher_focus(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "tool": "launcher_focus", "response": client.gateway.request_focus()}

    def _launcher_journey(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "tool": "launcher_journey", "response": client.gateway.submit_journey(args["journey_id"])}

    def _launcher_connect(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, "tool": "launcher_connect", "response": client.gateway.connect_token(args["single_use_token"])}

    # -- POD --

    def _pod_verify(self, client: GameClient, args: dict[str, Any]) -> dict[str, Any]:
        pod_str = args["pod_json"]
        pod_data = json.loads(pod_str) if isinstance(pod_str, str) else pod_str
        result = client.world.try_request("/v2/pod/verify", method="POST", body=pod_data)
        return {"ok": result["ok"], "tool": "pod_verify", "status": result["status"], "result": result["body"]}

    _HANDLERS = {
        "system_find": _system_find,
        "system_info": _system_info,
        "constellation_find": _constellation_find,
        "constellation_info": _constellation_info,
        "ship_list": _ship_list,
        "ship_info": _ship_info,
        "type_search": _type_search,
        "type_info": _type_info,
        "type_list": _type_list,
        "tribe_list": _tribe_list,
        "tribe_info": _tribe_info,
        "gate_list": _gate_list,
        "gate_info": _gate_info,
        "assembly_list": _assembly_list,
        "assembly_info": _assembly_info,
        "character_info": _character_info,
        "jump_history": _jump_history,
        "jump_detail": _jump_detail,
        "events_jumps": _events_jumps,
        "events_kills": _events_kills,
        "killmails": _killmails,
        "move": _move,
        "sandbox_moveme": _sandbox_moveme,
        "sandbox_giveitem": _sandbox_giveitem,
        "launcher_status": _launcher_status,
        "launcher_focus": _launcher_focus,
        "launcher_journey": _launcher_journey,
        "launcher_connect": _launcher_connect,
        "pod_verify": _pod_verify,
    }

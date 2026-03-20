#!/usr/bin/env python3
"""Unified remote game API client for EVE Frontier.

ALL skills are cloud-based and require authentication before use.
All interactions go through remote HTTP/GraphQL/RPC endpoints.

Architecture (ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world):
- WorldApiClient:      REST API for game world data (read)
- SuiGraphQLClient:    Sui blockchain queries — read path (GraphQL / gRPC)
- SuiRpcClient:        Sui JSON-RPC — events, transaction dry-runs
- MessageBridgeClient: Game command relay
- GatewayRpcClient:    ConnectRPC gateway (launcher-level operations)

Write path: Sui TypeScript SDK → build Transaction → sign via EVE Vault → submit
Read path:  GraphQL / gRPC / SuiClient → query on-chain state
Auth:       EVE Vault browser extension (wallet) + SSO OAuth2 bearer

Sandbox commands (/moveme, /giveitem) are in-game chat commands only,
documented at https://docs.evefrontier.com/troubleshooting/sandbox-access
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------

ENVIRONMENTS: dict[str, dict[str, str]] = {
    "utopia": {
        "world_api": "https://world-api-utopia.uat.pub.evefrontier.com",
        "message_bridge": "https://message-bridge-nebula.test.tech.evefrontier.com",
        "gateway": "https://gateway.production.services.evevanguardtech.com:443",
        "auth_companion": "https://auth-companion-utopia.auth.evefrontier.com",
        "sso": "https://login.eveonline.com",
        "signup": "https://signup.eveonline.com",
        "graphql": "https://graphql.testnet.sui.io/graphql",
        "sui_rpc": "https://fullnode.testnet.sui.io:443",
        "dapp": "https://uat.dapps.evefrontier.com",
        "world_package": "0xd12a70c74c1e759445d6f209b01d43d860e97fcf2ef72ccbbd00afd828043f75",
        "object_registry": "0xc2b969a72046c47e24991d69472afb2216af9e91caf802684514f39706d7dc57",
        "energy_config": "0x9285364e8104c04380d9cc4a001bbdfc81a554aad441c2909c2d3bd52a0c9c62",
        "fuel_config": "0x0f354c803af170ac0d1ac9068625c6321996b3013dc67bdaf14d06f93fa1671f",
        "gate_config": "0x69a392c514c4ca6d771d8aa8bf296d4d7a021e244e792eb6cd7a0c61047fc62b",
        "killmail_registry": "0xa92de75fde403a6ccfcb1d5a380f79befaed9f1a2210e10f1c5867a4cd82b84e",
        "location_registry": "0x62e6ec4caea639e21e4b8c3cf0104bace244b3f1760abed340cc3285905651cf",
    },
    "stillness": {
        "world_api": "https://world-api-stillness.live.tech.evefrontier.com",
        "message_bridge": "https://message-bridge-stillness.live.tech.evefrontier.com",
        "gateway": "https://gateway.production.services.evevanguardtech.com:443",
        "auth_companion": "https://auth-companion-stillness.auth.evefrontier.com",
        "sso": "https://login.eveonline.com",
        "signup": "https://signup.eveonline.com",
        "graphql": "https://graphql.testnet.sui.io/graphql",
        "sui_rpc": "https://fullnode.testnet.sui.io:443",
        "dapp": "https://dapps.evefrontier.com",
        "world_package": "0x28b497559d65ab320d9da4613bf2498d5946b2c0ae3597ccfda3072ce127448c",
        "object_registry": "0x454a9aa3d37e1d08d3c9181239c1b683781e4087fbbbd48c935d54b6736fd05c",
        "energy_config": "0xd77693d0df5656d68b1b833e2a23cc81eb3875d8d767e7bd249adde82bdbc952",
        "fuel_config": "0x4fcf28a9be750d242bc5d2f324429e31176faecb5b84f0af7dff3a2a6e243550",
        "gate_config": "0xd6d9230faec0230c839a534843396e97f5f79bdbd884d6d5103d0125dc135827",
        "killmail_registry": "0x7fd9a32d0bbe7b1cfbb7140b1dd4312f54897de946c399edb21c3a12e52ce283",
        "location_registry": "0xc87dca9c6b2c95e4a0cbe1f8f9eeff50171123f176fbfdc7b49eef4824fc596b",
    },
}

DEFAULT_ENV = os.environ.get("EVE_FRONTIER_ENV", "utopia")


def get_env_config(env: str = DEFAULT_ENV) -> dict[str, str]:
    if env not in ENVIRONMENTS:
        raise ValueError(f"Unknown environment '{env}', expected one of: {sorted(ENVIRONMENTS)}")
    return ENVIRONMENTS[env]


# ---------------------------------------------------------------------------
# HTTP utilities
# ---------------------------------------------------------------------------

class ApiError(RuntimeError):
    def __init__(self, status: int, body: Any, url: str = ""):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"API request failed: {url} -> {status}")


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    payload = None
    req_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=payload, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            parsed = json.loads(raw) if raw else None
            return {"ok": True, "status": resp.status, "body": parsed}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw.decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": parsed}
    except urllib.error.URLError as exc:
        return {"ok": False, "status": 0, "body": str(exc.reason)}


def post_form(url: str, form_fields: dict[str, str], *, timeout: int = 20) -> dict[str, Any]:
    payload = urllib.parse.urlencode(form_fields).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"ok": True, "status": resp.status, "body": json.loads(resp.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return {"ok": False, "status": exc.code, "body": parsed}


# ---------------------------------------------------------------------------
# World API Client (REST)
# ---------------------------------------------------------------------------

class WorldApiClient:
    """REST client for the EVE Frontier World API."""

    def __init__(
        self,
        base_url: str = "",
        bearer_token: str = "",
        env: str = DEFAULT_ENV,
    ) -> None:
        self.base_url = (base_url or get_env_config(env)["world_api"]).rstrip("/")
        self.bearer_token = bearer_token or os.environ.get("EVE_FRONTIER_BEARER", "")

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        return h

    def request(self, path: str, *, method: str = "GET", body: Any | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        result = request_json(url, method=method, headers=self._headers(), body=body)
        if not result["ok"]:
            raise ApiError(result["status"], result["body"], url)
        return result["body"]

    def try_request(self, path: str, *, method: str = "GET", body: Any | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        return request_json(url, method=method, headers=self._headers(), body=body)

    def list_collection(self, path: str, *, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        sep = "&" if "?" in path else "?"
        return self.request(f"{path}{sep}limit={limit}&offset={offset}")

    def iter_collection(self, path: str, *, page_size: int = 1000) -> Iterable[dict[str, Any]]:
        offset = 0
        while True:
            page = self.list_collection(path, limit=page_size, offset=offset)
            items = list(page.get("data", []))
            yield from items
            total = page.get("metadata", {}).get("total")
            offset += len(items)
            if not items or (total is not None and offset >= total):
                break

    # -- Public endpoints --

    def get_health(self) -> Any:
        return self.request("/health")

    def get_config(self) -> Any:
        return self.request("/config")

    # Solar Systems (24502 total)
    def list_solarsystems(self, *, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/solarsystems", limit=limit, offset=offset)

    def get_solarsystem(self, system_id: int | str) -> dict[str, Any]:
        """Get detailed solar system info including gateLinks to connected systems."""
        return self.request(f"/v2/solarsystems/{system_id}")

    def search_solarsystems(self, name: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search solar systems by name (client-side filtering over paginated API)."""
        normalized = name.strip().lower()
        matches: list[dict[str, Any]] = []
        for system in self.iter_collection("/v2/solarsystems", page_size=1000):
            if normalized in system.get("name", "").lower():
                matches.append(system)
                if len(matches) >= limit:
                    break
        return matches

    # Ships (11 total)
    def list_ships(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/ships", limit=limit, offset=offset)

    def get_ship(self, ship_id: int | str) -> dict[str, Any]:
        """Get detailed ship info including slots, health, physics, resistances."""
        return self.request(f"/v2/ships/{ship_id}")

    # Constellations (2213 total)
    def list_constellations(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/constellations", limit=limit, offset=offset)

    def get_constellation(self, constellation_id: int | str) -> dict[str, Any]:
        """Get constellation detail with its solar systems."""
        return self.request(f"/v2/constellations/{constellation_id}")

    def search_constellations(self, name: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search constellations by name or ID prefix."""
        normalized = name.strip().lower()
        matches: list[dict[str, Any]] = []
        for c in self.iter_collection("/v2/constellations", page_size=1000):
            if normalized in c.get("name", "").lower() or normalized in str(c.get("id", "")):
                matches.append(c)
                if len(matches) >= limit:
                    break
        return matches

    # Types (390 total) — items, modules, commodities, etc.
    def list_types(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/types", limit=limit, offset=offset)

    def get_type(self, type_id: int | str) -> dict[str, Any]:
        """Get detailed type info with attributes."""
        return self.request(f"/v2/types/{type_id}")

    def search_types(self, name: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search types (items/modules) by name or category."""
        normalized = name.strip().lower()
        matches: list[dict[str, Any]] = []
        for t in self.iter_collection("/v2/types", page_size=1000):
            if (normalized in t.get("name", "").lower()
                    or normalized in t.get("categoryName", "").lower()
                    or normalized in t.get("groupName", "").lower()):
                matches.append(t)
                if len(matches) >= limit:
                    break
        return matches

    # Tribes (2 total)
    def list_tribes(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/tribes", limit=limit, offset=offset)

    def get_tribe(self, tribe_id: int | str) -> dict[str, Any]:
        """Get detailed tribe info including tax rate and URL."""
        return self.request(f"/v2/tribes/{tribe_id}")

    # POD verification
    def verify_pod(self, pod_data: dict[str, Any]) -> dict[str, Any]:
        return self.request("/v2/pod/verify", method="POST", body=pod_data)

    # -- Protected endpoints (require BearerAuth) --

    def get_character_jumps(self, *, limit: int = 100, offset: int = 0) -> Any:
        return self.list_collection("/v2/characters/me/jumps", limit=limit, offset=offset)

    def get_character_jump(self, jump_id: str, *, fmt: str = "json") -> Any:
        """Get a single jump by ID. Supports ?format=pod for POD format."""
        path = f"/v2/characters/me/jumps/{jump_id}"
        if fmt != "json":
            path += f"?format={urllib.parse.quote(fmt)}"
        return self.request(path)


# ---------------------------------------------------------------------------
# Sui GraphQL Client
# ---------------------------------------------------------------------------

class SuiGraphQLClient:
    """Client for querying EVE Frontier on-chain state via Sui GraphQL."""

    def __init__(self, endpoint: str = "", env: str = DEFAULT_ENV) -> None:
        self.endpoint = endpoint or get_env_config(env)["graphql"]
        self._env_config = get_env_config(env)

    @property
    def world_package(self) -> str:
        return self._env_config["world_package"]

    def query(self, gql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": gql}
        if variables:
            payload["variables"] = variables
        result = request_json(self.endpoint, method="POST", body=payload)
        if not result["ok"]:
            raise ApiError(result["status"], result["body"], self.endpoint)
        data = result["body"]
        if data.get("errors"):
            raise ApiError(200, data["errors"], self.endpoint)
        return data.get("data", {})

    # -- Object queries --

    def get_object(self, address: str) -> dict[str, Any]:
        return self.query(
            """query($addr: SuiAddress!) {
              object(address: $addr) {
                address version digest
                owner {
                  ... on Shared { initialSharedVersion }
                  ... on AddressOwner { owner { address } }
                }
                asMoveObject {
                  contents { type { repr } json }
                  hasPublicTransfer
                }
              }
            }""",
            {"addr": address},
        )

    def get_objects_by_type(
        self, type_name: str, *, first: int = 50, after: str | None = None,
    ) -> dict[str, Any]:
        variables: dict[str, Any] = {"type": type_name, "first": first}
        if after:
            variables["after"] = after
        return self.query(
            """query($type: String!, $first: Int!, $after: String) {
              objects(filter: { type: $type }, first: $first, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  address
                  asMoveObject { contents { type { repr } json } }
                }
              }
            }""",
            variables,
        )

    def get_owned_objects(
        self,
        owner: str,
        *,
        type_filter: str = "",
        first: int = 50,
    ) -> dict[str, Any]:
        variables: dict[str, Any] = {"owner": owner, "first": first}
        if type_filter:
            variables["type"] = type_filter
            return self.query(
                """query($owner: SuiAddress!, $first: Int!, $type: String!) {
                  address(address: $owner) {
                    objects(first: $first, filter: { type: $type }) {
                      nodes {
                        address
                        asMoveObject { contents { type { repr } json } }
                      }
                    }
                  }
                }""",
                variables,
            )
        return self.query(
            """query($owner: SuiAddress!, $first: Int!) {
              address(address: $owner) {
                objects(first: $first) {
                  nodes {
                    address
                    asMoveObject { contents { type { repr } json } }
                  }
                }
              }
            }""",
            variables,
        )

    # -- Smart Assembly shortcuts --

    def get_smart_gates(self, *, first: int = 50) -> dict[str, Any]:
        return self.get_objects_by_type(f"{self.world_package}::smart_gate::SmartGate", first=first)

    def get_smart_storage_units(self, *, first: int = 50) -> dict[str, Any]:
        return self.get_objects_by_type(
            f"{self.world_package}::smart_storage_unit::SmartStorageUnit", first=first,
        )

    def get_smart_turrets(self, *, first: int = 50) -> dict[str, Any]:
        return self.get_objects_by_type(f"{self.world_package}::smart_turret::SmartTurret", first=first)

    def get_character(self, wallet_address: str) -> dict[str, Any]:
        return self.get_owned_objects(
            wallet_address,
            type_filter=f"{self.world_package}::character::PlayerProfile",
        )

    # -- Event queries --

    def query_events(self, event_type: str, *, limit: int = 25) -> dict[str, Any]:
        return self.query(
            """query($eventType: String!, $limit: Int!) {
              events(filter: { eventType: $eventType }, last: $limit) {
                nodes {
                  sendingModule { name package { address } }
                  type { repr }
                  json
                  timestamp
                }
              }
            }""",
            {"eventType": event_type, "limit": limit},
        )

    def get_jump_events(self, *, limit: int = 25) -> dict[str, Any]:
        return self.query_events(f"{self.world_package}::smart_gate::GateJumpEvent", limit=limit)

    def get_kill_events(self, *, limit: int = 25) -> dict[str, Any]:
        return self.query_events(f"{self.world_package}::smart_turret::KillEvent", limit=limit)


# ---------------------------------------------------------------------------
# Sui JSON-RPC Client
# ---------------------------------------------------------------------------

class SuiRpcClient:
    """Client for Sui JSON-RPC (events, object reads, transaction dry-runs)."""

    def __init__(self, endpoint: str = "", env: str = DEFAULT_ENV) -> None:
        self.endpoint = endpoint or get_env_config(env)["sui_rpc"]
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def call(self, method: str, params: list[Any]) -> Any:
        body = {"jsonrpc": "2.0", "id": self._next_id(), "method": method, "params": params}
        result = request_json(self.endpoint, method="POST", body=body)
        if not result["ok"]:
            raise ApiError(result["status"], result["body"], self.endpoint)
        rpc_result = result["body"]
        if "error" in rpc_result:
            raise ApiError(200, rpc_result["error"], self.endpoint)
        return rpc_result.get("result")

    def query_events(self, event_type: str, *, limit: int = 25, descending: bool = True) -> Any:
        return self.call("suix_queryEvents", [{"MoveEventType": event_type}, None, limit, descending])

    def get_object(self, object_id: str) -> Any:
        return self.call(
            "sui_getObject",
            [object_id, {"showContent": True, "showType": True, "showOwner": True}],
        )

    def dry_run_transaction(self, tx_bytes: str) -> Any:
        return self.call("sui_dryRunTransactionBlock", [tx_bytes])


# ---------------------------------------------------------------------------
# Message Bridge Client
# ---------------------------------------------------------------------------

class MessageBridgeClient:
    """Client for the EVE Frontier message bridge.

    Relays game commands (chat slash commands, etc.) to the game server remotely,
    replacing local osascript/keystroke dispatch.
    """

    def __init__(
        self,
        base_url: str = "",
        bearer_token: str = "",
        env: str = DEFAULT_ENV,
    ) -> None:
        self.base_url = (base_url or get_env_config(env)["message_bridge"]).rstrip("/")
        self.bearer_token = bearer_token or os.environ.get("EVE_FRONTIER_BEARER", "")

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        return h

    def send_command(self, command: str, *, channel: str = "chat") -> dict[str, Any]:
        """Send a game command through the message bridge."""
        return request_json(
            f"{self.base_url}/api/v1/command",
            method="POST",
            headers=self._headers(),
            body={"command": command, "channel": channel},
        )

    def get_status(self) -> dict[str, Any]:
        return request_json(f"{self.base_url}/api/v1/status", headers=self._headers())

    def send_chat(self, message: str) -> dict[str, Any]:
        return self.send_command(message, channel="chat")


# ---------------------------------------------------------------------------
# Gateway RPC Client
# ---------------------------------------------------------------------------

class GatewayRpcClient:
    """Client for the EVE Frontier ConnectRPC gateway.

    Replaces localhost launcher bridge calls with remote gateway requests.
    """

    def __init__(
        self,
        base_url: str = "",
        bearer_token: str = "",
        env: str = DEFAULT_ENV,
    ) -> None:
        self.base_url = (base_url or get_env_config(env)["gateway"]).rstrip("/")
        self.bearer_token = bearer_token or os.environ.get("EVE_FRONTIER_BEARER", "")

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        }
        if self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        return h

    def call_rpc(
        self, service: str, method: str, payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{service}/{method}"
        return request_json(url, method="POST", headers=self._headers(), body=payload or {})

    def get_status(self) -> dict[str, Any]:
        return self.call_rpc("eve_launcher.gateway.GatewayService", "GetStatus")

    def request_focus(self) -> dict[str, Any]:
        return self.call_rpc("eve_launcher.gateway.GatewayService", "RequestFocus")

    def submit_journey(self, journey_id: str) -> dict[str, Any]:
        return self.call_rpc(
            "eve_launcher.gateway.GatewayService", "SubmitJourney", {"journeyId": journey_id},
        )

    def connect_token(self, token: str) -> dict[str, Any]:
        return self.call_rpc(
            "eve_launcher.gateway.GatewayService", "Connect", {"singleUseToken": token},
        )


# ---------------------------------------------------------------------------
# Unified Game Client
# ---------------------------------------------------------------------------

class AuthenticationRequired(RuntimeError):
    """Raised when a skill is invoked without valid authentication."""

    def __init__(self, hint: str = ""):
        msg = "Authentication required. All skills are cloud-based and require login."
        if hint:
            msg += f" {hint}"
        super().__init__(msg)


@dataclass
class GameClient:
    """Unified client aggregating all remote EVE Frontier API interfaces.

    ALL skills are cloud-based and require authentication.
    The client must be created with a valid bearer_token or wallet_address.

    Auth methods (ref: https://docs.evefrontier.com/eve-vault/browser-extension):
    - bearer_token: SSO/OAuth2 bearer for World API + Gateway + Bridge
    - wallet_address: Sui wallet from EVE Vault (for chain queries + tx signing)

    Usage:
        client = GameClient(env="utopia", bearer_token="...", wallet_address="0x...")
        client.ensure_authenticated()
        systems = client.world.list_solarsystems(limit=10)
        gates = client.graphql.get_smart_gates(first=5)
    """

    env: str = DEFAULT_ENV
    bearer_token: str = ""
    wallet_address: str = ""

    world: WorldApiClient = field(init=False)
    graphql: SuiGraphQLClient = field(init=False)
    sui_rpc: SuiRpcClient = field(init=False)
    bridge: MessageBridgeClient = field(init=False)
    gateway: GatewayRpcClient = field(init=False)

    def __post_init__(self) -> None:
        token = self.bearer_token or os.environ.get("EVE_FRONTIER_BEARER", "")
        self.bearer_token = token
        self.wallet_address = self.wallet_address or os.environ.get("EVE_FRONTIER_WALLET", "")
        self.world = WorldApiClient(bearer_token=token, env=self.env)
        self.graphql = SuiGraphQLClient(env=self.env)
        self.sui_rpc = SuiRpcClient(env=self.env)
        self.bridge = MessageBridgeClient(bearer_token=token, env=self.env)
        self.gateway = GatewayRpcClient(bearer_token=token, env=self.env)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.bearer_token or self.wallet_address)

    def ensure_authenticated(self) -> None:
        """Raise AuthenticationRequired if no credentials are present."""
        if not self.is_authenticated:
            raise AuthenticationRequired(
                "Set EVE_FRONTIER_BEARER (SSO token) or EVE_FRONTIER_WALLET (EVE Vault address), "
                "or pass --bearer-token / --wallet."
            )

    def env_config(self) -> dict[str, str]:
        return get_env_config(self.env)

    def build_sui_move_call(
        self,
        *,
        package: str = "",
        module: str,
        function: str,
        type_arguments: list[str] | None = None,
        arguments: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build a Sui Move call descriptor for transaction construction.

        This produces the JSON structure that the Sui TypeScript SDK or
        EVE Vault wallet extension uses to build and sign a transaction.
        Ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world
        """
        pkg = package or self.env_config()["world_package"]
        return {
            "target": f"{pkg}::{module}::{function}",
            "typeArguments": type_arguments or [],
            "arguments": arguments or [],
            "sender": self.wallet_address,
            "package": pkg,
            "module": module,
            "function": function,
        }

    def build_assembly_online_tx(
        self,
        *,
        assembly_id: str,
        character_id: str,
        owner_cap_id: str,
        network_node_id: str,
    ) -> dict[str, Any]:
        """Build a 'bring assembly online' transaction following the official pattern.

        Pattern: borrow OwnerCap → call assembly::online → return OwnerCap
        Ref: https://docs.evefrontier.com/tools/interfacing-with-the-eve-frontier-world
        """
        cfg = self.env_config()
        pkg = cfg["world_package"]
        return {
            "transaction_type": "assembly_online",
            "steps": [
                {
                    "step": "borrow_owner_cap",
                    "move_call": self.build_sui_move_call(
                        module="character",
                        function="borrow_owner_cap",
                        type_arguments=[f"{pkg}::assembly::Assembly"],
                        arguments=[character_id, owner_cap_id],
                    ),
                },
                {
                    "step": "assembly_online",
                    "move_call": self.build_sui_move_call(
                        module="assembly",
                        function="online",
                        arguments=[assembly_id, network_node_id, cfg["energy_config"], "$ownerCap"],
                    ),
                },
                {
                    "step": "return_owner_cap",
                    "move_call": self.build_sui_move_call(
                        module="character",
                        function="return_owner_cap",
                        type_arguments=[f"{pkg}::assembly::Assembly"],
                        arguments=[character_id, "$ownerCap"],
                    ),
                },
            ],
            "sign_with": "EVE Vault wallet or Sui TypeScript SDK",
            "sender": self.wallet_address,
        }

    def build_gate_jump_tx(
        self,
        *,
        source_gate: str,
        destination_gate: str,
        character_id: str,
    ) -> dict[str, Any]:
        """Build a Smart Gate jump transaction descriptor."""
        cfg = self.env_config()
        return {
            "transaction_type": "gate_jump",
            "move_call": self.build_sui_move_call(
                module="smart_gate",
                function="jump",
                arguments=[source_gate, destination_gate, character_id, cfg["gate_config"]],
            ),
            "sender": self.wallet_address,
            "notes": [
                "Sign with EVE Vault browser extension or Sui TypeScript SDK.",
                "For sponsored transactions, set gas_owner to admin address.",
                "Call sui_dryRunTransactionBlock to validate before submission.",
            ],
        }

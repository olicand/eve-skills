#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_WORLD_API_BASE_URL = "https://world-api-utopia.uat.pub.evefrontier.com"
DEFAULT_SYSTEM_INDEX_PATH = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/metadata/system_search_index.json"
)


class WorldApiError(RuntimeError):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"World API request failed with status {status}")


@dataclass
class SearchMatch:
    score: int
    item: dict[str, Any]


def parse_json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


def normalize_name(value: str) -> str:
    lowered = value.lower().strip()
    compact = re.sub(r"\s+", " ", lowered)
    return compact


def alnum_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_name(value))


def tokenize_name(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", normalize_name(value)) if token]


def request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {"ok": True, "status": response.status, "body": parse_json(response.read())}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = parse_json(raw)
        except Exception:
            parsed = raw.decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": parsed}


class WorldApiClient:
    def __init__(self, base_url: str = DEFAULT_WORLD_API_BASE_URL, bearer_token: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token

    def _headers(self) -> dict[str, str]:
        headers = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def request(self, path: str, *, method: str = "GET", body: Any | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        result = request_json(url, method=method, headers=self._headers(), body=body)
        if not result["ok"]:
            raise WorldApiError(result["status"], result["body"])
        return result["body"]

    def list_collection(self, path: str, *, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        separator = "&" if "?" in path else "?"
        return self.request(f"{path}{separator}limit={limit}&offset={offset}")

    def iter_collection(self, path: str, *, page_size: int = 1000) -> Iterable[dict[str, Any]]:
        offset = 0
        while True:
            page = self.list_collection(path, limit=page_size, offset=offset)
            items = list(page.get("data", []))
            for item in items:
                yield item

            metadata = page.get("metadata", {})
            total = metadata.get("total")
            offset += len(items)
            if not items:
                break
            if total is not None and offset >= total:
                break

    def get_health(self) -> Any:
        return self.request("/health")

    def get_config(self) -> Any:
        return self.request("/config")

    def list_solarsystems(self, *, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/solarsystems", limit=limit, offset=offset)

    def get_solarsystem(self, system_id: int | str) -> dict[str, Any]:
        return self.request(f"/v2/solarsystems/{system_id}")

    def list_ships(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self.list_collection("/v2/ships", limit=limit, offset=offset)

    def get_ship(self, ship_id: int | str, *, format_name: str = "json") -> dict[str, Any]:
        return self.request(f"/v2/ships/{ship_id}?format={urllib.parse.quote(format_name)}")

    def get_jump_history(self) -> Any:
        return self.request("/v2/characters/me/jumps")


def load_system_index(path: Path = DEFAULT_SYSTEM_INDEX_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def choose_search_aliases(item: dict[str, Any]) -> list[str]:
    aliases = []
    name = item.get("name")
    normalized = item.get("normalized_name")
    alnum = item.get("alnum_name")
    if isinstance(name, str):
        aliases.append(name)
    if isinstance(normalized, str):
        aliases.append(normalized)
    if isinstance(alnum, str):
        aliases.append(alnum)
    return aliases


def score_system(query: str, item: dict[str, Any]) -> int:
    normalized_query = normalize_name(query)
    compact_query = alnum_key(query)
    aliases = choose_search_aliases(item)

    best = 0
    for alias in aliases:
        normalized_alias = normalize_name(alias)
        compact_alias = alnum_key(alias)
        if normalized_query == normalized_alias or compact_query == compact_alias:
            best = max(best, 100)
        elif normalized_alias.startswith(normalized_query) or compact_alias.startswith(compact_query):
            best = max(best, 80)
        elif normalized_query in normalized_alias or compact_query in compact_alias:
            best = max(best, 60)

    query_tokens = set(tokenize_name(query))
    item_tokens = set(item.get("tokens", []))
    if query_tokens and item_tokens:
        overlap = len(query_tokens & item_tokens)
        if overlap and (len(query_tokens) == 1 or overlap == len(query_tokens) or overlap > 1):
            best = max(best, 40 + overlap * 5)

    return best


def search_system_index(index_payload: dict[str, Any], query: str, *, limit: int = 10) -> list[dict[str, Any]]:
    matches: list[SearchMatch] = []
    for item in index_payload.get("systems", []):
        score = score_system(query, item)
        if score <= 0:
            continue
        matches.append(SearchMatch(score=score, item=item))

    matches.sort(key=lambda match: (-match.score, match.item.get("name", ""), match.item.get("id", 0)))
    return [
        {
            "score": match.score,
            **match.item,
        }
        for match in matches[:limit]
    ]

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test the EVE Frontier World API and optionally a protected endpoint with a bearer token."
    )
    parser.add_argument(
        "--base-url",
        default="https://world-api-utopia.uat.pub.evefrontier.com",
        help="World API base URL.",
    )
    parser.add_argument(
        "--bearer-token",
        default="",
        help="Optional bearer token for protected endpoints.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/world_api_smoke_test.json"),
        help="Where to write the JSON report.",
    )
    return parser.parse_args()


def parse_json(raw: bytes) -> object:
    text = raw.decode("utf-8")
    return json.loads(text)


def request_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: object | None = None) -> dict[str, object]:
    encoded = None
    request_headers = dict(headers or {})
    if body is not None:
        encoded = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=encoded, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = parse_json(response.read())
            return {"ok": True, "status": response.status, "body": payload}
    except urllib.error.HTTPError as exc:
        payload = None
        raw = exc.read()
        try:
            payload = parse_json(raw)
        except Exception:
            payload = raw.decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "body": payload}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def summarize_public_calls(base_url: str) -> dict[str, object]:
    health = request_json(f"{base_url}/health")
    config = request_json(f"{base_url}/config")
    solarsystems = request_json(f"{base_url}/v2/solarsystems?limit=2&offset=0")
    ships = request_json(f"{base_url}/v2/ships?limit=1&offset=0")

    ship_summary: dict[str, object] = {"skipped": True}
    if ships["ok"] and ships["body"].get("data"):
        ship_id = ships["body"]["data"][0]["id"]
        ship_detail = request_json(f"{base_url}/v2/ships/{ship_id}")
        ship_pod = request_json(f"{base_url}/v2/ships/{ship_id}?format=pod")

        verify = {"skipped": True}
        if ship_pod["ok"]:
            verify = request_json(f"{base_url}/v2/pod/verify", method="POST", body=ship_pod["body"])

        ship_summary = {
            "skipped": False,
            "ship_id": ship_id,
            "ship_name": ship_detail["body"].get("name") if ship_detail["ok"] else None,
            "detail": {"status": ship_detail["status"], "ok": ship_detail["ok"]},
            "pod": {
                "status": ship_pod["status"],
                "ok": ship_pod["ok"],
                "keys": list(ship_pod["body"].keys()) if ship_pod["ok"] and isinstance(ship_pod["body"], dict) else [],
            },
            "pod_verify": {
                "status": verify.get("status"),
                "ok": verify.get("ok"),
                "body": verify.get("body"),
            },
        }

    return {
        "health": health,
        "config": {
            "status": config["status"],
            "ok": config["ok"],
            "entry_count": len(config["body"]) if config["ok"] and isinstance(config["body"], list) else None,
            "body": config["body"],
        },
        "solarsystems": {
            "status": solarsystems["status"],
            "ok": solarsystems["ok"],
            "count": len(solarsystems["body"].get("data", [])) if solarsystems["ok"] else None,
            "metadata": solarsystems["body"].get("metadata") if solarsystems["ok"] else None,
            "first_ids": [item["id"] for item in solarsystems["body"].get("data", [])] if solarsystems["ok"] else [],
        },
        "ships": {
            "status": ships["status"],
            "ok": ships["ok"],
            "count": len(ships["body"].get("data", [])) if ships["ok"] else None,
            "metadata": ships["body"].get("metadata") if ships["ok"] else None,
        },
        "sample_ship_chain": ship_summary,
    }


def summarize_protected_calls(base_url: str, bearer_token: str) -> dict[str, object]:
    no_token = request_json(f"{base_url}/v2/characters/me/jumps")
    summary: dict[str, object] = {
        "without_token": {
            "status": no_token["status"],
            "ok": no_token["ok"],
            "body": no_token["body"],
        }
    }

    if bearer_token:
        with_token = request_json(
            f"{base_url}/v2/characters/me/jumps",
            headers={"Authorization": f"Bearer {bearer_token}"},
        )
        summary["with_token"] = {
            "status": with_token["status"],
            "ok": with_token["ok"],
            "body": with_token["body"],
        }
    else:
        summary["with_token"] = {"skipped": True, "reason": "no bearer token provided"}

    return summary


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    report = {
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "public_calls": summarize_public_calls(base_url),
        "protected_calls": summarize_protected_calls(base_url, args.bearer_token),
    }
    write_json(args.output.expanduser().resolve(), report)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

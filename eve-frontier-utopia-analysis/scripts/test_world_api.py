#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from auth_session import resolve_world_api_auth
from world_api_client import DEFAULT_WORLD_API_BASE_URL, WorldApiClient, request_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test the EVE Frontier World API and optionally a protected endpoint with a bearer token."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_WORLD_API_BASE_URL,
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


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def summarize_public_calls(base_url: str) -> dict[str, object]:
    client = WorldApiClient(base_url=base_url)
    health = request_json(f"{base_url}/health")
    config = request_json(f"{base_url}/config")
    solarsystems = client.list_solarsystems(limit=2, offset=0)
    ships = client.list_ships(limit=1, offset=0)

    ship_summary: dict[str, object] = {"skipped": True}
    if ships.get("data"):
        ship_id = ships["data"][0]["id"]
        ship_detail = client.get_ship(ship_id)
        ship_pod = request_json(f"{base_url}/v2/ships/{ship_id}?format=pod")

        verify = {"skipped": True}
        if ship_pod["ok"]:
            verify = request_json(f"{base_url}/v2/pod/verify", method="POST", body=ship_pod["body"])

        ship_summary = {
            "skipped": False,
            "ship_id": ship_id,
            "ship_name": ship_detail.get("name"),
            "detail": {"ok": True},
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
            "status": 200,
            "ok": True,
            "count": len(solarsystems.get("data", [])),
            "metadata": solarsystems.get("metadata"),
            "first_ids": [item["id"] for item in solarsystems.get("data", [])],
        },
        "ships": {
            "status": 200,
            "ok": True,
            "count": len(ships.get("data", [])),
            "metadata": ships.get("metadata"),
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
        derived_token, auth_report = resolve_world_api_auth(base_url=base_url, probe_world_api=True)
        summary["auth_report"] = auth_report
        if derived_token:
            with_token = request_json(
                f"{base_url}/v2/characters/me/jumps",
                headers={"Authorization": f"Bearer {derived_token}"},
            )
            summary["with_token"] = {
                "status": with_token["status"],
                "ok": with_token["ok"],
                "body": with_token["body"],
                "source": "derived_local_session",
            }
        else:
            summary["with_token"] = {
                "skipped": True,
                "reason": "no valid bearer token available from explicit input or local session probe",
            }

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

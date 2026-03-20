#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from world_api_client import DEFAULT_WORLD_API_BASE_URL, request_json


DEFAULT_TOKEN_ENDPOINT = "https://test.auth.evefrontier.com/oauth2/token"


@dataclass
class CandidateToken:
    source: str
    token: str
    claims: dict[str, Any]


def decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    name, domain = value.split("@", 1)
    if len(name) <= 2:
        masked_name = "*" * len(name)
    else:
        masked_name = name[:1] + "*" * (len(name) - 2) + name[-1:]
    return f"{masked_name}@{domain}"


def parse_process_args(command_line: str) -> dict[str, str]:
    pairs = re.findall(r"/([A-Za-z0-9_]+)(?::|=)([^\s]+)", command_line)
    return {key: value for key, value in pairs}


def read_process_table() -> str:
    return subprocess.run(["ps", "auxww"], capture_output=True, text=True, check=True).stdout


def detect_runtime_components(ps_text: str | None = None) -> dict[str, Any]:
    ps_text = ps_text or read_process_table()
    return {
        "launcher_running": "EVE Frontier.app/Contents/MacOS/EVE Frontier --frontier-test-servers=Utopia" in ps_text,
        "utopia_client_running": "SharedCache/utopia/EVE.app" in ps_text,
        "zk_signer_running": "SharedCache/utopia/EVE.app/Contents/Resources/build/bin64/zk_signer" in ps_text,
    }


def find_running_utopia_session(ps_text: str | None = None) -> dict[str, Any] | None:
    ps_text = ps_text or read_process_table()
    for line in ps_text.splitlines():
        if "SharedCache/utopia/EVE.app" not in line or "/refreshToken=" not in line:
            continue
        parts = line.split(None, 10)
        pid = int(parts[1]) if len(parts) > 1 else None
        command = parts[10] if len(parts) > 10 else line
        args = parse_process_args(command)
        sso_token = args.get("ssoToken", "")
        refresh_token = args.get("refreshToken", "")
        if not sso_token or not refresh_token:
            continue
        claims = decode_jwt_claims(sso_token)
        return {
            "pid": pid,
            "command_path": command.split()[0] if command else "",
            "server": args.get("server", ""),
            "sso_token": sso_token,
            "refresh_token": refresh_token,
            "claims": claims,
            "application_id": claims.get("applicationId") or claims.get("aud"),
            "tenant": claims.get("tenant"),
            "email": claims.get("email"),
            "scope": claims.get("scope") or claims.get("scp"),
        }
    return None


def post_form(url: str, form_fields: dict[str, str]) -> dict[str, Any]:
    import urllib.request
    import urllib.error

    payload = urllib.parse.urlencode(form_fields).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return {"ok": True, "status": response.status, "body": json.loads(response.read().decode("utf-8"))}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return {"ok": False, "status": exc.code, "body": parsed}


def build_candidate_tokens(
    *,
    explicit_bearer_token: str = "",
    running_session: dict[str, Any] | None = None,
    token_endpoint: str = DEFAULT_TOKEN_ENDPOINT,
) -> tuple[list[CandidateToken], dict[str, Any]]:
    candidates: list[CandidateToken] = []
    report: dict[str, Any] = {"sources": []}

    if explicit_bearer_token:
        claims = decode_jwt_claims(explicit_bearer_token)
        candidates.append(CandidateToken(source="explicit_bearer", token=explicit_bearer_token, claims=claims))
        report["sources"].append({"source": "explicit_bearer", "claims": summarize_claims(claims)})

    if not running_session:
        return candidates, report

    sso_claims = running_session.get("claims", {})
    candidates.append(CandidateToken(source="game_sso_token", token=running_session["sso_token"], claims=sso_claims))
    report["sources"].append({"source": "game_sso_token", "claims": summarize_claims(sso_claims)})

    application_id = running_session.get("application_id")
    if not application_id:
        report["oauth_exchange"] = {"ok": False, "reason": "missing application_id in running session claims"}
        return candidates, report

    exchange_result = post_form(
        token_endpoint,
        {
            "grant_type": "refresh_token",
            "client_id": application_id,
            "refresh_token": running_session["refresh_token"],
        },
    )
    report["oauth_exchange"] = {
        "ok": exchange_result["ok"],
        "status": exchange_result["status"],
        "keys": sorted(exchange_result["body"].keys()) if exchange_result["ok"] and isinstance(exchange_result["body"], dict) else [],
    }
    if not exchange_result["ok"] or not isinstance(exchange_result["body"], dict):
        return candidates, report

    for field_name in ("access_token", "id_token"):
        token = exchange_result["body"].get(field_name)
        if not token:
            continue
        claims = decode_jwt_claims(token)
        source_name = f"oauth_{field_name}"
        candidates.append(CandidateToken(source=source_name, token=token, claims=claims))
        report["sources"].append({"source": source_name, "claims": summarize_claims(claims)})

    return candidates, report


def summarize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "aud": claims.get("aud"),
        "iss": claims.get("iss"),
        "scope": claims.get("scope") or claims.get("scp"),
        "tenant": claims.get("tenant"),
        "email": mask_email(claims.get("email")),
        "application_id": claims.get("applicationId"),
    }


def probe_world_api_bearers(base_url: str, candidates: list[CandidateToken]) -> tuple[str | None, list[dict[str, Any]]]:
    success_token = None
    results = []
    for candidate in candidates:
        probe = request_json(
            f"{base_url.rstrip('/')}/v2/characters/me/jumps",
            headers={"Authorization": f"Bearer {candidate.token}"},
        )
        results.append(
            {
                "source": candidate.source,
                "claims": summarize_claims(candidate.claims),
                "status": probe["status"],
                "ok": probe["ok"],
                "body": probe["body"],
            }
        )
        if probe["ok"] and success_token is None:
            success_token = candidate.token
    return success_token, results


def resolve_world_api_auth(
    *,
    base_url: str = DEFAULT_WORLD_API_BASE_URL,
    explicit_bearer_token: str = "",
    token_endpoint: str = DEFAULT_TOKEN_ENDPOINT,
    probe_world_api: bool = True,
) -> tuple[str | None, dict[str, Any]]:
    ps_text = read_process_table()
    running_session = find_running_utopia_session(ps_text)
    runtime = detect_runtime_components(ps_text)
    report: dict[str, Any] = {
        "runtime": runtime,
        "running_session": None,
    }
    if running_session:
        report["running_session"] = {
            "pid": running_session["pid"],
            "server": running_session.get("server"),
            "tenant": running_session.get("tenant"),
            "email": mask_email(running_session.get("email")),
            "application_id": running_session.get("application_id"),
            "scope": running_session.get("scope"),
        }

    candidates, candidate_report = build_candidate_tokens(
        explicit_bearer_token=explicit_bearer_token,
        running_session=running_session,
        token_endpoint=token_endpoint,
    )
    report.update(candidate_report)

    if probe_world_api:
        success_token, probes = probe_world_api_bearers(base_url, candidates)
        report["world_api_probe"] = probes
        report["world_api_ready"] = success_token is not None
        if success_token is None:
            report["next_step"] = "No locally-derived token currently passes /v2/characters/me/jumps. Capture the official browser or launcher auth flow to find the World API-specific bearer exchange."
        return success_token, report

    report["world_api_ready"] = False
    return None, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect local EVE Frontier login state and probe World API bearer candidates.")
    parser.add_argument("--base-url", default=DEFAULT_WORLD_API_BASE_URL, help="World API base URL.")
    parser.add_argument("--token-endpoint", default=DEFAULT_TOKEN_ENDPOINT, help="OIDC token endpoint.")
    parser.add_argument("--bearer-token", default=os.environ.get("EVE_FRONTIER_WORLD_BEARER", ""), help="Explicit bearer token override.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--skip-probe", action="store_true", help="Do not probe /v2/characters/me/jumps.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _, report = resolve_world_api_auth(
        base_url=args.base_url,
        explicit_bearer_token=args.bearer_token,
        token_endpoint=args.token_endpoint,
        probe_world_api=not args.skip_probe,
    )
    text = json.dumps(report, indent=2, ensure_ascii=True)
    if args.output:
        args.output.expanduser().resolve().write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

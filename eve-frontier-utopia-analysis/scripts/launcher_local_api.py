#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from world_api_client import DEFAULT_WORLD_API_BASE_URL, request_json


DEFAULT_LOCAL_LAUNCHER_BASE_URL = "http://localhost:3275"
DEFAULT_SIGNUP_SERVICE_BASE_URL = "https://signup.eveonline.com"


class LauncherLocalApiError(RuntimeError):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"Launcher local API request failed with status {status}")


@dataclass
class HttpResult:
    ok: bool
    status: int
    body: Any
    headers: dict[str, str]


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


def mask_identifier(value: str | None, *, leading: int = 8, trailing: int = 4) -> str | None:
    if not value:
        return value
    if len(value) <= leading + trailing:
        if len(value) <= 2:
            return "*" * len(value)
        return value[:1] + "*" * (len(value) - 2) + value[-1:]
    return f"{value[:leading]}...{value[-trailing:]}"


def summarize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "aud": claims.get("aud"),
        "iss": claims.get("iss"),
        "scope": claims.get("scope") or claims.get("scp"),
        "tenant": claims.get("tenant"),
        "name": claims.get("name"),
        "email": mask_email(claims.get("email")),
        "application_id": claims.get("applicationId"),
    }


def request_http(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: int = 20,
) -> HttpResult:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)

    def parse_body(raw: bytes, response_headers: dict[str, str]) -> Any:
        if not raw:
            return None
        content_type = response_headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return raw.decode("utf-8", errors="replace")
        return raw.decode("utf-8", errors="replace")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            headers_dict = dict(response.headers.items())
            body_value = parse_body(response.read(), headers_dict)
            return HttpResult(ok=True, status=response.status, body=body_value, headers=headers_dict)
    except urllib.error.HTTPError as exc:
        headers_dict = dict(exc.headers.items())
        body_value = parse_body(exc.read(), headers_dict)
        return HttpResult(ok=False, status=exc.code, body=body_value, headers=headers_dict)


class LauncherLocalApiClient:
    def __init__(self, base_url: str = DEFAULT_LOCAL_LAUNCHER_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, *, method: str = "GET", body: Any | None = None) -> HttpResult:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        return request_http(url, method=method, body=body)

    def get_status(self) -> dict[str, Any]:
        result = self.request("/status")
        if not result.ok or not isinstance(result.body, dict):
            raise LauncherLocalApiError(result.status, result.body)
        return result.body

    def focus(self) -> dict[str, Any]:
        result = self.request("/focus", method="POST")
        if not result.ok and result.status != 204:
            raise LauncherLocalApiError(result.status, result.body)
        return {
            "ok": result.ok or result.status == 204,
            "status": result.status,
            "content_type": result.headers.get("Content-Type"),
        }

    def submit_journey(self, journey_id: str) -> dict[str, Any]:
        result = self.request("/journey", method="POST", body={"journeyId": journey_id})
        if not result.ok or not isinstance(result.body, dict):
            raise LauncherLocalApiError(result.status, result.body)
        return result.body

    def connect(self, single_use_token: str, *, journey_id: str = "") -> dict[str, Any]:
        payload = {"singleUseToken": single_use_token}
        if journey_id:
            payload["journeyId"] = journey_id
        result = self.request("/connect", method="POST", body=payload)
        if not result.ok or not isinstance(result.body, dict):
            raise LauncherLocalApiError(result.status, result.body)
        return result.body


def exchange_signup_single_use_token(
    single_use_token: str,
    *,
    signup_base_url: str = DEFAULT_SIGNUP_SERVICE_BASE_URL,
    world_api_base_url: str = DEFAULT_WORLD_API_BASE_URL,
    probe_world_api: bool = False,
) -> dict[str, Any]:
    endpoint = f"{signup_base_url.rstrip('/')}/api/v2/token/launcher"
    result = request_http(endpoint, method="POST", body={"token": single_use_token})
    report: dict[str, Any] = {
        "endpoint": endpoint,
        "ok": result.ok,
        "status": result.status,
        "returned_keys": [],
    }
    if not result.ok or not isinstance(result.body, dict):
        report["body"] = result.body
        return report

    report["returned_keys"] = sorted(result.body.keys())
    access_token = result.body.get("accessToken") or result.body.get("access_token") or ""
    refresh_token = result.body.get("refreshToken") or result.body.get("refresh_token") or ""
    id_token = result.body.get("idToken") or result.body.get("id_token") or ""

    if access_token:
        access_claims = decode_jwt_claims(access_token)
        report["access_token_claims"] = summarize_claims(access_claims)
        report["user_id"] = access_claims.get("eve_sub") or access_claims.get("sub")
    if refresh_token:
        report["refresh_token_present"] = True
    if id_token:
        report["id_token_claims"] = summarize_claims(decode_jwt_claims(id_token))

    if probe_world_api and access_token:
        probe = request_json(
            f"{world_api_base_url.rstrip('/')}/v2/characters/me/jumps",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        report["world_api_probe"] = {
            "ok": probe["ok"],
            "status": probe["status"],
            "body": probe["body"],
        }
        report["accepted_by_world_api"] = probe["ok"]

    return report

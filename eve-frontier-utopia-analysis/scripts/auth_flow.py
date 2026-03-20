#!/usr/bin/env python3
"""Remote-only authentication flow for EVE Frontier.

All auth operations go through remote SSO/OAuth endpoints.
No local process detection, no `ps` commands, no localhost calls.

Supported flows:
- Explicit bearer token (env var or parameter)
- Refresh token exchange via auth companion
- Single-use signup token exchange
- SSO OAuth2 authorize URL generation
- World API bearer validation
"""
from __future__ import annotations

import base64
import json
import os
import urllib.parse
from dataclasses import dataclass
from typing import Any

from game_api_client import (
    DEFAULT_ENV,
    ApiError,
    get_env_config,
    post_form,
    request_json,
)


# ---------------------------------------------------------------------------
# JWT / masking helpers
# ---------------------------------------------------------------------------

def decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return value
    name, domain = value.split("@", 1)
    if len(name) <= 2:
        return "*" * len(name) + "@" + domain
    return name[:1] + "*" * (len(name) - 2) + name[-1:] + "@" + domain


def mask_identifier(value: str | None, *, leading: int = 8, trailing: int = 4) -> str | None:
    if not value:
        return value
    if len(value) <= leading + trailing:
        return value[:1] + "*" * max(0, len(value) - 2) + value[-1:] if len(value) > 2 else "*" * len(value)
    return f"{value[:leading]}...{value[-trailing:]}"


def summarize_claims(claims: dict[str, Any]) -> dict[str, Any]:
    return {
        "aud": claims.get("aud"),
        "iss": claims.get("iss"),
        "scope": claims.get("scope") or claims.get("scp"),
        "tenant": claims.get("tenant"),
        "email": mask_email(claims.get("email")),
        "name": claims.get("name"),
        "application_id": claims.get("applicationId"),
        "sub": claims.get("sub"),
    }


# ---------------------------------------------------------------------------
# Auth token container
# ---------------------------------------------------------------------------

@dataclass
class AuthToken:
    token: str
    source: str
    claims: dict[str, Any]
    valid: bool | None = None


# ---------------------------------------------------------------------------
# Auth flow client
# ---------------------------------------------------------------------------

class AuthFlowClient:
    """Remote-only authentication flow manager.

    All operations use remote HTTP endpoints:
    - Auth Companion for refresh token exchange
    - SSO for OAuth2 authorize & signup token exchange
    - World API for bearer validation

    No local process detection or localhost calls.
    """

    def __init__(self, env: str = DEFAULT_ENV) -> None:
        self.env = env
        self._config = get_env_config(env)

    @property
    def auth_companion_url(self) -> str:
        return self._config["auth_companion"]

    @property
    def sso_url(self) -> str:
        return self._config["sso"]

    @property
    def signup_url(self) -> str:
        return self._config["signup"]

    @property
    def world_api_url(self) -> str:
        return self._config["world_api"]

    # -- Bearer resolution --

    def resolve_bearer(
        self,
        *,
        explicit_token: str = "",
        refresh_token: str = "",
        client_id: str = "",
        validate: bool = True,
    ) -> tuple[str | None, dict[str, Any]]:
        """Resolve a valid World API bearer token from available credentials.

        Priority:
        1. Explicit token (parameter or EVE_FRONTIER_BEARER env var)
        2. Refresh token exchange (parameter or EVE_FRONTIER_REFRESH_TOKEN env var)

        When ``validate`` is True, probes /v2/characters/me/jumps to confirm
        each candidate is accepted by the World API.
        """
        report: dict[str, Any] = {"candidates": [], "accepted_token": None}
        candidates: list[AuthToken] = []

        token = explicit_token or os.environ.get("EVE_FRONTIER_BEARER", "")
        if token:
            claims = decode_jwt_claims(token)
            candidates.append(AuthToken(token=token, source="explicit", claims=claims))
            report["candidates"].append({"source": "explicit", "claims": summarize_claims(claims)})

        r_token = refresh_token or os.environ.get("EVE_FRONTIER_REFRESH_TOKEN", "")
        r_client = client_id or os.environ.get("EVE_FRONTIER_CLIENT_ID", "")
        if r_token and r_client:
            exchange = self.exchange_refresh_token(r_token, r_client)
            report["refresh_exchange"] = {
                "ok": exchange["ok"],
                "status": exchange.get("status"),
                "keys": sorted(exchange["body"].keys()) if exchange["ok"] and isinstance(exchange.get("body"), dict) else [],
            }
            if exchange["ok"] and isinstance(exchange.get("body"), dict):
                for field_name in ("access_token", "id_token"):
                    t = exchange["body"].get(field_name)
                    if t:
                        claims = decode_jwt_claims(t)
                        src = f"refresh_{field_name}"
                        candidates.append(AuthToken(token=t, source=src, claims=claims))
                        report["candidates"].append({"source": src, "claims": summarize_claims(claims)})

        if validate:
            accepted = None
            probes: list[dict[str, Any]] = []
            for c in candidates:
                probe = self.validate_bearer(c.token)
                c.valid = probe["ok"]
                probes.append({"source": c.source, "ok": probe["ok"], "status": probe.get("status")})
                if probe["ok"] and accepted is None:
                    accepted = c.token
                    report["accepted_token"] = {"source": c.source, "claims": summarize_claims(c.claims)}
            report["validation_probes"] = probes
            return accepted, report

        if candidates:
            first = candidates[0]
            report["accepted_token"] = {"source": first.source, "claims": summarize_claims(first.claims)}
            return first.token, report

        return None, report

    # -- Token exchange --

    def exchange_refresh_token(self, refresh_token: str, client_id: str) -> dict[str, Any]:
        """Exchange a refresh token for new access/id tokens via auth companion."""
        return post_form(
            f"{self.auth_companion_url}/oauth2/token",
            {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
            },
        )

    def exchange_signup_token(self, single_use_token: str) -> dict[str, Any]:
        """Exchange a single-use signup token via the SSO launcher endpoint."""
        endpoint = f"{self.signup_url.rstrip('/')}/api/v2/token/launcher"
        result = request_json(endpoint, method="POST", body={"token": single_use_token})
        report: dict[str, Any] = {
            "endpoint": endpoint,
            "ok": result["ok"],
            "status": result.get("status"),
        }
        if result["ok"] and isinstance(result.get("body"), dict):
            body = result["body"]
            report["returned_keys"] = sorted(body.keys())
            access = body.get("accessToken") or body.get("access_token") or ""
            if access:
                report["access_token_claims"] = summarize_claims(decode_jwt_claims(access))
            report["refresh_token_present"] = bool(body.get("refreshToken") or body.get("refresh_token"))
            id_tok = body.get("idToken") or body.get("id_token") or ""
            if id_tok:
                report["id_token_claims"] = summarize_claims(decode_jwt_claims(id_tok))
        return report

    # -- Validation --

    def validate_bearer(self, token: str) -> dict[str, Any]:
        """Validate a bearer token against the World API protected endpoint."""
        return request_json(
            f"{self.world_api_url.rstrip('/')}/v2/characters/me/jumps",
            headers={"Authorization": f"Bearer {token}"},
        )

    # -- SSO helpers --

    def get_sso_authorize_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        state: str = "",
    ) -> str:
        """Build an SSO OAuth2 authorize URL for the browser login flow."""
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email offline_access",
        }
        if state:
            params["state"] = state
        return f"{self.sso_url}/v2/oauth/authorize?{urllib.parse.urlencode(params)}"

    def exchange_auth_code(
        self,
        code: str,
        *,
        client_id: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange an OAuth2 authorization code for tokens."""
        return post_form(
            f"{self.auth_companion_url}/oauth2/token",
            {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )


# ---------------------------------------------------------------------------
# Convenience wrapper matching the old resolve_world_api_auth signature
# ---------------------------------------------------------------------------

def resolve_world_api_auth(
    *,
    base_url: str = "",
    explicit_bearer_token: str = "",
    refresh_token: str = "",
    client_id: str = "",
    probe_world_api: bool = True,
    env: str = DEFAULT_ENV,
) -> tuple[str | None, dict[str, Any]]:
    """Resolve a World API bearer token from available credentials (remote-only).

    Drop-in replacement for the old auth_session.resolve_world_api_auth that
    used local process detection.  Now fully remote.
    """
    auth = AuthFlowClient(env=env)
    if base_url:
        auth._config = dict(auth._config)
        auth._config["world_api"] = base_url

    return auth.resolve_bearer(
        explicit_token=explicit_bearer_token,
        refresh_token=refresh_token,
        client_id=client_id,
        validate=probe_world_api,
    )

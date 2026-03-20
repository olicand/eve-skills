#!/usr/bin/env python3
"""Per-user session manager for EVE Frontier AI Agent.

Manages authentication state for each user across chat interactions.
Supports multiple frontends (Telegram, Discord, web, CLI).

Architecture:
    User123 → SessionManager.get_session("user123")
           → UserSession(bearer_token=..., wallet=..., expires_at=...)
           → GameClient(bearer_token=..., wallet_address=...)
           → execute skills

Storage: JSON file-based for simplicity (swap for Redis/DB in production).
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from auth_flow import AuthFlowClient, decode_jwt_claims, mask_identifier
from game_api_client import DEFAULT_ENV, GameClient


DEFAULT_SESSION_DIR = Path(
    os.environ.get(
        "EVE_SESSION_DIR",
        str(Path(__file__).resolve().parent.parent.parent / "output" / "sessions"),
    )
)

SSO_CLIENT_ID = os.environ.get("EVE_FRONTIER_CLIENT_ID", "")
SSO_REDIRECT_URI = os.environ.get("EVE_FRONTIER_REDIRECT_URI", "")


@dataclass
class UserSession:
    user_id: str
    bearer_token: str = ""
    wallet_address: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0
    env: str = DEFAULT_ENV
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    login_state: str = ""

    @property
    def is_authenticated(self) -> bool:
        return bool(self.bearer_token or self.wallet_address)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return time.time() > self.expires_at

    @property
    def needs_refresh(self) -> bool:
        return self.is_expired and bool(self.refresh_token)

    def to_client(self) -> GameClient:
        return GameClient(
            env=self.env,
            bearer_token=self.bearer_token,
            wallet_address=self.wallet_address,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "authenticated": self.is_authenticated,
            "has_bearer": bool(self.bearer_token),
            "has_wallet": bool(self.wallet_address),
            "bearer_masked": mask_identifier(self.bearer_token) if self.bearer_token else None,
            "wallet_masked": mask_identifier(self.wallet_address) if self.wallet_address else None,
            "expired": self.is_expired,
            "env": self.env,
        }


class SessionManager:
    """Manages per-user authentication sessions.

    Each user (identified by platform + user ID) gets a persistent session
    that stores their authentication credentials.

    Usage:
        mgr = SessionManager()
        session = mgr.get_session("tg_123456")
        if not session.is_authenticated:
            url = mgr.start_login(session)
            # send url to user
        else:
            client = session.to_client()
            result = client.world.list_ships()
    """

    def __init__(self, session_dir: Path = DEFAULT_SESSION_DIR, env: str = DEFAULT_ENV) -> None:
        self.session_dir = session_dir
        self.env = env
        self._sessions: dict[str, UserSession] = {}
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, user_id: str) -> Path:
        safe_id = user_id.replace("/", "_").replace("\\", "_")
        return self.session_dir / f"{safe_id}.json"

    def get_session(self, user_id: str) -> UserSession:
        if user_id in self._sessions:
            session = self._sessions[user_id]
            session.last_used_at = time.time()
            return session

        path = self._session_path(user_id)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                session = UserSession(**{
                    k: v for k, v in data.items()
                    if k in UserSession.__dataclass_fields__
                })
                session.last_used_at = time.time()
                self._sessions[user_id] = session
                return session
            except Exception:
                pass

        session = UserSession(user_id=user_id, env=self.env)
        self._sessions[user_id] = session
        return session

    def save_session(self, session: UserSession) -> None:
        self._sessions[session.user_id] = session
        path = self._session_path(session.user_id)
        path.write_text(json.dumps(asdict(session), indent=2, ensure_ascii=True) + "\n")

    def delete_session(self, user_id: str) -> None:
        self._sessions.pop(user_id, None)
        path = self._session_path(user_id)
        if path.exists():
            path.unlink()

    # -- Login flows --

    def start_login(
        self,
        session: UserSession,
        *,
        client_id: str = "",
        redirect_uri: str = "",
    ) -> dict[str, Any]:
        """Start SSO OAuth2 login flow. Returns a URL for the user to open.

        Flow:
        1. Generate a unique state token
        2. Build SSO authorize URL
        3. Store state in session for later verification
        4. User opens URL in browser → logs in → redirected to callback
        5. Callback calls complete_login() with the auth code
        """
        cid = client_id or SSO_CLIENT_ID
        ruri = redirect_uri or SSO_REDIRECT_URI

        if not cid:
            return {
                "ok": False,
                "error": "SSO client_id not configured",
                "hint": "Set EVE_FRONTIER_CLIENT_ID env var or pass client_id parameter",
            }
        if not ruri:
            return {
                "ok": False,
                "error": "SSO redirect_uri not configured",
                "hint": "Set EVE_FRONTIER_REDIRECT_URI env var or pass redirect_uri parameter",
            }

        state = uuid.uuid4().hex
        session.login_state = state
        self.save_session(session)

        auth = AuthFlowClient(env=session.env)
        url = auth.get_sso_authorize_url(client_id=cid, redirect_uri=ruri, state=state)

        return {
            "ok": True,
            "login_url": url,
            "state": state,
            "instruction": "Open this URL in your browser to log in with EVE Frontier SSO.",
        }

    def complete_login(
        self,
        session: UserSession,
        *,
        code: str,
        state: str = "",
        client_id: str = "",
        redirect_uri: str = "",
    ) -> dict[str, Any]:
        """Complete SSO login by exchanging the auth code for tokens.

        Called after the user is redirected back from SSO with an auth code.
        """
        if state and session.login_state and state != session.login_state:
            return {"ok": False, "error": "State mismatch — possible CSRF attack"}

        cid = client_id or SSO_CLIENT_ID
        ruri = redirect_uri or SSO_REDIRECT_URI

        auth = AuthFlowClient(env=session.env)
        result = auth.exchange_auth_code(code, client_id=cid, redirect_uri=ruri)

        if not result["ok"]:
            return {"ok": False, "error": "Token exchange failed", "detail": result}

        body = result.get("body", {})
        access = body.get("access_token", "")
        refresh = body.get("refresh_token", "")
        expires_in = body.get("expires_in", 3600)

        if access:
            session.bearer_token = access
            session.refresh_token = refresh
            session.expires_at = time.time() + expires_in
            session.login_state = ""
            self.save_session(session)

            claims = decode_jwt_claims(access)
            return {
                "ok": True,
                "message": "Login successful!",
                "user": claims.get("name") or claims.get("sub", "unknown"),
                "expires_in": expires_in,
            }

        return {"ok": False, "error": "No access_token in response", "detail": result}

    def login_with_token(self, session: UserSession, bearer_token: str) -> dict[str, Any]:
        """Direct login with an explicit bearer token (for dev/testing)."""
        session.bearer_token = bearer_token
        session.login_state = ""
        claims = decode_jwt_claims(bearer_token)
        if claims.get("exp"):
            session.expires_at = float(claims["exp"])
        self.save_session(session)
        return {
            "ok": True,
            "message": "Token set successfully.",
            "claims_summary": {
                "name": claims.get("name"),
                "sub": claims.get("sub"),
                "exp": claims.get("exp"),
            },
        }

    def login_with_wallet(self, session: UserSession, wallet_address: str) -> dict[str, Any]:
        """Login with EVE Vault wallet address (for chain queries + tx signing)."""
        if not wallet_address.startswith("0x"):
            return {"ok": False, "error": "Invalid wallet address format. Must start with 0x."}
        session.wallet_address = wallet_address
        self.save_session(session)
        return {
            "ok": True,
            "message": f"Wallet {mask_identifier(wallet_address)} linked.",
        }

    def try_refresh(self, session: UserSession, client_id: str = "") -> dict[str, Any]:
        """Try to refresh an expired bearer token."""
        if not session.refresh_token:
            return {"ok": False, "error": "No refresh token available"}

        cid = client_id or SSO_CLIENT_ID
        if not cid:
            return {"ok": False, "error": "No client_id for refresh"}

        auth = AuthFlowClient(env=session.env)
        result = auth.exchange_refresh_token(session.refresh_token, cid)

        if not result["ok"]:
            return {"ok": False, "error": "Refresh failed", "detail": result}

        body = result.get("body", {})
        access = body.get("access_token", "")
        new_refresh = body.get("refresh_token", session.refresh_token)
        expires_in = body.get("expires_in", 3600)

        if access:
            session.bearer_token = access
            session.refresh_token = new_refresh
            session.expires_at = time.time() + expires_in
            self.save_session(session)
            return {"ok": True, "message": "Token refreshed", "expires_in": expires_in}

        return {"ok": False, "error": "No access_token in refresh response"}

    def ensure_authenticated(self, session: UserSession) -> GameClient | None:
        """Ensure session is authenticated, auto-refreshing if needed.

        Returns a ready-to-use GameClient, or None if not authenticated.
        """
        if session.needs_refresh:
            refresh_result = self.try_refresh(session)
            if not refresh_result["ok"]:
                return None

        if not session.is_authenticated:
            return None

        return session.to_client()

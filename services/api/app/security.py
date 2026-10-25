"""Token encryption, OAuth state, API auth and log redaction."""

from __future__ import annotations

import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .models import OAuthState

STATE_TTL = timedelta(minutes=10)


class TokenCipher:
    """Fernet encryption. TOKEN_ENCRYPTION_KEY may hold several comma-separated keys:
    the first encrypts, all decrypt. That is how key rotation works (see docs/security.md)."""

    def __init__(self, keys: str):
        parts = [k.strip() for k in keys.split(",") if k.strip()]
        if not parts:
            raise ValueError("no encryption key")
        self._f = MultiFernet([Fernet(k.encode()) for k in parts])

    def encrypt(self, plaintext: str) -> str:
        return self._f.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._f.decrypt(ciphertext.encode()).decode()
        except InvalidToken as e:
            raise ValueError("token could not be decrypted with the configured key") from e

    def rotate(self, ciphertext: str) -> str:
        return self._f.rotate(ciphertext.encode()).decode()


def get_cipher() -> TokenCipher:
    key = get_settings().token_encryption_key
    if key is None:
        raise HTTPException(503, "TOKEN_ENCRYPTION_KEY is not configured")
    return TokenCipher(key.get_secret_value())


def new_oauth_state(db: Session) -> str:
    state = secrets.token_urlsafe(32)
    db.add(OAuthState(state=state))
    db.flush()
    return state


def consume_oauth_state(db: Session, state: str | None) -> bool:
    """Single use, time limited, constant-time compared."""
    if not state or len(state) > 128:
        return False
    row = db.get(OAuthState, state)
    if row is None or row.used or not hmac.compare_digest(row.state, state):
        return False
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - created > STATE_TTL:
        return False
    row.used = True
    db.flush()
    return True


def require_api_auth(authorization: str | None = Header(default=None)) -> None:
    """No-op locally (bound to 127.0.0.1). In production a bearer token is mandatory."""
    s = get_settings()
    if s.app_env != "production":
        return
    if s.api_auth_token is None:
        raise HTTPException(503, "API_AUTH_TOKEN must be set in production")
    expected = f"Bearer {s.api_auth_token.get_secret_value()}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(401, "unauthorized")


_KV = re.compile(r"\b(access_token|client_secret|code|token|api_key|secret)=([^&\s\"']+)", re.I)
_JSON = re.compile(r"(\"(?:access_token|client_secret|token|api_key|secret)\"\s*:\s*\")([^\"]+)", re.I)
_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+/]+=*")
_RAW = re.compile(r"\b(?:IG[A-Za-z0-9]{40,}|EAA[A-Za-z0-9]{40,})\b")


def redact(text: str) -> str:
    text = _KV.sub(r"\1=[REDACTED]", text)
    text = _JSON.sub(r"\1[REDACTED]", text)
    text = _BEARER.sub(r"\1[REDACTED]", text)
    return _RAW.sub("[REDACTED]", text)

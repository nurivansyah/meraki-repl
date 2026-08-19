"""TokenService — issue, list, revoke and validate API tokens."""

import hashlib
import secrets
import uuid
from datetime import timedelta

from twin.application.ports import TokenRepository
from twin.domain.tokens import (
    Token,
    TokenAlreadyRevoked,
    TokenInvalid,
    TokenNameRequired,
    now_utc,
)


def hash_token(raw: str) -> str:
    """Deterministic hash of a raw token value for storage and lookup."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token_value() -> str:
    """Generate a new opaque token value (256 bits of entropy, url-safe)."""
    return secrets.token_urlsafe(32)


class TokenService:
    """Application service for issuing, listing, revoking and validating tokens."""

    def __init__(self, repo: TokenRepository):
        self._repo = repo

    async def issue_token(self, name: str, ttl_days: int | None = None) -> tuple[Token, str]:
        """Issue a new token. Returns (Token, raw_value); raw is shown once only."""
        name = (name or "").strip()
        if not name:
            raise TokenNameRequired("token name is required")
        raw = generate_token_value()
        token = Token(
            id=uuid.uuid4(),
            name=name,
            hashed_value=hash_token(raw),
            created_at=now_utc(),
            expires_at=now_utc() + timedelta(days=ttl_days) if ttl_days else None,
        )
        await self._repo.save(token)
        return token, raw

    async def list_tokens(self) -> list[Token]:
        return await self._repo.list_all()

    async def revoke_token(self, token_id: uuid.UUID) -> Token:
        token = await self._repo.get_by_id(token_id)
        if token is None:
            raise TokenInvalid(f"no token with id '{token_id}'")
        if token.revoked_at is not None:
            raise TokenAlreadyRevoked(f"token '{token.name}' is already revoked")
        revoked_at = now_utc()
        await self._repo.revoke(token_id, revoked_at)
        token.revoked_at = revoked_at
        return token

    async def validate_bearer(self, raw: str) -> Token:
        """Validate a raw bearer token. Raises TokenInvalid/Revoked/Expired."""
        token = await self._repo.get_by_hash(hash_token(raw))
        if token is None:
            raise TokenInvalid("invalid token")
        token.ensure_valid()
        return token

    async def create_bootstrap(self, raw: str) -> Token | None:
        """Create a bootstrap token if the store is empty. Returns None if tokens exist."""
        existing = await self._repo.list_all()
        if existing:
            return None
        token = Token(
            id=uuid.uuid4(),
            name="bootstrap",
            hashed_value=hash_token(raw),
            created_at=now_utc(),
        )
        try:
            await self._repo.save(token)
        except Exception:
            # A concurrent worker may have created the bootstrap first; recover
            # by treating the now-existing store as "already bootstrapped".
            if await self._repo.get_by_hash(token.hashed_value) is not None:
                return None
            raise
        return token

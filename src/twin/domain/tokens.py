"""Token domain entity and exceptions for the auth realm."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime


def now_utc() -> datetime:
    """Current UTC time, tz-aware."""
    return datetime.now(UTC)


class TokenError(Exception):
    """Base error for token domain."""


class TokenInvalid(TokenError):
    """The presented token does not match any stored token."""


class TokenRevoked(TokenError):
    """The token has been revoked."""


class TokenExpired(TokenError):
    """The token has expired."""


class TokenAlreadyRevoked(TokenError):
    """The token has already been revoked."""


class TokenNameRequired(TokenError):
    """A token name is required."""


@dataclass
class Token:
    """An API token. Only the hashed value is ever stored or returned."""

    id: uuid.UUID
    name: str
    hashed_value: str
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, at: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at <= (at or now_utc())

    def ensure_valid(self, at: datetime | None = None) -> None:
        """Raise if the token is revoked or expired."""
        if self.revoked_at is not None:
            raise TokenRevoked(f"token '{self.name}' has been revoked")
        if self.is_expired(at):
            raise TokenExpired(f"token '{self.name}' has expired")

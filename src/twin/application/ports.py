"""Ports for the auth realm — interfaces the application depends on."""

import uuid
from datetime import datetime
from typing import Protocol

from twin.domain.tokens import Token


class TokenRepository(Protocol):
    """Storage boundary for API tokens."""

    async def save(self, token: Token) -> None: ...

    async def get_by_id(self, token_id: uuid.UUID) -> Token | None: ...

    async def get_by_hash(self, hashed_value: str) -> Token | None: ...

    async def list_all(self) -> list[Token]: ...

    async def revoke(self, token_id: uuid.UUID, revoked_at: datetime) -> None: ...

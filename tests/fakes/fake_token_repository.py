"""In-memory fake for TokenRepository, used at the application boundary in tests."""

import uuid
from datetime import datetime

from twin.domain.tokens import Token


class FakeTokenRepository:
    """In-memory token store keyed by id, with a hash index for lookup."""

    def __init__(self):
        self._by_id: dict[uuid.UUID, Token] = {}
        self._by_hash: dict[str, Token] = {}

    async def save(self, token: Token) -> None:
        self._by_id[token.id] = token
        self._by_hash[token.hashed_value] = token

    async def get_by_id(self, token_id: uuid.UUID) -> Token | None:
        return self._by_id.get(token_id)

    async def get_by_hash(self, hashed_value: str) -> Token | None:
        return self._by_hash.get(hashed_value)

    async def list_all(self) -> list[Token]:
        return list(self._by_id.values())

    async def revoke(self, token_id: uuid.UUID, revoked_at: datetime) -> None:
        token = self._by_id[token_id]
        token.revoked_at = revoked_at

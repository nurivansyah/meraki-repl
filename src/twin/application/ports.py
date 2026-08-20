"""Ports — interfaces the application depends on (auth realm + graph projection)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from twin.domain.tokens import Token


class TokenRepository(Protocol):
    """Storage boundary for API tokens."""

    async def save(self, token: Token) -> None: ...

    async def get_by_id(self, token_id: uuid.UUID) -> Token | None: ...

    async def get_by_hash(self, hashed_value: str) -> Token | None: ...

    async def list_all(self) -> list[Token]: ...

    async def revoke(self, token_id: uuid.UUID, revoked_at: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class CypherStatement:
    """A structured Cypher statement consumed by the ``GraphPort``.

    The transform produces these; the real driver translates them to
    ``session.run(query, **params)`` and the fake interprets them directly.
    """

    query: str
    params: dict[str, Any] = field(default_factory=dict)


class GraphPort(Protocol):
    """Storage boundary for the Neo4j graph projection.

    The real adapter translates ``CypherStatement`` objects into
    ``session.run`` calls; the fake interprets them directly.
    """

    async def execute(self, statements: list[CypherStatement]) -> list[dict]:
        """Execute a list of Cypher statements and return result rows."""
        ...

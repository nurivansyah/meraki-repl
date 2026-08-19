"""Postgres-backed TokenRepository using the psycopg async connection pool."""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from psycopg_pool import AsyncConnectionPool

from twin.config import settings
from twin.domain.tokens import Token

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tokens (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    hashed_value TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
"""

_COLUMNS = "id, name, hashed_value, created_at, expires_at, revoked_at"


async def apply_schema(pool: AsyncConnectionPool) -> None:
    """Create the tokens table if it does not exist."""
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_SQL)


class PostgresTokenRepository:
    """TokenRepository over an AsyncConnectionPool."""

    def __init__(self, pool: AsyncConnectionPool):
        self._pool = pool

    async def save(self, token: Token) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                f"""
                INSERT INTO tokens ({_COLUMNS})
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(token.id),
                    token.name,
                    token.hashed_value,
                    token.created_at,
                    token.expires_at,
                    token.revoked_at,
                ),
            )

    async def get_by_id(self, token_id: uuid.UUID) -> Token | None:
        async with self._pool.connection() as conn:
            row = await conn.execute(
                f"""
                SELECT {_COLUMNS}
                FROM tokens WHERE id = %s
                """,
                (str(token_id),),
            )
            record = await row.fetchone()
        return self._row_to_token(record)

    async def get_by_hash(self, hashed_value: str) -> Token | None:
        async with self._pool.connection() as conn:
            row = await conn.execute(
                f"""
                SELECT {_COLUMNS}
                FROM tokens WHERE hashed_value = %s
                """,
                (hashed_value,),
            )
            record = await row.fetchone()
        return self._row_to_token(record)

    async def list_all(self) -> list[Token]:
        async with self._pool.connection() as conn:
            row = await conn.execute(
                f"""
                SELECT {_COLUMNS}
                FROM tokens ORDER BY created_at
                """
            )
            records = await row.fetchall()
        return [self._row_to_token(r) for r in records]

    async def revoke(self, token_id: uuid.UUID, revoked_at: datetime) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "UPDATE tokens SET revoked_at = %s WHERE id = %s",
                (revoked_at, str(token_id)),
            )

    @staticmethod
    def _row_to_token(record) -> Token | None:
        if record is None:
            return None
        token_id, name, hashed_value, created_at, expires_at, revoked_at = record
        return Token(
            id=token_id,
            name=name,
            hashed_value=hashed_value,
            created_at=created_at,
            expires_at=expires_at,
            revoked_at=revoked_at,
        )


@asynccontextmanager
async def postgres_lifespan():
    """Open the Postgres pool, apply schema, yield a repository. No-op in test mode."""
    if os.getenv("TESTING") == "1":
        yield None
        return
    pool = AsyncConnectionPool(
        settings.pg_dsn,
        min_size=1,
        max_size=10,
        open=False,
    )
    await pool.open()
    await apply_schema(pool)
    try:
        yield PostgresTokenRepository(pool)
    finally:
        await pool.close()

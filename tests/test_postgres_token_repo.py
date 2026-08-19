"""Integration tests for PostgresTokenRepository against a real Postgres.

Skipped unless RUN_INTEGRATION=1 and PG_TEST_DSN points at a reachable Postgres.
"""

import os
import uuid

import pytest
from psycopg.errors import UniqueViolation
from psycopg_pool import AsyncConnectionPool

from twin.adapters.postgres_token_repository import (
    PostgresTokenRepository,
    apply_schema,
)
from twin.application.token_service import TokenService, hash_token
from twin.domain.tokens import Token, TokenRevoked, now_utc

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="integration test requires RUN_INTEGRATION=1 and a real Postgres (PG_TEST_DSN)",
)

PG_DSN = os.getenv("PG_TEST_DSN", "postgresql://twin:changeme@localhost:5432/twin")


@pytest.fixture
async def pg_pool():
    pool = AsyncConnectionPool(PG_DSN, min_size=1, max_size=2, open=False)
    await pool.open()
    await apply_schema(pool)
    async with pool.connection() as conn:
        await conn.execute("TRUNCATE tokens")
    try:
        yield pool
    finally:
        await pool.close()


async def test_roundtrip_save_and_load(pg_pool):
    repo = PostgresTokenRepository(pg_pool)
    token = Token(
        id=uuid.uuid4(),
        name="agent-a",
        hashed_value=hash_token("raw-value"),
        created_at=now_utc(),
    )
    await repo.save(token)

    loaded = await repo.get_by_id(token.id)
    assert loaded is not None
    assert loaded.name == "agent-a"
    assert loaded.hashed_value == hash_token("raw-value")


async def test_lookup_by_hash(pg_pool):
    repo = PostgresTokenRepository(pg_pool)
    raw = "seed-integration"
    token = Token(
        id=uuid.uuid4(),
        name="agent-b",
        hashed_value=hash_token(raw),
        created_at=now_utc(),
    )
    await repo.save(token)

    found = await repo.get_by_hash(hash_token(raw))
    assert found is not None
    assert found.id == token.id


async def test_revoke_marks_token(pg_pool):
    repo = PostgresTokenRepository(pg_pool)
    token = Token(
        id=uuid.uuid4(),
        name="agent-c",
        hashed_value=hash_token("raw-c"),
        created_at=now_utc(),
    )
    await repo.save(token)

    await repo.revoke(token.id, now_utc())

    loaded = await repo.get_by_id(token.id)
    assert loaded is not None
    assert loaded.revoked_at is not None
    with pytest.raises(TokenRevoked):
        await TokenService(repo).validate_bearer("raw-c")


async def test_unique_hashed_value_constraint(pg_pool):
    repo = PostgresTokenRepository(pg_pool)
    created_at = now_utc()
    await repo.save(Token(uuid.uuid4(), "a", "dup-hash", created_at))

    with pytest.raises(UniqueViolation):
        await repo.save(Token(uuid.uuid4(), "b", "dup-hash", created_at))


async def test_list_all_orders_by_created_at(pg_pool):
    repo = PostgresTokenRepository(pg_pool)
    await repo.save(Token(uuid.uuid4(), "first", "h1", now_utc()))
    await repo.save(Token(uuid.uuid4(), "second", "h2", now_utc()))

    tokens = await repo.list_all()
    assert [t.name for t in tokens] == ["first", "second"]

"""Tests for the bootstrap token created on first run."""

from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.application.token_service import TokenService, hash_token
from twin.domain.tokens import now_utc


async def test_create_bootstrap_creates_first_token_when_store_empty():
    repo = FakeTokenRepository()
    service = TokenService(repo)

    token = await service.create_bootstrap("bootstrap-raw-value")

    assert token is not None
    assert token.name == "bootstrap"
    assert token.hashed_value == hash_token("bootstrap-raw-value")
    stored = await repo.get_by_hash(hash_token("bootstrap-raw-value"))
    assert stored is not None
    assert stored.id == token.id


async def test_create_bootstrap_is_noop_when_tokens_exist():
    repo = FakeTokenRepository()
    service = TokenService(repo)
    await service.create_bootstrap("first")

    second = await service.create_bootstrap("second")

    assert second is None
    tokens = await repo.list_all()
    assert len(tokens) == 1
    assert await repo.get_by_hash(hash_token("second")) is None


async def test_bootstrap_token_can_authenticate():
    repo = FakeTokenRepository()
    service = TokenService(repo)
    await service.create_bootstrap("bootstrap-raw-value")

    token = await service.validate_bearer("bootstrap-raw-value")

    assert token.name == "bootstrap"


async def test_bootstrap_token_created_with_created_at():
    repo = FakeTokenRepository()
    service = TokenService(repo)
    before = now_utc()

    token = await service.create_bootstrap("raw")

    assert token.created_at >= before

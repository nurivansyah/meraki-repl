"""REST-contract tests for the token auth realm (S1 seam)."""

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from starlette import status

from tests.fakes.fake_token_repository import FakeTokenRepository
from twin.application.token_service import hash_token
from twin.domain.tokens import Token, now_utc

SEEDED_PLUS_ISSUED = 2
ONE_TOKEN = 1


def _headers(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


async def _seed_and_headers(repo: FakeTokenRepository, name: str = "admin") -> dict[str, str]:
    raw = f"seed-{uuid.uuid4()}"
    token = Token(
        id=uuid.uuid4(),
        name=name,
        hashed_value=hash_token(raw),
        created_at=now_utc(),
    )
    await repo.save(token)
    return _headers(raw)


async def _seed(repo: FakeTokenRepository, name: str = "victim") -> tuple[Token, str]:
    raw = f"seed-{uuid.uuid4()}"
    token = Token(
        id=uuid.uuid4(),
        name=name,
        hashed_value=hash_token(raw),
        created_at=now_utc(),
    )
    await repo.save(token)
    return token, raw


async def test_issue_token_returns_plaintext_once_and_stores_hash(
    client: TestClient, token_repo: FakeTokenRepository
):
    headers = await _seed_and_headers(token_repo)

    response = client.post("/admin/tokens", json={"name": "agent-a"}, headers=headers)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "agent-a"
    raw = data["token"]
    assert raw

    stored = await token_repo.get_by_hash(hash_token(raw))
    assert stored is not None
    assert stored.hashed_value == hash_token(raw)
    assert stored.hashed_value != raw


async def test_issue_token_requires_auth(client: TestClient, token_repo: FakeTokenRepository):
    response = client.post("/admin/tokens", json={"name": "agent-a"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_issue_token_requires_name(client: TestClient, token_repo: FakeTokenRepository):
    headers = await _seed_and_headers(token_repo)
    response = client.post("/admin/tokens", json={"name": "  "}, headers=headers)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_list_tokens_does_not_expose_hash(
    client: TestClient, token_repo: FakeTokenRepository
):
    headers = await _seed_and_headers(token_repo)
    client.post("/admin/tokens", json={"name": "agent-a"}, headers=headers)

    response = client.get("/admin/tokens", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == SEEDED_PLUS_ISSUED
    assert all("hashed_value" not in item for item in data)
    assert all("token" not in item for item in data)


async def test_list_tokens_orders_and_has_expected_shape(
    client: TestClient, token_repo: FakeTokenRepository
):
    headers = await _seed_and_headers(token_repo, name="admin")
    response = client.get("/admin/tokens", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == ONE_TOKEN
    assert data[0]["name"] == "admin"
    assert set(data[0].keys()) == {
        "id",
        "name",
        "created_at",
        "expires_at",
        "revoked_at",
        "revoked",
    }


async def test_revoke_token_stops_authorizing(client: TestClient, token_repo: FakeTokenRepository):
    admin_headers = await _seed_and_headers(token_repo, name="admin")
    victim, victim_raw = await _seed(token_repo)

    assert (
        client.get("/whoami", headers=_headers(victim_raw)).status_code
        == status.HTTP_200_OK
    )

    response = client.delete(f"/admin/tokens/{victim.id}", headers=admin_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    assert (
        client.get("/whoami", headers=_headers(victim_raw)).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


async def test_revoke_missing_token_404(client: TestClient, token_repo: FakeTokenRepository):
    admin_headers = await _seed_and_headers(token_repo, name="admin")
    response = client.delete(f"/admin/tokens/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_revoke_twice_conflict(client: TestClient, token_repo: FakeTokenRepository):
    admin_headers = await _seed_and_headers(token_repo, name="admin")
    victim, _ = await _seed(token_repo)

    first = client.delete(f"/admin/tokens/{victim.id}", headers=admin_headers)
    assert first.status_code == status.HTTP_204_NO_CONTENT
    second = client.delete(f"/admin/tokens/{victim.id}", headers=admin_headers)
    assert second.status_code == status.HTTP_409_CONFLICT


async def test_whoami_requires_bearer(client: TestClient):
    assert client.get("/whoami").status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        client.get("/whoami", headers=_headers("garbage")).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.get("/whoami", headers={"Authorization": "Basic abc"}).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


async def test_whoami_with_valid_token(client: TestClient, token_repo: FakeTokenRepository):
    headers = await _seed_and_headers(token_repo, name="agent-a")
    response = client.get("/whoami", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "agent-a"


async def test_whoami_with_expired_token_rejected(
    client: TestClient, token_repo: FakeTokenRepository
):
    raw = f"seed-{uuid.uuid4()}"
    expired = Token(
        id=uuid.uuid4(),
        name="expired",
        hashed_value=hash_token(raw),
        created_at=now_utc() - timedelta(days=2),
        expires_at=now_utc() - timedelta(days=1),
    )
    await token_repo.save(expired)

    response = client.get("/whoami", headers=_headers(raw))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

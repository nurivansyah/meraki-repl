# 01 — Project scaffold & test seam

**What to build:** the Network Twin application boots with a healthcheck; the compose stack runs the app plus Postgres; configuration (ES hosts/creds, org id, Neo4j URI, NetBox URL/token) comes from the environment; and the single-seam test harness is in place — FastAPI's TestClient driving the app against an in-memory fake of the Elasticsearch client injected at the repository boundary. The layered package skeleton (domain / application / adapters / presentation) exists, and an import-lint rule enforces that domain and application never import from adapters or presentation.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] A `docker compose up` starts the app and Postgres; `/health` returns 200.
- [x] All env config (ES, Postgres, org, Neo4j, NetBox) is read from the environment with sane defaults and failures surface clearly.
- [x] `pytest` runs green with a TestClient fixture that injects an in-memory ES fake at the repository boundary.
- [x] The import-lint rule passes: no dependency from domain/application into adapters/presentation.
- [x] The layering is documented in the README so later tickets slot into known places.

## Implementation notes

- FastAPI app with `/health` and `/` endpoints; lifespan-managed ES client (skipped under `TESTING=1`).
- Compose stack: app + postgres (`postgres:18-alpine`); app image `python:3.14-slim`, `fastapi>=0.141.1`.
- Layered skeleton: `domain/` → `application/` → `adapters/` → `presentation/` with import-lint contracts on domain and application.
- Test seam: `TestClient` + in-memory `FakeElasticsearch` injected at the repository boundary (`tests/conftest.py`).
- Env config via `Settings` (pydantic-settings); `.env.example` committed, `.env` gitignored.
- Verified: pytest green, ruff clean, architecture contracts hold.


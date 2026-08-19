# 01 — Project scaffold & test seam

**What to build:** the Network Twin application boots with a healthcheck; the compose stack runs the app plus Postgres; configuration (ES hosts/creds, org id, Neo4j URI, NetBox URL/token) comes from the environment; and the single-seam test harness is in place — FastAPI's TestClient driving the app against an in-memory fake of the Elasticsearch client injected at the repository boundary. The layered package skeleton (domain / application / adapters / presentation) exists, and an import-lint rule enforces that domain and application never import from adapters or presentation.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A `docker compose up` starts the app and Postgres; `/health` returns 200.
- [ ] All env config (ES, Postgres, org, Neo4j, NetBox) is read from the environment with sane defaults and failures surface clearly.
- [ ] `pytest` runs green with a TestClient fixture that injects an in-memory ES fake at the repository boundary.
- [ ] The import-lint rule passes: no dependency from domain/application into adapters/presentation.
- [ ] The layering is documented in the README so later tickets slot into known places.


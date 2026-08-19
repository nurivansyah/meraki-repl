# 02 — Auth realm: API tokens

**What to build:** machine/agent-facing authentication for the twin: API tokens stored hashed in Postgres, admin endpoints to issue, list, and revoke tokens, a bootstrap token on first run, and bearer-token middleware that protects the REST read mirror and MCP interface. Tests run against an in-memory fake of the auth store at the application boundary, with one integration test proving the real Postgres adapter works.

**Blocked by:** 01 — project scaffold & test seam.

**Status:** done

- [x] An admin can issue a token; only the plaintext is returned once; it is stored hashed.
- [x] Tokens can be listed and revoked; revoked tokens stop authorizing.
- [x] A bootstrap token is created on first run so the admin can reach the admin endpoints.
- [x] Bearer middleware rejects requests with missing/invalid/revoked tokens on the REST surface.
- [x] The Postgres adapter integration test passes against a real Postgres.
- [x] The auth seam is tested through the REST contract, not by asserting on internal calls.

## Implementation notes

- Token values are 256-bit urlsafe secrets; stored hashed with SHA-256 (deterministic, enables lookup-by-hash; bcrypt kept for dashboard user passwords in ticket 09).
- `TokenService` (application) over a `TokenRepository` port; fake repo in `tests/fakes/` injected at the boundary via `app.dependency_overrides`; `PostgresTokenRepository` over `psycopg[binary,pool]` async pool with idempotent `tokens` schema.
- REST surface: `POST /admin/tokens`, `GET /admin/tokens` (never exposes hash/plaintext), `DELETE /admin/tokens/{id}`; all require a valid bearer token; `/whoami` proves the middleware; 401s carry `WWW-Authenticate: Bearer`.
- Bootstrap: on startup, if `BOOTSTRAP_TOKEN` is set and the store is empty, that token is created (name `bootstrap`); race-safe against concurrent workers via unique-hash recovery.
- Naming follows CONTEXT.md ("Auth realm"; avoid "auth service") — the application service is `TokenService`.
- Verified: 17 unit tests + 5 Postgres integration tests green against postgres:18-alpine (compose volume mount updated to `/var/lib/postgresql` for the 18 image layout); ruff clean; architecture contracts hold; live smoke test of bootstrap→issue→revoke flow; code-review findings addressed (rename, atomic bootstrap, public repo access in tests, WWW-Authenticate).

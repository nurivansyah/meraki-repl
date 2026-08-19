# 02 — Auth realm: API tokens

**What to build:** machine/agent-facing authentication for the twin: API tokens stored hashed in Postgres, admin endpoints to issue, list, and revoke tokens, a bootstrap token on first run, and bearer-token middleware that protects the REST read mirror and MCP interface. Tests run against an in-memory fake of the auth store at the application boundary, with one integration test proving the real Postgres adapter works.

**Blocked by:** 01 — project scaffold & test seam.

**Status:** ready-for-agent

- [ ] An admin can issue a token; only the plaintext is returned once; it is stored hashed.
- [ ] Tokens can be listed and revoked; revoked tokens stop authorizing.
- [ ] A bootstrap token is created on first run so the admin can reach the admin endpoints.
- [ ] Bearer middleware rejects requests with missing/invalid/revoked tokens on the REST surface.
- [ ] The Postgres adapter integration test passes against a real Postgres.
- [ ] The auth seam is tested through the REST contract, not by asserting on internal calls.

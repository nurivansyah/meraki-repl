# 06 — MCP server

**What to build:** the MCP interface for AI agents: an SSE/HTTP MCP server exposing the full core operation set as tools — get/list per state domain, events search, changes list — as a thin adapter over the same core the REST mirror uses, protected by the same bearer tokens.

**Blocked by:** 05 — chronology: events + changes.

**Status:** ready-for-agent

- [ ] MCP server starts over SSE/HTTP transport.
- [ ] Tools map one-to-one onto core operations (state get/list, events, changes) with no logic forks.
- [ ] Bearer auth is enforced on MCP connections.
- [ ] One smoke test confirms MCP reaches the same core behavior already covered by the REST seam.

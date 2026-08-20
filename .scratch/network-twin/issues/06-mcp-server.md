# 06 — MCP server

**What to build:** the MCP interface for AI agents: an SSE/HTTP MCP server exposing the full core operation set as tools — get/list per state domain, events search, changes list — as a thin adapter over the same core the REST mirror uses, protected by the same bearer tokens.

**Blocked by:** 05 — chronology: events + changes.

**Status:** done

- [x] MCP server starts over SSE/HTTP transport.
- [x] Tools map one-to-one onto core operations (state get/list, events, changes) with no logic forks.
- [x] Bearer auth is enforced on MCP connections.
- [x] One smoke test confirms MCP reaches the same core behavior already covered by the REST seam.

## Implementation notes

- New `src/twin/presentation/mcp_server.py` — `MCPServer` (`mcp>=2.0.0`) with one `@tool` per core operation: `list_networks`, `get_network`, `list_devices`, `get_device`, `list_uplinks`, `get_uplink`, `list_switchports`, `get_switchport`, `list_vlans`, `get_vlan`, `list_topologies`, `get_topology`, `list_clients`, `get_client`, `list_events`, `list_changes`. Not-found in `get_*` tools raises `ValueError` (the MCP-protocol analogue of REST 404). `mcp_app()` returns the `sse_app()` (SSE at `/sse`, messages at `/messages/`) wrapped in an ASGI bearer guard, mounted at `/mcp` in `main.py`.
- **Single core (spec: no logic forks):** new `src/twin/application/read_mirror.py` — `ReadMirror` application service owns all cross-index joins (network name onto devices/switchports/clients) and the device inventory/metrics merge, plus `search_events`/`list_changes` with `limit` clamped to 1–1000. Both the REST routers (`state_router.py`, `chronology_router.py`) and the MCP tools delegate to it; the presentation surfaces are now pure `asdict(...)` adapters with no data logic.
- Auth: `bearer.py` refactored to expose `validate_bearer_header(authorization, token_service)` shared by the FastAPI `require_bearer` dependency and the MCP ASGI guard — identical parsing, error messages, and `401 + WWW-Authenticate: Bearer`.
- Runtime binding: `configure_runtime(ReadMirror, TokenService)` sets a module-level context; the FastAPI lifespan binds it in production (`ReadMirror(ElasticsearchStateStore(es))`), tests bind it to the fake ES.
- Tests: `tests/test_mcp.py` — one smoke test that boots the real app under uvicorn on a free port (fake ES + fake token repo wired in), asserts unauthenticated `/mcp/sse` → 401, then connects the official `mcp.client.sse.sse_client` + `ClientSession`, initializes, lists tools, and calls `list_networks`/`get_network` against the seeded fake, asserting projected output.
- Dependency: added `mcp>=2.0.0` to `pyproject.toml`. Note: mcp 2.x removed the 1.x `mcp.server.fastmcp` module; the current API is `MCPServer` from `mcp.server.mcpserver` with `sse_app()` / `streamable_http_app()`. Impact analysis is a spec-listed MCP tool but is deferred until the graph/impact core operation exists (the REST `/twin/impact` is likewise not built yet).
- Verified: full suite green (87 unit + 5 skipped; 92 with Postgres integration), ruff clean, architecture contracts hold (domain/application free of adapters/presentation), code review across standards + spec axes.
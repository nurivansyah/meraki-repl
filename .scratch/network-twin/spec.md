# Network Twin — spec

Status: ready-for-agent

## Problem Statement

AI agents and automation need to reason about Meraki network state (device status, uplink IPs, switchports, vlans, topology, clients, syslog events, and change history), but querying the Meraki API directly is constrained: rate limits, latency, credentials sprawl, and verbose responses that burn LLM context tokens. Meanwhile, all the needed state already lives in Elasticsearch — populated continuously by a Logstash pipeline that polls the Meraki API — but it sits behind raw ES query DSL and raw document shapes, which agents and humans cannot productively use.

The project needs a dedicated read surface: a Network Twin application that projects Elasticsearch state into a clean, agent-friendly, eventually-consistent interface — without the twin itself ever touching the Meraki API.

## Solution

Build the Network Twin: a read-only Python application that reads Elasticsearch (the store of record) and exposes:

- A **REST read mirror** — Meraki-shaped endpoints, simplified (fixed org, flat arrays, trimmed fields, read-only), plus twin-specific analytics endpoints.
- An **MCP server** (SSE/HTTP transport) — the same operations as the REST mirror, for AI agents.
- A **Dashboard** — a server-rendered HTML surface (Jinja2 + HTMX + Tailwind) for human operators: Networks page with a topology modal, Devices page with uplinks/clients modals, and a searchable Events page.
- An **auth realm** — Postgres-backed identity. API tokens (issue/list/revoke via admin endpoint, bootstrap token, bearer on REST + MCP) for agents/scripts, and app users with username/password + session cookies for the dashboard. Coexist; no scopes in v1.
- An **ES→Neo4j translation** — rebuilds the topology graph per network; impact analysis runs as Cypher over Neo4j.
- An **ES→NetBox translation** — one-way sync of discovered state (devices + uplink interfaces/IPs, keyed by serial) to keep NetBox current.

Everything the twin serves is eventually consistent and carries explicit freshness (`as_of` = poll time). Deployment: compose stack with the app + Postgres; ES, Neo4j, and NetBox are external.

## User Stories

1. As an AI agent, I want to query Meraki network state through MCP tools, so that I can answer user questions without ever hitting the Meraki API or its rate limits.
2. As an AI agent, I want to query a network's devices, so that I can report inventory and current online/offline status.
3. As an AI agent, I want the device response to merge inventory and availability data, so that one call gives me serial, model, name, network, and status together.
4. As an AI agent, I want to look up uplink addresses for a device, so that I can answer "what is this MX's uplink IP" without API access.
5. As an AI agent, I want every state response to carry an `as_of` timestamp, so that I can judge how fresh the data is and avoid overstating it.
6. As an AI agent, I want to list switchports for a device, so that I can report port status, speed, and duplex.
7. As an AI agent, I want to list vlans for a network, so that I can answer subnet and appliance IP questions.
8. As an AI agent, I want to get a network's topology, so that I can reason about the link layer.
9. As an AI agent, I want to list recently-seen clients, so that I can answer "who's connected" questions using the ephemeral client documents.
10. As an AI agent, I want client responses to be clearly flagged as ephemeral "recently seen" data, so that I do not present idle-but-plugged-in clients as actively connected.
11. As an AI agent, I want to search syslog events over a time range and free-text, so that I can do incident analysis (e.g., wireless connect/disconnect timelines).
12. As an AI agent, I want to list change history for a device or network over a window, so that I can see what changed and when.
13. As an AI agent, I want impact analysis via the graph projection, so that I can answer "what's affected if I disable X" as a Cypher traversal.
14. As a human operator, I want a REST read mirror that mirrors Meraki endpoint shapes, so that my scripts and manual queries are familiar and simple.
15. As a human operator, I want flat arrays and trimmed fields instead of Meraki's pagination envelope, so that responses are small and cheap to consume.
16. As a human operator, I want to issue, list, and revoke API tokens through an admin endpoint, so that each consumer gets its own credential.
17. As a human operator, I want the same bearer token to work on both REST and MCP, so that I manage one credential per consumer.
18. As a human operator, I want the twin to keep NetBox devices and uplink interfaces/IPs up to date from discovered state, so that NetBox reflects reality even before it becomes a source of truth.
19. As an operator, I want the twin to never call the Meraki API itself, so that all rate-limit and credential concerns stay in the Logstash/ES stack.
20. As a developer, I want the ES read core to be the single place projections live, so that REST and MCP are thin adapters over one implementation.
21. As a human operator, I want to reach the twin through a dashboard in a browser, so that I can inspect network state without scripting or tokens.
22. As a human operator, I want to set up the admin account on first launch, so that I control who logs in before anyone can see data.
23. As a human operator, I want to log in with a username and password, so that the dashboard is protected behind my session.
24. As a human operator, I want to browse the Networks page and view a network's topology in a modal, so that I can understand the link layer without the API.
25. As a human operator, I want to browse the Devices page and view an appliance's uplinks and a device's recently-seen clients in modals, so that I can answer operational questions visually.
26. As a human operator, I want to search the syslog event stream from the dashboard, so that I can do incident analysis without querying Elasticsearch.
27. As a developer, I want the dashboard views to render from the same shared core as REST and MCP, so that there is no third implementation to keep in sync.
28. As a developer, I want the codebase layered as domain → application → adapters → presentation with enforced dependency direction, so that changes stay local and tests cross stable seams.
29. As a developer, I want tests written first (red → green) at pre-agreed seams, so that behavior is verified through public interfaces rather than implementation details.
30. As a developer, I want the Postgres auth stores tested through an in-memory fake at the application boundary with one real-adapter integration test, so that the loop stays fast and the real adapter is still proven.

## Implementation Decisions

### Architecture

- **Single core, three surfaces.** One read/query core (FastAPI) owns all projections, chronology queries, impact analysis, and auth logic. REST, MCP, and the dashboard views are all thin adapters over that core. No logic forks between surfaces.
- **Clean architecture, enforced layering.** The app is layered as `domain → application → adapters → presentation`, with an import-lint rule enforcing that domain and application never import from adapters or presentation. Application is the deep module (all real behavior); presentation and adapters stay thin (no duplicated logic). This satisfies ADR-0001's single-core shape.
- **ES is the store of record; the twin is stateless and read-only** (ADR-0001). It never writes to ES and never calls Meraki.
- **Freshness contract.** Eventual consistency with explicit `as_of` on every state response (the `@timestamp` of the state document). No cross-resource transactional guarantees. Clients additionally flagged as ephemeral (seen-window ~1h30m).
- **Scope.** v1 = read mirror + MCP + dashboard + auth + graph projection with deterministic impact analysis + NetBox sync. No capacity simulation, no drift/intent reconciliation (ADR-0004).

### Modules

- **Read core** — one projection per domain, read from the corresponding ES `-metrics` index: networks, devices (inventory merged with availability), uplinks, switchports, vlans, topology, clients. Device projection merges `meraki-device-inventory` + `meraki-device-metrics` + network name. Cross-index context (e.g., network name onto uplink) is already baked in by the pipelines where possible; any residual joins happen here. Chronology: `search_events` over `meraki-syslog-*`, `list_changes` over `*-history-*`.
- **REST read mirror** — Meraki-shaped read endpoints (fixed org, no pagination envelope, trimmed fields, read-only) plus `/twin/impact`, `/twin/events`, `/twin/changes`. Bearer auth enforced.
- **MCP server** — SSE/HTTP transport; tools map one-to-one onto core operations (get/list per domain, impact, events, changes). Same bearer auth.
- **Dashboard** — server-rendered (Jinja2 + HTMX + Tailwind) pages inside the same FastAPI app: Networks (topology modal — structured node/link/offline data, no graph rendering), Devices (uplinks modal gated on `appliance`, clients modal; both plain tables), Events search. Views render from the shared core; no data logic in views.
- **Auth realm** — Postgres-backed identity, two kinds:
  - *Tokens* (agents/scripts/MCP): `tokens` table (hashed token, issued/revoked timestamps, optional expiry); admin endpoints to issue/list/revoke; bootstrap token on first run; bearer middleware on REST and MCP.
  - *App users* (dashboard): `users` table (hashed password) + `sessions` table; setup page served only while no users exist (first visitor creates admin, gated by optional `SETUP_ENABLED` env override); login/logout; opaque session cookie (HttpOnly, SameSite=Lax, +Secure on TLS, idle timeout); CSRF token on the login form. Single admin, no user management in v1.
- **ES→Neo4j sync** — reads topology state per network, rebuilds that network's subgraph. Graph model: `Network` and `Device` nodes; `(Device)-[:IN_NETWORK]->(Network)`; `(Device)-[:LINKED_TO {sourcePort,targetPort}]->(Device)` from `topology.links`. Refresh on new poll timestamp.
- **Impact analysis** — Cypher over Neo4j: walk `LINKED_TO`, mask down/offline devices, return the affected set. Deterministic; no capacity claims.
- **ES→NetBox sync** — one-way discovered-state translation, keyed by serial, additive create/update (NetBox currently empty). v1 payload: devices (name, type matched from model, serial, status from availability `online/offline` → `active/offline`) and uplink interfaces + IP records. URL/token from env.

### ES index contract (read-only assumptions)

- `meraki-network-metrics` (doc id `network id`) · `meraki-device-inventory` + `meraki-device-metrics` (doc id `serial`) · `meraki-uplink-metrics` (`serial-interface`) · `meraki-switchport-metrics` (`serial-portId`) · `meraki-vlan-metrics` (`network_id-vlan_id`) · `meraki-topology-metrics` (`network_id`) · `meraki-client-metrics` (doc id `mac`) · `meraki-syslog-*` (append) · `*-history-*` (changelog, day-partitioned).
- Clients are ephemeral: present means "seen in last ~1h30m", no per-client history.

### Auth

- Tokens stored hashed (e.g., sha256); bearer string returned once at issue. No scopes in v1 (per-consumer trust); same token valid on both surfaces. Admin token issuance is authenticated (bootstrap token).
- App user passwords hashed (e.g., bcrypt/argon2); sessions stored in Postgres as opaque ids. Setup page reachable only while zero users exist (optional `SETUP_ENABLED` env override). Dashboard auth is completely separate from the token system — no cross-dependency.

### Deployment

- `compose.yml` in this repo: app (uvicorn) + Postgres. ES, Neo4j, NetBox external, configured via env (ES hosts/creds, org id, Neo4j URI, NetBox URL/token).

## Testing Decisions

- **Development method is TDD.** Each vertical slice is built red → green: a failing test at a seam first, then the minimal implementation to pass it, one slice per cycle. Tests are written before the code they verify.
- **Seams under test (pre-agreed):**
  - **S1 — REST API** (primary): tests drive the app through FastAPI's TestClient against an in-memory fake of the Elasticsearch client injected at the repository boundary. All core behavior is verified here.
  - **S2 — Sync transforms** (ES→Neo4j, ES→NetBox): pure functions tested directly — they are jobs, not reachable via REST, so they get their own seam (with fake Neo4j/NetBox clients at the boundary).
  - **S3 — Dashboard views** (thin): auth gating + rendering only, through TestClient; no logic re-tested.
  - **MCP**: covered transitively by S1 (thin adapter over the same core) — one smoke test, no seam of its own.
- **Mocking at system boundaries only.** In-memory fakes replace ES, Neo4j, and NetBox clients; application's own modules are never mocked. Postgres-backed auth/session stores are faked at the application boundary for the fast loop, with one real-adapter integration test each proving the actual Postgres adapter works.
- **Good test = external behavior.** Assert on response shape, `as_of` presence, ephemeral-client flagging, merged device projection, filtered lists, and changelog/event query behavior — not on internal function calls. No implementation-coupled or tautological tests.
- **Modules tested:** read core projections (device merge, uplink, clients, topology), chronology (events/changes), impact analysis transform, auth middleware + admin endpoints + dashboard gating, NetBox sync transform, Neo4j sync transform.
- **Prior art:** none yet in this repo — greenfield. S1 is the first-established seam; keep it primary.

## Out of Scope

- Writing to Meraki (control plane) — twin is strictly read-only.
- What-if capacity simulation / congestion prediction (≤2 uplinks, no utilization data).
- Drift/intent reconciliation against NetBox as source of truth (intended state does not exist yet).
- Connected-client history (per-client changelog); client connect/disconnect timelines come from syslog events only.
- Clients in the Neo4j graph projection (ephemeral by design).
- Meraki pagination semantics; multi-organization support; token scopes.
- Structured parsing of raw syslog fields (field richness depends on a future Logstash parsing pipeline; the twin's access surface is stable regardless).
- Dashboard: user management (multiple users / roles) — single admin in v1; rendered topology *graph* (structured data only); dashboard actions that mutate anything — pure display + search.

## Further Notes

- The Logstash pipelines (in the elk repo) define cadence: networks/inventory 12h, availability/uplinks 5m, switchports/topology/vlans 60m, clients 15m, syslog real-time push. The twin inherits these freshness bounds and surfaces them via `as_of`.
- A client active across multiple devices settles to the last-polled device's `network_id`/`serial` (one doc per MAC, last write wins) — the twin should treat device fields as "the device that most recently reported it", not a definitive single home.
- The dashboard setup page behavior (empty users → setup, else login) mirrors common appliance flows; the optional `SETUP_ENABLED` env override is the escape hatch if the app ever crosses a trust boundary.
- Contradicts nothing in existing ADRs; consistent with ADR-0001 through ADR-0004.

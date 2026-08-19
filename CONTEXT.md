# Meraki Network Twin

The read-only, agent-facing interface to Meraki network state. Elasticsearch (fed by Logstash polling the Meraki API) is the memory bank; the Network Twin is the analytical layer that projects it for AI agents, humans, and scripts. It never calls the Meraki API itself.

## Language

### Core

**Twin**:
The application that reads discovered state from Elasticsearch and exposes it as a REST read mirror, MCP interface, and dashboard, and translates it into a graph projection and NetBox. Never writes to Elasticsearch and never calls the Meraki API.
_Avoid_: replica, mirror-of-API, dashboard clone

**Discovered state**:
What the twin knows from Elasticsearch — the ground truth used today.
_Avoid_: live state, real-time state

**Intended state**:
A separate source (NetBox) that would describe how the network *should* be. Not active yet; NetBox is currently a sync target, not a source of truth.
_Avoid_: desired state (when meaning the future NetBox source)

**Freshness (as-of)**:
The measure of how recent a piece of state is. Every state response carries an `as_of` timestamp (the poll time); the twin is eventually consistent by construction and never promises cross-resource transactional consistency.
_Avoid_: live, real-time, up-to-date

**Impact analysis**:
Deterministic graph traversal over the graph projection ("what is affected if I disable X", failover-path check). Not a capacity simulation.
_Avoid_: blast radius simulation, what-if simulation

### Documents in Elasticsearch

**State document**:
One-doc-per-entity snapshot in a `-metrics` index, keyed by `document_id`, written on each poll. Carries the poll time as `@timestamp`.
_Avoid_: metric, snapshot record

**Changelog document**:
A `-history-*` document written when a watched field changed between polls — current state plus `history.previous`.
_Avoid_: history, audit trail

**Event document**:
A raw syslog line in `meraki-syslog-*`, append-only, arriving in real time. The source for connect/disconnect timelines and incident analysis.
_Avoid_: log entry, syslog record

**Client document**:
An ephemeral "recently seen" record in `meraki-client-metrics`, one per normalized MAC. Purged ~1h30m after last seen; does not mean "currently connected".
_Avoid_: connected client, current client

**Client seen-window**:
The ~30-minute activity window (plus ~1h purge lag) that defines whether a client document exists. A client present means "seen recently", not "plugged in".
_Avoid_: online client

### Surfaces

**Read mirror**:
The REST API that mirrors Meraki endpoint shapes in simplified form (fixed org, flat arrays, trimmed fields, read-only).
_Avoid_: Meraki clone, passthrough

**Graph projection**:
The topology graph stored in Neo4j (external), rebuilt from Elasticsearch by the twin, queried via Cypher.
_Avoid_: topology store, graph database

**NetBox sync**:
The one-way translation of discovered state into NetBox (devices and uplink interfaces/IPs, keyed by serial), keeping NetBox current. Middleware posture.
_Avoid_: NetBox integration, CMDB replication

**Auth realm**:
The Postgres-backed identity system with two kinds of credential: bearer tokens for agents/scripts/MCP, and app users with sessions for the dashboard. Admin endpoints issue/list/revoke tokens; the first app user is created on the setup flow.
_Avoid_: auth service, identity provider

**Dashboard**:
The server-rendered HTML surface (Jinja2 + HTMX + Tailwind) for human operators, rendering from the shared core — a third renderer over the same logic, not a separate implementation.
_Avoid_: frontend, UI app

**App user**:
A human identity with username/password who logs into the dashboard via a session. Distinct from agents, which authenticate by bearer token. Single admin in v1.
_Avoid_: user account (when meaning an API token), operator profile

**Session**:
A server-side record of an app user's logged-in state, stored in Postgres, carried by an opaque HttpOnly cookie. Revocable by logout or idle expiry.
_Avoid_: JWT, auth token (when meaning a session)

**Setup flow**:
The first-run page served only while no app user exists, on which the first visitor creates the admin account. Gated by an optional `SETUP_ENABLED` env override.
_Avoid_: onboarding, bootstrap account (for the dashboard)

**View route**:
A dashboard page handler that renders HTML from the shared core, distinct from a read-mirror resource that returns JSON.
_Avoid_: endpoint (when meaning a dashboard page), page controller

**Clients**:
Endpoint clients tracked by Meraki (switches, wireless APs, MX). Out of the graph projection by design — they are ephemeral.
_Avoid_: users, devices

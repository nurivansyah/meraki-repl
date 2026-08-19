# 03 — State read mirror: networks + devices

**What to build:** the first slice of the REST read mirror, bearer-protected: list and get-by-id endpoints for networks, and list (with filters) and get-by-serial endpoints for devices, where a device response merges inventory, availability, and network name into one payload. Every state response carries an `as_of` freshness timestamp. Responses are flat arrays with trimmed fields and a fixed org — no pagination envelope.

**Blocked by:** 02 — auth realm: API tokens.

**Status:** done

- [x] `GET` networks returns the network list with trimmed fields and `as_of`.
- [x] `GET` devices returns devices; filters (network, product type, status) work.
- [x] A device response merges inventory + availability + network name into one object.
- [x] `GET` a single network and single device by id/serial work.
- [x] Every response carries `as_of`; responses are flat arrays without Meraki's pagination envelope.
- [x] Unauthenticated requests are rejected; bearer auth works on every endpoint.
- [x] Projection logic is tested through the REST seam with the in-memory ES fake.

## Implementation notes

- Layering: `domain/networks.py` (`Network`) and `domain/devices.py` (`Device`) are the projected entities; `application/state_store.py` defines raw ES document dataclasses (`NetworkDocument`, `DeviceInventoryDocument`, `DeviceMetricsDocument`, all carrying `as_of` from `@timestamp`) plus the `StateStore` protocol; `application/state_projector.py` composes raw docs into entities; `adapters/elasticsearch_state_store.py` implements the protocol over `AsyncElasticsearch`.
- Index contracts (from the Logstash pipelines): `meraki-network-metrics` (doc id = network_id), `meraki-device-inventory` (doc id = serial), `meraki-device-metrics` (doc id = serial, carries `status` only). Filters map to `bool.filter` with `term` clauses; `meraki_org_id` is always ANDed server-side. ES `size` capped at 10000.
- Endpoints: `GET /networks`, `GET /networks/{id}`, `GET /devices?network_id&product_type&status`, `GET /devices/{serial}` — all bearer-protected, 401s carry `WWW-Authenticate: Bearer`.
- Filter semantics: a `status` filter makes availability the primary side; a `product_type` filter makes inventory primary; with no restrictive filter the two sides union (liberal merge — a device present on only one side still materialises). The non-primary side enriches rather than expands.
- The state store dependency is built from the ES client via `Depends(get_es_client)`, so tests inject `FakeElasticsearch` (enhanced `search` to apply `match_all`/`term`/`bool.filter`, `get` returns `found: false` on miss) at the repository boundary per the spec.
- Verified: 17 REST-seam tests in `tests/test_state_mirror.py` through the TestClient with seeded fake ES + fake token repo; full suite green (34 unit + 5 Postgres integration); ruff clean; architecture contracts hold (domain/application free of adapters/presentation); live smoke test of whoami + networks + devices flows.
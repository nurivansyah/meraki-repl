# 05 — Chronology: events + changes

**What to build:** the twin's timeline surfaces, bearer-protected: search events over the syslog stream (time range + free-text/device/network filters, append-only) and list changes over the `*-history-*` changelog indices for a device or network over a window. These power incident analysis without any caller touching Elasticsearch query DSL.

**Blocked by:** 03 — state read mirror: networks + devices.

**Status:** done

- [x] `/twin/events` searches syslog events with time-range and free-text filters, returning trimmed event docs.
- [x] `/twin/changes` lists changelog entries for a device or network over a window.
- [x] The raw syslog shape is surfaced with a note that structured fields depend on future Logstash parsing; the access surface is stable.
- [x] Both endpoints require bearer auth.
- [x] Chronology queries are tested through the REST seam with the in-memory ES fake.

## Implementation notes

- Domain: `src/twin/domain/events.py` (`Event`), `src/twin/domain/changes.py` (`Change`).
- Application: `EventDocument`, `ChangeDocument` raw doc dataclasses added to `state_store.py`; `StateStore` protocol extended with `search_event_documents` and `list_change_documents`; projection functions `project_event` / `project_change` in `state_projector.py`.
- Adapter: `ElasticsearchStateStore` implements both methods. Events use the `meraki-syslog-*` index pattern (append-only, no `meraki_org_id` tag in current pipeline, so no org filter applied). Changes use `meraki-*-history-*` with org filter + term filters on `serial` (device) or `network_id` + time range; results sorted newest-first by `@timestamp`. Helper `_extract_entity_type_from_index` derives entity type from index name; `_extract_entity_id` builds a human-readable key.
- Presentation: new `src/twin/presentation/chronology_router.py` with `GET /twin/events` (params: `start`, `end`, `q`, `device`, `network_id`, `limit`) and `GET /twin/changes` (params: `device`, `network_id`, `start`, `end`, `limit`), both bearer-protected. Registered in `main.py`.
- Tests: `tests/test_events.py` (7 tests), `tests/test_changes.py` (8 tests) — auth gating, empty results, projection shape, time-range filtering, free-text `q`, device filter, network filter, org scoping for changes, sort order.
- `FakeElasticsearch` extended with wildcard index resolution (`meraki-syslog-*`, `meraki-*-history-*`), `range` query clause, `query_string` / `match` clause, and `_index` on search hits.
- Verified: full suite green (86 unit + 5 skipped; 91 with Postgres integration), ruff clean, architecture contracts hold (domain/application free of adapters/presentation), live smoke test of `/twin/events`, `/twin/changes` + 401 passed.
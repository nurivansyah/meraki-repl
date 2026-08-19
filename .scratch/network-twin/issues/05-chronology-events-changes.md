# 05 — Chronology: events + changes

**What to build:** the twin's timeline surfaces, bearer-protected: search events over the syslog stream (time range + free-text/device/network filters, append-only) and list changes over the `*-history-*` changelog indices for a device or network over a window. These power incident analysis without any caller touching Elasticsearch query DSL.

**Blocked by:** 03 — state read mirror: networks + devices.

**Status:** ready-for-agent

- [ ] `/twin/events` searches syslog events with time-range and free-text filters, returning trimmed event docs.
- [ ] `/twin/changes` lists changelog entries for a device or network over a window.
- [ ] The raw syslog shape is surfaced with a note that structured fields depend on future Logstash parsing; the access surface is stable.
- [ ] Both endpoints require bearer auth.
- [ ] Chronology queries are tested through the REST seam with the in-memory ES fake.

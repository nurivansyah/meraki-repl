# 12 — Events search page

**What to build:** the Events page of the dashboard: a searchable view over the syslog event stream — time range and free-text filters, results listed in the authenticated shell — rendering from the shared core's chronology query.

**Blocked by:** 09 — dashboard shell + auth, 05 — chronology: events + changes.

**Status:** ready-for-agent

- [ ] The Events page searches syslog events by time range and free text and lists results.
- [ ] The page renders from the shared core; no data logic lives in the view.
- [ ] The page is only reachable when authenticated.
- [ ] Views are tested thin through TestClient (gating + render, not logic).

# 10 — Networks page + topology modal

**What to build:** the Networks page of the dashboard: a list of networks from the shared core, with a "show topology" button per network that opens a modal rendering the network's structured topology data (node/link/offline lists + counts) — no rendered graph in v1.

**Blocked by:** 09 — dashboard shell + auth, 03 — state read mirror: networks + devices, 04 — state read mirror: uplinks, switchports, vlans, topology, clients.

**Status:** ready-for-agent

- [ ] The Networks page lists networks with their trimmed state and `as_of`.
- [ ] "Show topology" opens a modal with structured node/link/offline data for that network.
- [ ] The page renders from the shared core; no data logic lives in the view.
- [ ] The page is only reachable when authenticated.
- [ ] Views are tested thin through TestClient (gating + render, not logic).

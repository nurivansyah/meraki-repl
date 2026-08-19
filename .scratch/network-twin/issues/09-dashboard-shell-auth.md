# 09 — Dashboard shell + auth

**What to build:** the human-facing dashboard surface: first-run setup page (served only while no app users exist — the first visitor creates the admin account), a login page, logout, opaque session cookies stored in Postgres (HttpOnly, SameSite=Lax, +Secure on TLS, idle timeout), a CSRF token on the login form, and the authenticated app shell with navigation. A single admin user in v1 — no user management yet.

**Blocked by:** 01 — project scaffold & test seam.

**Status:** ready-for-agent

- [ ] With zero users, visiting the app shows the setup page that creates the admin account; no other route is reachable.
- [ ] With an admin present, setup is not exposed; login is required.
- [ ] Logging in sets an opaque session cookie; logging out clears it; idle timeout expires sessions.
- [ ] The login form is CSRF-protected.
- [ ] A layout/nav shell renders after auth, ready for the state pages.
- [ ] Auth gating and rendering are tested through TestClient (views tested thin; no logic duplication).
- [ ] One integration test proves the Postgres session adapter works.

# Pending Improvements

Code review findings for the Kennel Management System. Items marked `[DONE]` were
implemented as part of the initial missing-features sprint. Everything else is
deferred for later validation and prioritization.

---

## Critical — Fix Before Production

| # | Finding | Files | Status |
|---|---------|-------|--------|
| C1 | JWT stored in `localStorage` — vulnerable to XSS; any injected script can steal tokens | `frontend/src/contexts/AuthContext.jsx`, `frontend/src/api/client.js` | Deferred |
| C2 | `SECRET_KEY` has hardcoded default `CHANGE_ME_IN_PRODUCTION`; deployer might forget to set env var | `docker-compose.yml` | Deferred |
| C3 | No CSRF protection on state-changing requests | All POST/PUT/DELETE routes | Deferred |
| C4 | No rate limiting on `/api/auth/login` or other sensitive endpoints | `backend/app/routes/auth.py` | Deferred |
| C5 | SMTP credentials in plaintext `config/smtp.json` | `config/smtp.json` | Deferred |

---

## High — Before First Major Deployment

| # | Finding | Files | Status |
|---|---------|-------|--------|
| H1 | No input `max_length` constraints on unbounded text fields (`Incident.description`, `Issue.description`, etc.) | `backend/app/models/` | Deferred |
| H2 | CORS origins hardcoded; production hostname mismatch if it differs | `backend/app/main.py:38-44` | Deferred |
| H3 | Missing DB indexes — 8 indexes absent, causing full-table scans on filtered columns | `backend/migrations/` | **[DONE]** — `002_add_indexes.sql` |
| H4 | N+1 query problem on list endpoints (e.g., incidents queried per dog in a loop) | `backend/app/routes/owners.py`, `dogs.py` | Deferred |
| H5 | No pagination on list endpoints — all records returned at once | All `list_*` routes | Deferred |
| H6 | `billing.py` hardcoded NIGHTLY_RATES / activity prices — `pricing.json` ignored | `backend/app/services/billing.py` | **[DONE]** |
| H7 | `pacfa.py` hardcoded `SIZE_CLASSES` dict — `pacfa.json` ignored | `backend/app/services/pacfa.py` | **[DONE]** |
| H8 | 14-day billing cycle `check_14day_cycle()` existed but was never triggered | `backend/app/services/billing.py`, `backend/app/routes/calendar.py` | **[DONE]** |
| H9 | Overdue pickup detection: `pickup_overdue_alerted` field existed but no service logic | `backend/app/services/` | **[DONE]** — `overdue.py` |
| H10 | `PICKUP_OVERDUE_THRESHOLD_HOURS` hardcoded in calendar.py instead of reading `system.json` | `backend/app/routes/calendar.py:25` | **[DONE]** |

---

## Medium — Scalability and Security Hardening

| # | Finding | Files | Status |
|---|---------|-------|--------|
| M1 | No database encryption at rest — SQLite file at `/data/kennel.db` unencrypted | `docker-compose.yml` | Deferred |
| M2 | No role-based access control — any authenticated staff can read/write any record | All routes | Deferred |
| M3 | No audit logging — no record of who changed what and when | All models/routes | Deferred |
| M4 | No refresh tokens — 8-hour JWT lifespan is long; no way to revoke | `backend/app/auth.py` | Deferred |
| M5 | No validation on date ordering (dropoff < pickup not enforced) | `backend/app/routes/reservations.py` | Deferred |
| M6 | No password complexity policy in `manage.py add-user` | `backend/manage.py` | Deferred |
| M7 | JSON columns for `line_items`, `vaccination_records`, `override_log` are not schema-validated at the DB layer | `backend/migrations/001_initial_schema.sql` | Deferred |
| M8 | No config file schema validation at startup — malformed JSON not caught until runtime | `backend/app/config.py` | Deferred |
| M9 | Config files not validated for logical correctness (e.g., phase hours must be 0–23) | `config/phases.json` | Deferred |
| M10 | SQLite not recommended for production under concurrent staff writes — lock contention | Infrastructure | Deferred (PostgreSQL migration) |

---

## Low — Polish and Long-Term

| # | Finding | Files | Status |
|---|---------|-------|--------|
| L1 | No React error boundaries — unhandled render error unmounts entire app | `frontend/src/` | Deferred |
| L2 | No loading skeletons — blank screen until API responds | `frontend/src/pages/` | Deferred |
| L3 | No request cancellation — stale API responses can overwrite newer ones | `frontend/src/api/` | Deferred |
| L4 | No request deduplication — double-clicking sends two identical requests | `frontend/src/pages/` | Deferred |
| L5 | No TypeScript — API schema changes break components silently | All `.jsx` / `.js` | Deferred |
| L6 | No ARIA labels or keyboard navigation in frontend | `frontend/src/` | Deferred |
| L7 | Phase logic duplicated in both frontend (`QuickAddWizard.jsx`) and backend (`phase.py`) — two places to update on rule change | `backend/app/services/phase.py`, `frontend/src/pages/Calendar/QuickAddWizard.jsx` | Deferred |
| L8 | No `restart: unless-stopped` policy on Docker services | `docker-compose.yml` | Deferred |
| L9 | No health check in `docker-compose.yml` `healthcheck:` block | `docker-compose.yml` | Deferred |
| L10 | Services use generic `dict` return types instead of `TypedDict` | `backend/app/services/billing.py`, `pacfa.py` | Deferred |
| L11 | Generic `except Exception` swallows failures silently in email / PDF services | `backend/app/services/email.py`, `pdf.py` | Deferred |
| L12 | No soft-delete indexes on `dogs.archived` / `owners.archived` (now added) | `backend/migrations/` | **[DONE]** in 002 |
| L13 | Frontend state reload uses blunt `setRefresh(r => r+1)` pattern — re-fetches entire page | Multiple page components | Deferred |
| L14 | `migrate.py` migration runner splits SQL on `;` — fragile if string literals contain semicolons | `backend/app/main.py` | Deferred |

---

## Testing Gaps (Deferred)

| # | Finding | Status |
|---|---------|--------|
| T1 | No frontend unit tests for `ReservationsPage`, `DogsPage`, `OwnersPage`, `BillsPage` | Deferred |
| T2 | No test for CSRF protection | Deferred (CSRF not implemented) |
| T3 | No test for rate limiting on login | Deferred (rate limiting not implemented) |
| T4 | No test for concurrent reservation creation (race condition) | Deferred |
| T5 | No test for multi-dog billing across cycles | Deferred |
| T6 | IAT overdue alert detection | **[DONE]** — `test_iat_overdue_alert.py` |
| T7 | IAT pricing amounts match `pricing.json` | **[DONE]** — `test_iat_pricing_config.py` |
| T8 | IAT co-housing calendar consistency | **[DONE]** — `test_iat_calendar_cohousing.py` committed |

---

## Validation Checklist

After each deferred item is implemented, mark it `[DONE]` above and run `./scripts/qa.sh`
to confirm all six gates still pass.

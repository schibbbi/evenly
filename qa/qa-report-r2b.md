# QA Report — Round 2b: Roles & Access Control

**Date:** 2026-03-08
**Reviewed by:** QA Agent

---

## Summary

Round 2b is approved. All PIN endpoints are implemented, role guards are applied to all relevant
endpoints, throttle logic is in place, and `pin_hash` is never exposed in any response body.
Two minor findings noted — no blockers.

---

## Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| `bcrypt` in requirements.txt | ✅ | Present from R2 |
| `POST /auth/verify-pin` — returns `{ valid, role }` | ✅ | `app/routers/auth.py:69` |
| `POST /auth/verify-pin` — logs failed attempt | ✅ | via `verify_pin()` in `auth.py:108` |
| `POST /auth/verify-pin` — 429 after 3 failures / 10 min | ✅ | `_check_pin_throttle()` in `auth.py:87` |
| `POST /residents/{id}/change-pin` — own PIN only, any role | ✅ | `auth.py router:95` — checks `active_resident.id != resident_id` |
| `POST /residents/{id}/reset-pin` — admin only, no current PIN | ✅ | `auth.py router:128` — `require_role("admin")` |
| `PINAttemptLog` model | ✅ | `app/models/pin_attempt_log.py` — from R2b setup |
| Alembic migration for PINAttemptLog | ✅ | `0003_pin_attempt_log.py` |
| `get_active_resident` dependency | ✅ | `app/auth.py:41` |
| `require_role` factory | ✅ | `app/auth.py:61` |
| `require_pin_or_role` factory | ✅ | `app/auth.py:134` |
| Role hierarchy: view < edit < admin | ✅ | `ROLE_HIERARCHY = ["view", "edit", "admin"]` |
| Guard `POST /residents` → admin | ✅ | `routers/residents.py:93` |
| Guard `PUT /residents/{id}` → admin | ✅ | `routers/residents.py:133` |
| Guard `POST /rooms` → admin | ✅ | `routers/rooms.py:66` |
| Guard `PUT /rooms/{id}` → admin | ✅ | `routers/rooms.py:101` |
| Guard `POST /devices` → admin | ✅ | `routers/devices.py:72` |
| Guard `PUT /devices/{id}` → admin | ✅ | `routers/devices.py:113` |
| Guard `PUT /households/{id}` → admin | ✅ | `routers/households.py:140` |
| Guard `POST /residents/{id}/preferences` → view | ✅ | `routers/residents.py:154` |
| Guard `GET /residents/{id}/preferences` → view | ✅ | `routers/residents.py:165` |
| `GET /residents` — public, no auth required | ✅ | No guard on `routers/residents.py:124` |
| `GET /health` — public | ✅ | No guard on `main.py:46` |
| `pin_hash` never in response body | ✅ | `ResidentResponse` schema excludes `pin_hash` |
| auth router registered in `main.py` | ✅ | `main.py:40` |
| X-Resident-ID header convention | ✅ | `get_active_resident` reads `x_resident_id` from header |
| Throttle window: 10 min, max 3 failures | ✅ | Constants in `auth.py:32-34` |

---

## Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `app/routers/auth.py:38` | `role: str \| None = None` — on a failed PIN verify, the response returns `valid: false` without `role`, which is correct. However, the OpenAPI schema shows `role` as nullable string, not as a discriminated union. This is a documentation clarity issue only. | Consider using a Union response model or adding a `description` to the field. Not blocking. |
| 2 | NOTE | `app/routers/auth.py:95` | `POST /residents/{resident_id}/change-pin` uses `verify_pin()` to check `current_pin`. This means a failed `change-pin` attempt also increments the throttle counter — which is correct behavior (prevents brute-forcing via change-pin), but worth documenting explicitly. | Add a docstring note: "Failed change-pin attempts count toward throttle." Already correct; document only. |
| 3 | NOTE | `app/routers/households.py` | `POST /households` has no auth guard. This is intentional (bootstrap problem: no residents exist yet), but not explicitly noted in the code. | Add a comment: `# No auth guard — public during first-run setup wizard` |

---

## Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | `POST /auth/verify-pin` with correct PIN for resident_id=1 | `{ "valid": true, "role": "admin" }`, HTTP 200 | ✅ Logic correct — `verify_pin()` checks bcrypt, returns True, role is included |
| 2 | `POST /auth/verify-pin` with wrong PIN (attempt 4 after 3 failures in 10 min) | HTTP 429 with `Retry-After` header | ✅ `_check_pin_throttle()` counts failures in window, raises 429 |
| 3 | `POST /rooms` with `X-Resident-ID` of a view-role resident | HTTP 403, detail mentions role required | ✅ `require_role("admin")` checks index, raises 403 |
| 4 | `POST /rooms` with `X-Resident-ID` of an admin resident | HTTP 201, room created | ✅ Guard passes, endpoint logic executes |
| 5 | `GET /residents` with no `X-Resident-ID` header | HTTP 200, list of residents | ✅ Endpoint has no guard dependency |
| 6 | `POST /residents/{id}/change-pin` with different resident's ID in path | HTTP 403, "You can only change your own PIN" | ✅ `active_resident.id != resident_id` check at line 108 |
| 7 | `POST /residents/{id}/reset-pin` by admin | HTTP 204, PIN updated | ✅ `require_role("admin")` passes, new hash written |

---

## Verdict

- [x] Round approved — proceed to Milestone 1 Review

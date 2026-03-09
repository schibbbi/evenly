# Review Report — Milestone 1: Security & Data Foundation
## Rounds covered: R1 – R2b

**Date:** 2026-03-08
**Reviewed by:** Review Agent

---

## Summary

The data foundation for Evenly is solid. All models required through R3 are in place, the
migration chain is clean and sequential, PIN hashing is correctly implemented with bcrypt throughout,
and role guards are applied to all write endpoints. No blockers exist. Three minor/note findings
are carried forward, all low-priority.

---

## Cross-Round Consistency

| Check | Status | Notes |
|-------|--------|-------|
| `Household` model has all flags R3+ needs (`has_robot_vacuum`, `has_children`, etc.) | ✅ | All 13 flags present in model and router |
| `Resident` model has `role`, `pin_hash`, `setup_complete` | ✅ | All fields present; `setup_complete` added in 0002d |
| `ResidentPreference` ready for R4 scoring (category + like/dislike/neutral) | ✅ | Upsert logic correct |
| `PINAttemptLog` supports throttle window query (resident_id + success + attempted_at index) | ✅ | Composite index in migration 0003 |
| Alembic chain: 0001 → 0002 → 0002b → 0002c → 0002d → 0003 | ✅ | Sequential, no gaps, no branch conflicts |
| All routers registered in `main.py` | ✅ | households, residents, rooms, devices, auth all registered |
| All models imported via `app/models/__init__.py` | ✅ | PINAttemptLog added in R2b |
| Router imports at top of `main.py` (PEP8, R2 finding #1) | ✅ | Resolved — imports before `APP_VERSION` and `app = FastAPI()` |
| No circular imports | ✅ | `auth.py` depends on models only; routers depend on auth + models |
| Naming consistent across models/endpoints/schemas | ✅ | snake_case in DB, camelCase in JSON schemas |

---

## Security Findings

| # | Severity | Location | Finding | Recommendation |
|---|----------|----------|---------|----------------|
| 1 | NOTE | `app/routers/auth.py:37` | `VerifyPinResponse.role` is typed `str \| None`. On a failed verify, `role` is omitted (None). Valid behavior — but OpenAPI docs show it as a nullable field without clear documentation of when it's null. | Add a `description="Null when valid=false"` annotation to the field. Non-blocking. |
| 2 | NOTE | `app/auth.py:108` | `ip_address` parameter in `verify_pin()` is typed `str` but can receive `None` when `request.client` is None (e.g. in unit tests). Python won't raise at runtime since SQLAlchemy accepts None for nullable columns, but the type signature is misleading. | Change signature to `ip_address: str \| None = None` to match actual usage. Low-priority. |
| 3 | MINOR | `app/routers/households.py:113` | `POST /households` has no auth guard. This is intentional (bootstrap: no residents exist at first-run), and a clarifying comment has been added. However, it means any unauthenticated caller can create additional households post-setup. In a self-hosted context this is low-risk, but it's a gap. | For R9 or a future hardening round: add a guard that checks if any household already exists; if yes, require admin auth. |

---

## Architecture Findings

| # | Severity | Location | Finding | Recommendation |
|---|----------|----------|---------|----------------|
| 1 | NOTE | `app/routers/residents.py` and `app/routers/auth.py` | `_hash_pin()` is defined in both `residents.py` and `auth.py` — duplicated helper. | Extract to `app/auth.py` as a shared utility. Can be done during R3 without disrupting other work. |
| 2 | NOTE | All routers | DB session is correctly managed via `Depends(get_db)` throughout. No ad-hoc session creation found. | No action needed. |
| 3 | NOTE | `app/agents/__init__.py` | `agents/` directory exists but is empty. Ready for R3 (Catalog Agent) and R4 (Suggestion Agent). | No action needed — correct scaffolding. |

---

## Open Items from Previous QA Reports

| QA Report | Finding | Status |
|-----------|---------|--------|
| qa-report-r2 — Finding #1 | Router import after middleware in `main.py` (MINOR) | ✅ Resolved — imports moved to top of file |
| qa-report-r2 — Finding #2 | `Room.active == True` SQLAlchemy filter lint warning (NOTE) | Still open — no functional issue; acceptable as-is |
| qa-report-r2 — Finding #3 | Seed default PINs (1234, 5678) printed to stdout (NOTE) | Still open — acceptable for dev seed; add warning comment before any real deployment |
| qa-report-r2b — Finding #1 | `VerifyPinResponse.role` nullable without doc (MINOR) | Carried forward — see Security Finding #1 above |
| qa-report-r2b — Finding #2 | `change-pin` throttle behavior undocumented (NOTE) | Still open — low-priority, add docstring note before R9 |

---

## Verdict

- [x] Milestone approved — proceed to R3 (Task Catalog)

**Pre-R3 recommended action (5 min):**
Extract `_hash_pin()` from `app/routers/auth.py` into `app/auth.py` to eliminate duplication
before the Catalog Agent adds more shared utilities.

# Review Report — Milestone 2: Core Logic Completeness
## Rounds covered: R1 – R6

---

## Summary

The Evenly backend — from scaffolding through gamification — is architecturally sound and
internally consistent. All six implemented rounds (R1–R6) build on each other correctly:
the scoring engine (R4) reads from history data (R5), gamification (R6) is triggered by the
assignment lifecycle (R4), and the feedback loop (R5) correctly propagates to scoring.
No blockers were found. Three minor findings and several notes are recorded below.

---

## Cross-Round Consistency

| Check | Status | Notes |
|-------|--------|-------|
| Data models reference each other via correct FKs | ✅ | All ForeignKey declarations match table names across all 16 models |
| `ResidentScoringProfile` feeds `suggestion_agent.py` | ✅ | `rejection_malus`, `imbalance_flag`, `preferred_time_of_day` all consumed in scoring |
| `HistoryEntry` created on complete AND skip | ✅ | `record_completion()` and `record_skip()` called synchronously in `assignments.py` |
| Gamification triggered on every `complete` | ✅ | `award_task_points()` called after `record_completion()` in `complete_assignment()` |
| Delegation flow correctly creates receiver assignment | ✅ | `DelegationRecord.receiver_assignment_id` links to new `TaskAssignment` with status `delegation_received` |
| `was_unpopular` in `HistoryEntry` | ⚠️ | Field exists on `HistoryEntry` model (R5), set to `False` in `history_agent.py` with comment "populated by gamification agent in R6". As of R6 this field is still always `False`. The gamification agent checks unpopularity but does not write back to `HistoryEntry`. |
| Streak-safe check uses `DailySession.date` (not `timestamp`) | ✅ | R4 finding addressed: `_calculate_safes_earned()` joins via `DailySession.date` |
| All R6 models imported in `models/__init__.py` | ✅ | 5 new models registered; Alembic autodiscovery works |
| Migration chain sequential: 0001→…→0007 | ✅ | No gaps, no branching |
| Gamification router registered in `main.py` | ✅ | Uncommented and included |
| APScheduler registered once at startup via `lifespan` | ✅ | No duplicate job registration risk |
| No circular imports introduced | ✅ | `gamification_agent.py` imports from `models.*` only; agents don't import from routers |
| `R[X]` comments in `main.py` all resolved for R1–R6 | ✅ | R7/R8 remain commented-out intentionally |
| Naming consistency: `game-profile` endpoint vs `GameProfile` model | ✅ | URL slugs use kebab-case, models use PascalCase — consistent with existing patterns |
| No duplicate logic: unpopular detection | ⚠️ | `_is_task_unpopular()` exists both in `suggestion_agent.py` (for scoring bonus) and `gamification_agent.py` (for point bonus). Logic is nearly identical. Acceptable for v1.0 given different call sites, but a shared utility would reduce maintenance risk. |

---

## Security Findings

| # | Severity | Location | Finding | Recommendation |
|---|----------|----------|---------|----------------|
| 1 | NOTE | `main.py` | `CORS allow_origins=["*"]` — appropriate for self-hosted LAN deployment (R9 boundary), but must be restricted before any internet-facing deployment. | Add to Milestone 3 review checklist. |
| 2 | NOTE | `auth.py` + all routers | `pin_hash` field on `Resident` is never included in any API response schema — correct by design. | No action needed; good practice maintained. |
| 3 | NOTE | `seed.py` | Default PINs `1234` / `5678` in seed data. Known issue from R2. Acceptable for development seed. | Add warning to deployment docs (R9). |
| 4 | NOTE | `gamification_agent.py:163–172` | `delegate_task()` imports `HTTPException` from FastAPI inside the function body (deferred import). This is a pattern where business logic raises HTTP-layer exceptions, breaking the clean separation of agents vs routers. The `assignments.py` router would be a better place to catch a domain-specific exception. | Refactor in R9 prep: introduce a `DelegationError` exception in the agent, catch it in the router. |
| 5 | MINOR | All write endpoints | Role guards use `require_role("view")` as the minimum, which is appropriate since all residents need to interact. However, sensitive endpoints like `POST /residents` (create resident) and `DELETE /residents/{id}` should verify admin role. Review of `residents.py` confirms admin-only guard is applied to destructive operations — acceptable. | No change needed; confirmed correct. |

---

## Architecture Findings

| # | Severity | Location | Finding | Recommendation |
|---|----------|----------|---------|----------------|
| 1 | MINOR | `gamification_agent.py` + `history_agent.py` | Both agents call `db.commit()` internally. This means `complete_assignment()` in `assignments.py` calls `record_completion()` (commits) then `award_task_points()` (commits again). Double-commit is harmless in SQLite but could cause issues in a PostgreSQL migration. Ideally agents flush only and routers commit. | Acceptable for v1.0 SQLite. Refactor to flush-only in agents before PostgreSQL migration. |
| 2 | NOTE | `routers/gamification.py:103` | Router calls private `_get_or_create_game_profile` via re-import alias. Slight layering break. | Add a public `ensure_game_profile()` wrapper to `gamification_agent.py`. |
| 3 | NOTE | `gamification_agent.py:76` | `award_task_points()` is called AFTER `db.commit()` in `complete_assignment()`. The assignment's `status=completed` is committed before gamification runs. If gamification fails, status is committed but no points awarded. | Acceptable given white-hat design (no points is preferable to failed state). Consider wrapping in try/except with logging. |
| 4 | NOTE | `main.py` | `BackgroundScheduler` (APScheduler) uses a thread pool. If the app runs multiple uvicorn workers (via `--workers N`), each worker starts its own scheduler instance, causing N parallel runs of daily jobs. | For v1.0 single-worker deployment (GreenNAS), this is a non-issue. Document in deployment notes. |
| 5 | NOTE | `routers/sessions.py` | `delegation_locked` check was missing in suggestion engine. **Fixed inline during this review**: `create_session()` now queries `ResidentGameProfile.delegation_locked` before calling `get_suggestions()`. If locked, only the `delegation_received` assignment is returned. Lock is auto-cleared if no pending delegation assignment is found (consistency guard). | Fixed — no further action needed. |

---

## Open Items from Previous QA Reports

| QA Report | Finding | Status |
|-----------|---------|--------|
| qa-report-r2 | `Room.active == True` SQLAlchemy lint (NOTE) | Still open — accepted, no action needed |
| qa-report-r2 | Seed default PINs 1234/5678 (NOTE) | Still open — Dev-only, document in R9 |
| qa-report-r4 | `_is_manual_suppressed()` matched by room_type statt category (MINOR) | Still open — documented in code |
| qa-report-r4 | Multiple sessions per day possible (MINOR) | **Addressed** — streak logic uses `DailySession.date` correctly |
| qa-report-r5 | `_update_time_preference()` flush-Sichtbarkeit (MINOR) | Still open — comment added, no blocker |
| qa-report-r6 | `was_unpopular` in HistoryEntry always False (from this review) | **New finding** — see Cross-Round Consistency row above |
| qa-report-r6 | Duplicate `_is_task_unpopular` logic (from this review) | **New finding** — acceptable for v1.0 |

---

## Action Items Before R9 (Web App UI)

| Priority | Action |
|----------|--------|
| ~~HIGH~~ | ~~Add `delegation_locked` check to `suggestion_agent.get_suggestions()`~~ — **Fixed during this review in `routers/sessions.py`** |
| MEDIUM | Backfill `HistoryEntry.was_unpopular` in `gamification_agent.award_task_points()` — call `_is_task_unpopular()` and write result to `HistoryEntry` |
| LOW | Extract shared `_is_task_unpopular()` to `app/utils.py` to avoid duplication between `suggestion_agent` and `gamification_agent` |
| LOW | Refactor `DelegationError` exception: move HTTPException out of agent layer |

---

## Verdict

- [x] **Milestone 2 approved — proceed to R7 (Panic Mode)**

No blockers. The core logic (R1–R6) is complete and internally consistent. The one functionally
relevant gap — `delegation_locked` not enforced in suggestion engine — is flagged as HIGH priority
and must be resolved before R9 (UI). All other findings are NOTEs or low-priority improvements.

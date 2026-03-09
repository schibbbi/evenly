# QA Report — Round 7: Panic Mode

## Summary
Round 7 is approved with minor findings. All Panic Mode features are implemented correctly:
prioritized plan generation, time-box enforcement with 10% buffer, round-robin distribution,
normal history/gamification integration, and the three required API endpoints.
One minor finding and two notes are recorded.

---

## Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| **Data Model** | | |
| `PanicSession` model | ✅ | id, activated_by_resident_id, available_minutes, available_resident_ids (JSON), created_at, completed_at, status |
| `task_assignments.panic_session_id` (nullable FK) | ✅ | Migration 0008 recreates table with nullable session_id and new panic_session_id column |
| `task_assignments.session_id` made nullable | ✅ | Supports panic assignments that have no daily session |
| **Panic Agent** | | |
| Priority Tier 1: hallway, bathroom, kitchen, living | ✅ | `TIER_1_ROOMS` constant |
| Priority Tier 2: other (dining, staircase) | ✅ | `TIER_2_ROOMS` constant |
| Priority Tier 3: bedroom, children's room, garden | ✅ | `TIER_3_ROOMS` constant |
| Within tier: sort by visual impact (cleaning > tidying > …) | ✅ | `VISUAL_IMPACT_ORDER` constant |
| Filter: active tasks only | ✅ | `TaskTemplate.is_active == True` |
| Filter: not completed within last 24 hours | ✅ | `_recently_completed_task_ids()` with `RECENT_COMPLETION_HOURS = 24` |
| Ignore energy level | ✅ | No energy filter applied in panic_agent |
| Ignore resident preferences | ✅ | No preference filter applied |
| Fill time slot with 10% buffer | ✅ | `budget_with_buffer = max_minutes * TIME_BUFFER_FACTOR` (1.10) |
| Round-robin distribution across available residents | ✅ | `cycle_index % len(resident_cycle)` |
| Human-readable instruction per task | ✅ | `_build_instruction()` with template strings per category |
| Order note: highlight visible rooms | ✅ | `_build_order_note()` names tier-1 rooms explicitly |
| **API Endpoints** | | |
| `POST /panic` | ✅ | Validates duration (120/180/240), validates household membership |
| `GET /panic/{id}` | ✅ | Returns progress: total/completed/remaining tasks |
| `POST /panic/{id}/complete` | ✅ | Bulk-completes remaining tasks; triggers history + gamification per task |
| Reuse `POST /assignments/{id}/complete` for individual tasks | ✅ | Panic assignments have status=`suggested` — existing endpoint works |
| **Boundaries** | | |
| No gamification override — normal points | ✅ | `award_task_points()` called normally |
| Single-resident panic allowed | ✅ | `min_length=1` on `available_resident_ids` |
| No AI — purely rule-based | ✅ | Only static tier lists and template strings |
| Daily engine not blocked during panic | ✅ | No lock mechanism introduced |
| **Integration** | | |
| `PanicSession` imported in `models/__init__.py` | ✅ | |
| `panic` router registered in `main.py` | ✅ | |
| Migration chain: 0007 → 0008 | ✅ | Correct `down_revision` |
| `history_agent.record_completion()` works for panic assignments | ✅ | Agent uses only `assignment.resident_id`, `task_template_id` — no dependency on `session_id` |
| `gamification_agent.award_task_points()` works for panic assignments | ✅ | Streak-safe calculation joins via DailySession — panic tasks don't count toward daily safe thresholds (correct: no daily session context) |

---

## Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `routers/panic.py:162` | `_build_instruction` and `ROOM_TIER` are imported inside a loop within `_build_progress_response()` (deferred import inside for-loop). Python caches module imports so it's not a performance issue, but it's stylistically unusual and harder to read. | Move imports to top of file. Low priority. |
| 2 | NOTE | `panic_agent.py:160–170` | The time-budget fill loop skips tasks that would exceed the buffer, but doesn't try to backfill with smaller tasks. A 5-minute task could be skipped even if time remains. For a panic scenario this is acceptable (we want the high-priority ones), but could be refined later. | Acceptable for v1.0. Consider a knapsack-style fill in a future pass. |
| 3 | NOTE | `panic_agent.py:128` | `activating_resident.household_id` is used to scope task lookup (recently completed). However, eligible tasks are fetched from ALL households (no household filter on `TaskTemplate`). `TaskTemplate` is a shared catalog (not per-household), so this is correct — but the comment could be clearer. | Add inline comment clarifying that task catalog is household-agnostic. |
| 4 | NOTE | `routers/panic.py:305–320` | `POST /panic/{id}/complete` calls `record_completion()` and `award_task_points()` inside bare `try/except` blocks for best-effort behaviour. If either fails silently, points and history entries are lost without logging. | Add `logger.exception(...)` inside the except blocks to aid debugging. |

---

## Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | `POST /panic` with `available_minutes=120`, 2 residents | Returns plan with tier-1 rooms first, total_planned_minutes ≤ 132 (120 × 1.1) | ✅ Sort key `(tier, visual_impact, duration)` ensures tier-1 first; buffer check `total_minutes >= budget_with_buffer` enforces cap |
| 2 | Plan has hallway/bathroom tasks before bedroom tasks | Tier 1 tasks appear before tier 3 in each resident's list | ✅ `ROOM_TIER["hallway"] = 1`, `ROOM_TIER["bedroom"] = 3`; sorted ascending by tier |
| 3 | 2 residents, 4 tasks → distributed round-robin | Resident A gets tasks 1 & 3, Resident B gets tasks 2 & 4 | ✅ `cycle_index % len(resident_cycle)` with interleaved append |
| 4 | `POST /panic` with `available_minutes=90` | HTTP 422 with clear error message | ✅ `if payload.available_minutes not in VALID_DURATIONS: raise HTTPException(422)` |
| 5 | `POST /panic/{id}/complete` marks all remaining as done | All non-completed assignments set to `completed`; history + gamification triggered | ✅ `pending_assignments` query filters `status.notin_(["completed", "skipped"])` |
| 6 | Completing a panic task via `POST /assignments/{id}/complete` | Works identically to daily task completion; history entry created | ✅ Panic assignments have `status="suggested"` → existing endpoint accepts this |
| 7 | `POST /panic` with resident from a different household | HTTP 400 with "does not belong to the same household" | ✅ Validated in router before PanicSession creation |

---

## Pending Findings (carried from previous rounds)

| Round | Finding | Status |
|-------|---------|--------|
| R2 | `Room.active == True` SQLAlchemy lint | open, accepted |
| R2 | Seed default PINs 1234/5678 | open, Dev-only |
| R4 | `_is_manual_suppressed()` room_type matching | documented |
| R5 | `_update_time_preference()` flush visibility | comment added |
| R6 | `was_unpopular` in HistoryEntry always False | open, low priority |
| R6 | Duplicate `_is_task_unpopular` logic | open, v1.0 acceptable |

---

## Verdict

- [x] **Round approved — proceed to R8 (Calendar Integration)**

No blockers. All briefing requirements are fully implemented. The Panic Mode agent integrates
cleanly with the existing history and gamification pipelines. The migration correctly handles
the SQLite limitation for ALTER COLUMN via table recreation with data copy.

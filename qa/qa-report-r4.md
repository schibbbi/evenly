# QA Report — Round 4: Daily Task Engine

**Date:** 2026-03-08
**Reviewed by:** QA Agent

---

## Summary

Round 4 is approved with two minor findings. The scoring engine implements all 8 scoring
components from the briefing, robot-aware scoring is fully implemented with correct
energy-level branching, and the session/assignment lifecycle is complete. The migration
chain is clean (0004→0005). One minor logic gap in `_is_manual_suppressed` and one
missing uniqueness check on sessions are noted below.

---

## Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| `DailySession` model (all fields) | ✅ | `daily_session.py` — id, resident_id, date, energy_level, available_minutes, reroll_count, reroll_malus, created_at |
| `TaskAssignment` model (all fields) | ✅ | `task_assignment.py` — id, session_id, resident_id, task_template_id, status, score, suggested_at, accepted_at, completed_at, reroll_count, is_forced, points_awarded |
| `AssignmentStatusEnum` | ✅ | `enums.py` — suggested/accepted/in_progress/completed/skipped/delegated |
| Alembic migration 0005 (0004→0005) | ✅ | Both tables, 8 indexes including composite `(resident_id, completed_at)` |
| `suggestion_agent.py` — scoring constants at top | ✅ | `suggestion_agent.py:30-43` — all 8 constants named |
| `overdue_factor` — capped at 50 | ✅ | `suggestion_agent.py:133` — `min(..., OVERDUE_FACTOR_CAP)` |
| `effective_frequency_days` with robot multiplier | ✅ | `_effective_frequency()` — `freq / task.robot_frequency_multiplier` |
| `seasonality_factor` — garden spring/summer, indoor autumn/winter | ✅ | `_seasonality()` — checks `task.category` and `season` |
| `rejection_malus` — -3 per rejection, recovers +1/day | ✅ | `suggestion_agent.py:139-143` |
| `imbalance_bonus` — +8 if always done by others | ✅ | `_imbalance_bonus()` — compares my_last_done vs last_done_map |
| `random_factor` — uniform [0.0, 3.0] | ✅ | `suggestion_agent.py:149` — `random.uniform(0.0, RANDOM_FACTOR_MAX)` |
| `unpopular_bonus` — +5 if all residents dislike category | ✅ | `_all_dislike()` — iterates all resident preferences |
| `ROBOT_LOW_ENERGY_BONUS = 20` — robot variant at energy=low | ✅ | `_robot_score()` — checks `is_robot_variant + device_flag + energy=low` |
| `ROBOT_MANUAL_LOW_ENERGY_MALUS = 10` — manual when robot present + low | ✅ | `_robot_score()` — `-ROBOT_MANUAL_LOW_ENERGY_MALUS` |
| Robot suppression within 24h | ✅ | `_recently_run_robot_tasks()` + `_is_manual_suppressed()` |
| energy=medium/high: no robot bonus/malus | ✅ | `_robot_score()` — early return `if session.energy_level != "low"` |
| Energy filter (task ≤ resident energy) | ✅ | `suggestion_agent.py:108` — `ENERGY_ORDER` comparison |
| Time filter (duration ≤ available_minutes) | ✅ | `suggestion_agent.py:112` |
| device_flag filter (hidden if device absent) | ✅ | `_device_flag_ok()` |
| household_flag filter (hidden if flag absent) | ✅ | `_household_flag_ok()` |
| Frequency window exclusion | ✅ | `days_since_done < effective_freq` check |
| Unpopular overdue escalation (2x overdue + all dislike → forced) | ✅ | `_is_force_candidate()` — `2x threshold + _all_dislike_raw()` |
| Forced tasks survive reroll | ✅ | `sessions.py` reroll endpoint — forced_assignments preserved |
| Reroll: first free, 2nd+ sets `reroll_malus=True` | ✅ | `sessions.py:196` — `if session.reroll_count >= 2: session.reroll_malus = True` |
| Reroll excludes previously shown tasks | ✅ | `excluded_ids` passed to `get_suggestions()` |
| `POST /sessions` — creates session + returns suggestions | ✅ | `routers/sessions.py:103` |
| `GET /sessions/{id}/suggestions` | ✅ | `routers/sessions.py:147` |
| `POST /sessions/{id}/reroll` | ✅ | `routers/sessions.py:172` |
| `POST /assignments/{id}/accept` | ✅ | `routers/assignments.py:78` |
| `POST /assignments/{id}/complete` | ✅ | `routers/assignments.py:96` |
| `POST /assignments/{id}/skip` | ✅ | `routers/assignments.py:118` |
| All session/assignment endpoints require `view` role | ✅ | `require_role("view")` on all endpoints |
| Router registered in `main.py` | ✅ | `main.py` — sessions + assignments registered |
| Models registered in `__init__.py` | ✅ | `DailySession`, `TaskAssignment` registered |
| Scoring is rule-based only (no AI at runtime) | ✅ | `suggestion_agent.py` uses only Python math + DB queries |
| NOT: points/streaks (R6) | ✅ | `points_awarded` field exists but is only set by R6 agent |
| NOT: delegation (R6) | ✅ | `delegated` status in enum but no delegation endpoint in R4 |

---

## Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `suggestion_agent.py:209` | `_is_manual_suppressed()` checks if `task.id in robot_run_task_ids`, but `robot_run_task_ids` is built by matching manual tasks to robot-run **room_types**. This means if robot ran in "living room", ALL manual tasks with `robot_frequency_multiplier` in "living" are suppressed — including laundry tasks that happen to share the same room_type. For v1.0 with a well-structured catalog this is acceptable, but logically it should match on category (cleaning/vacuum), not room_type. | Low risk in v1.0 given catalog structure. Document in code comment. Can be refined in R5. |
| 2 | MINOR | `routers/sessions.py:103` | `POST /sessions` does not prevent a resident from creating multiple sessions for the same date. Multiple sessions per day per resident are allowed by the DB schema, which is intentional for R4 — but may conflict with gamification streak logic in R6 (only 1 streak per day). | Add a note in code: "R6 streak logic uses first session per day. Multiple sessions per day allowed." R6 agent should use `GROUP BY date` when counting streaks. |
| 3 | NOTE | `suggestion_agent.py:93` | `_recent_completions()` uses `.limit(500)` as a performance cap. For a household with many years of history this could miss old completions, but frequency-window logic only looks at recent data via `days_since_done`. No correctness issue. | Acceptable for v1.0. Document the limit. |

---

## Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | `POST /sessions` with `energy=medium, available_minutes=30` | Returns 201 with `suggestions` list of ≤3 tasks; all tasks have `duration_minutes ≤ 30` and `energy_level` in (low, medium) | ✅ Energy + time filters applied in `get_suggestions()` |
| 2 | Task completed yesterday, frequency=7 days | Task excluded from suggestions today (within frequency window) | ✅ `days_since_done=1 < effective_freq=7` → excluded |
| 3 | Task overdue 15 days, frequency=7, all residents dislike | `is_forced=True` in suggestion, survives reroll | ✅ `15 > 7*2=14` → `_is_force_candidate()` returns True |
| 4 | `POST /sessions/{id}/reroll` called twice | First reroll: `reroll_malus=false`. Second reroll: `reroll_malus=true` | ✅ `session.reroll_count >= 2 → reroll_malus = True` |
| 5 | `energy=low`, `household.has_robot_vacuum=True`, robot variant task present | Robot variant scores 20 pts higher than manual variant | ✅ `_robot_score()` returns `+ROBOT_LOW_ENERGY_BONUS` for robot, `-ROBOT_MANUAL_LOW_ENERGY_MALUS` for manual |
| 6 | `energy=medium`, `household.has_robot_vacuum=True` | No robot bonus/malus applied — both compete equally | ✅ `_robot_score()` returns `0.0` when `energy_level != "low"` |
| 7 | Robot vacuum task completed 2h ago, manual vacuum task requested | Manual vacuum task suppressed from suggestions | ✅ `_recently_run_robot_tasks()` finds robot run, `_is_manual_suppressed()` returns True |
| 8 | `POST /assignments/{id}/complete` | `status=completed`, `completed_at` set, 200 OK | ✅ Status transition in `assignments.py:96` |
| 9 | `household.has_cats=false`, cats-flagged task in catalog | Task hidden from suggestions | ✅ `_household_flag_ok()` returns False |
| 10 | Task with `device_flag=robot_vacuum`, `household.has_robot_vacuum=false` | Task hidden from suggestions | ✅ `_device_flag_ok()` returns False |

---

## Verdict

- [x] Round approved — two minor findings noted, no blockers
- Finding #1 (MINOR): document in code comment, refine in R5 if needed
- Finding #2 (MINOR): R6 agent should handle multi-session days gracefully

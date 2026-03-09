# QA Report — Round 5: History & Feedback Loop

**Date:** 2026-03-08
**Reviewed by:** QA Agent

---

## Summary

Round 5 is approved. All three models are in place, the migration chain is clean (0005→0006),
and the history agent correctly branches on completion vs. skip. Feed entries are generated
only for completed and delegated actions (skips are private). The feedback loop — rejection
tracking, imbalance detection, and time-of-day preference — is fully implemented. Two minor
findings noted, no blockers.

---

## Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| `HistoryEntry` model — all fields | ✅ | `history_entry.py` — id, resident_id, task_template_id, assignment_id, action, timestamp, room_type, points_awarded, was_unpopular, was_forced |
| `ResidentScoringProfile` model — all fields | ✅ | `resident_scoring_profile.py` — rejection_count, last_rejected_at, preferred_time_of_day, imbalance_flag, last_updated; UniqueConstraint on (resident_id, task_template_id) |
| `HouseholdFeedEntry` model — all fields | ✅ | `household_feed_entry.py` — text, action_type, task_name (denormalized), timestamp |
| Alembic migration 0006 (0005→0006) | ✅ | All 3 tables, composite index on history_entries(resident_id, timestamp) |
| `record_completion()` — HistoryEntry + FeedEntry | ✅ | `history_agent.py:54` — both written, feedback loop triggered |
| `record_skip()` — HistoryEntry only (no feed) | ✅ | `history_agent.py:94` — no HouseholdFeedEntry created on skip |
| Rejection tracking: increment on skip | ✅ | `history_agent.py:110` — `profile.rejection_count += 1` |
| Rejection decay: -1 per 14 days | ✅ | `_decay_rejection_count()` — `days // REJECTION_DECAY_DAYS` |
| Rejection prompt at count ≥ 3 | ✅ | `history_agent.py:115` — human-readable prompt returned in `RecordResult` |
| Prompt surfaced in skip API response | ✅ | `assignments.py` skip endpoint — `rejection_prompt=result.rejection_prompt` |
| Imbalance detection: 30-day window, one-sided | ✅ | `_update_imbalance()` — distinct completing residents; sets flag on others |
| Imbalance flag reset when multiple residents contribute | ✅ | `_update_imbalance()` — `len(completing_residents) > 1` clears all flags |
| Time-of-day preference: 3 windows + "none" | ✅ | `TIME_WINDOWS` dict — morning 05-12, afternoon 12-18, evening 18-23 |
| Time preference set after 5+ completions in window | ✅ | `_update_time_preference()` — `window_count >= TIME_PREF_MIN_COMPLETIONS` |
| `GET /feed` — newest first, optional limit | ✅ | `history.py:66` — `order_by(timestamp.desc()).limit(limit)` |
| `GET /history` — filterable by resident, room, date range | ✅ | `history.py:88` — all 4 filters applied |
| `GET /residents/{id}/stats` — all required fields | ✅ | `history.py:121` — all_time, week, month, skipped_week, favorite_room, favorite_category |
| `current_streak` placeholder in stats | ✅ | Returns `0` with comment "computed by Gamification Agent in R6" |
| `GET /household/stats` — breakdown by resident | ✅ | `history.py:184` — per-resident count + percentage |
| `GET /residents/{id}/scoring-profile` | ✅ | `history.py:251` — all profile fields |
| All endpoints require `view` role minimum | ✅ | `require_role("view")` on all 5 endpoints |
| History entries never modified after creation | ✅ | No UPDATE operations in `history_agent.py` — append-only |
| `assignments.py` complete → calls `record_completion()` | ✅ | `assignments.py:130` |
| `assignments.py` skip → calls `record_skip()` | ✅ | `assignments.py:156` |
| history router registered in `main.py` | ✅ | `main.py` — `app.include_router(history.router)` |
| Models registered in `__init__.py` | ✅ | HistoryEntry, ResidentScoringProfile, HouseholdFeedEntry registered |
| NOT: points/streaks (R6) | ✅ | `points_awarded` field exists, `was_unpopular` left False — both for R6 |
| NOT: notifications | ✅ | Prompt is returned in API response only, no push/email |

---

## Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `history_agent.py:130-147` | `_update_time_preference()` queries `HistoryEntry` joined with `TaskTemplate` after a `db.flush()` but before `db.commit()`. The just-inserted HistoryEntry is in the session but not yet committed. SQLAlchemy's flush makes it visible within the same transaction, so this is correct — but worth documenting explicitly to avoid confusion. | Add comment: "flush() above makes the new HistoryEntry visible in this query." Already functionally correct. |
| 2 | MINOR | `history.py:190` | `GET /household/stats` computes `pct` using `completed_this_month` as denominator. If `completed_this_month = 0`, the guard `total = completed_this_month or 1` prevents division by zero — correct. However, individual resident counts are queried separately with `month_start`, so if a resident completes tasks in the month but `completed_this_month` is 0 (shouldn't happen but edge case at month boundary), percentages could exceed 100%. Unlikely but worth noting. | Low-risk edge case at month boundaries. Acceptable for v1.0. |
| 3 | NOTE | `history_agent.py:171` | `_update_imbalance()` fetches household via `db.get(Resident, completing_resident_id).household_id` without loading the household object — this is fine since only `household_id` is used. No issue. | No action needed. |

---

## Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | `POST /assignments/{id}/complete` | Creates HistoryEntry with action="completed" AND HouseholdFeedEntry | ✅ Both written in `record_completion()` |
| 2 | `POST /assignments/{id}/skip` | Creates HistoryEntry with action="skipped", NO feed entry | ✅ `record_skip()` only writes HistoryEntry |
| 3 | Skip same task 3 times | 3rd skip response includes `rejection_prompt` non-null string | ✅ `profile.rejection_count >= REJECTION_PROMPT_THRESHOLD` → prompt set |
| 4 | `GET /feed` | Returns entries newest first, only completed/delegated actions | ✅ `order_by(timestamp.desc())`, only feed entries (skips not written) |
| 5 | Task done only by resident A for 30 days | `imbalance_flag=True` on resident B's scoring profile | ✅ `_update_imbalance()` detects sole_doer, flags others |
| 6 | Resident B also completes same task | Both imbalance flags cleared | ✅ `len(completing_residents) > 1` → all flags reset to False |
| 7 | `GET /residents/1/stats` | Returns correct completion counts for all-time, week, month | ✅ Separate queries with correct time cutoffs |
| 8 | `GET /household/stats?household_id=1` | Resident breakdown sums to ~100% | ✅ `pct = cnt / total * 100` per resident |

---

## Verdict

- [x] Round approved — two minor findings noted, no blockers
- Finding #1: add clarifying comment in `history_agent.py` (5-min fix)

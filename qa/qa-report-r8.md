# QA Report — Round 8: Calendar Integration

## Summary
Round 8 is approved with minor findings. All calendar integration features are implemented:
OAuth2 flow, Google Calendar sync, keyword-based guest detection, alert level assignment,
HouseholdContext storage, scoring boosts in the Suggestion Agent, panic prompt surfacing,
and the daily 07:00 APScheduler job. One minor finding and three notes are recorded.

---

## Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| **Data Models** | | |
| `CalendarEvent` model | ✅ | id, google_event_id, title, start_datetime, end_datetime, guest_probability, alert_level, processed_at |
| `CalendarConfig` model | ✅ | household_id, google_refresh_token (nullable), calendar_ids (JSON), last_synced_at, is_active |
| `HouseholdContext` model | ✅ | household_id (unique), current_alert_level, event_date, event_title, panic_prompt_active, updated_at |
| **OAuth2 Setup** | | |
| `GET /calendar/auth` | ✅ | Redirects to Google consent screen; admin-only; uses GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET from .env |
| `GET /calendar/callback` | ✅ | Exchanges auth code for refresh token; stores in CalendarConfig; never returned in API responses |
| Scope: `calendar.readonly` | ✅ | `CALENDAR_SCOPE` constant; read-only enforced |
| Refresh token stored in DB (not .env) | ✅ | Per-household in `calendar_configs.google_refresh_token` |
| Auto token refresh via Google client library | ✅ | `creds.refresh(Request())` when `not creds.valid` |
| **Calendar Agent** | | |
| HIGH-probability keywords (Besuch, party, birthday, etc.) | ✅ | `GUEST_KEYWORDS_HIGH` constant list |
| MEDIUM-probability keywords (meeting, brunch, etc.) | ✅ | `GUEST_KEYWORDS_MEDIUM` constant list |
| Multiple attendees → medium probability | ✅ | `len(attendees) >= 2` → `GuestProbabilityEnum.medium` |
| LOW probability → ignored | ✅ | `if probability == GuestProbabilityEnum.low: continue` |
| Alert level: ≥7 days → early | ✅ | `ALERT_MEDIUM_MAX_DAYS = 6` → else early |
| Alert level: 3–6 days → medium | ✅ | `days_until <= ALERT_MEDIUM_MAX_DAYS` |
| Alert level: 1–2 days → urgent | ✅ | `days_until <= ALERT_URGENT_MAX_DAYS` (=2) |
| Alert level: same day → panic | ✅ | `days_until <= ALERT_PANIC_MAX_DAYS` (=0) |
| Upsert CalendarEvent on sync | ✅ | Existing records updated, new ones created |
| Clear expired events (past start) | ✅ | `start_datetime < now` → deleted |
| Update HouseholdContext after sync | ✅ | `_upsert_household_context()` always called |
| Lookahead 14 days max | ✅ | `CALENDAR_LOOKAHEAD_DAYS = 14` |
| Keyword list as constant | ✅ | `GUEST_KEYWORDS_HIGH` / `GUEST_KEYWORDS_MEDIUM` |
| **Scoring Context Injection** | | |
| `early` → +5 to shared/visible room tasks | ✅ | `CALENDAR_BOOST_EARLY = 5`; only tier-1 rooms |
| `medium` → +10 to tier-1 rooms | ✅ | `CALENDAR_BOOST_MEDIUM = 10` |
| `urgent` → +20 to tier-1 rooms + force-include | ✅ | `CALENDAR_BOOST_URGENT = 20`; `is_forced = True` for tier-1 |
| `panic` → surface prompt in session response | ✅ | `panic_prompt` field on first `ScoredTask`; propagated to `TaskSuggestionResponse` |
| **API Endpoints** | | |
| `GET /calendar/auth` | ✅ | Admin-only |
| `GET /calendar/callback` | ✅ | No auth required (browser redirect) |
| `GET /calendar/status` | ✅ | Returns is_active, last_synced_at, alert_level, event info |
| `POST /calendar/sync` | ✅ | Manual trigger; any resident; returns SyncResult |
| `GET /calendar/events` | ✅ | Ordered by start_datetime asc; future events only |
| `PUT /calendar/config` | ✅ | Admin-only; updates calendar_ids |
| **Background Job** | | |
| APScheduler job at 07:00 daily | ✅ | `scheduler.add_job(..., hour=7, minute=0, id="daily_calendar_sync")` |
| Registered once at startup via `lifespan` | ✅ | Single scheduler instance; `replace_existing=True` |
| Syncs all households with active CalendarConfig | ✅ | Queries all `is_active=True` configs |
| **Boundaries** | | |
| No event content beyond title/description | ✅ | `description` used for keyword matching, not stored |
| No create/modify/delete of calendar events | ✅ | Read-only API scope |
| No notifications/emails | ✅ | Not implemented |
| No AI — keyword matching only | ✅ | Pure string search |
| Max 14 days lookahead | ✅ | `time_max = now + timedelta(days=14)` |

---

## Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `routers/calendar.py:110` | `GET /calendar/callback` has no authentication guard (intentional — it's a browser redirect from Google). However, the `state` parameter only contains `household_id` with no CSRF token or signature verification. A malicious actor who knows the household_id could attempt to trigger an unauthorized token exchange. | For v1.0 self-hosted LAN deployment this is acceptable. For internet-facing deployment, add a signed state parameter (HMAC). Note for Milestone 3 review. |
| 2 | NOTE | `calendar_agent.py:175` | Event `description` is fetched for keyword matching but NOT stored in the DB (only `title` is stored, for privacy). However, the keyword check runs against `description` at sync time. This means re-syncing an event won't re-detect keywords from the description if only the title is stored in `CalendarEvent`. | Acceptable — description is transient; if keywords appear in description, they likely appear in title too over time. |
| 3 | NOTE | `suggestion_agent.py:218–226` | `urgent` force-include adds **all** tier-1 room tasks to `forced[]`, but the existing logic only picks `forced[0]` (highest-scoring). So in practice only 1 tier-1 task is forced — which is correct. But all other tier-1 tasks lose their `is_forced` status after the first one is picked, even though they have a +20 boost in score. The net effect is correct: 1 forced tier-1 + 2 high-scored tier-1 from regular scored list. | Acceptable. Could be clarified with a comment. |
| 4 | NOTE | `calendar_agent.py` | Google credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) confirmed loaded from `.env` only via `os.getenv()`. `google_refresh_token` is never returned in any API response schema. Both correct per security requirements. | No action needed. |

---

## Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Event with title "Besuch von Familie" starts in 5 days | `alert_level = medium`, `guest_probability = high` | ✅ "besuch" in `GUEST_KEYWORDS_HIGH`; days_until=5 ≤ ALERT_MEDIUM_MAX_DAYS=6 → medium |
| 2 | Event with title "Geburtstag" starts today (same day) | `alert_level = panic`, `panic_prompt_active = True` | ✅ "geburtstag" in HIGH; days_until=0 ≤ 0 → panic |
| 3 | Event with 3 attendees, no keywords, 10 days out | `guest_probability = medium`, `alert_level = early` | ✅ attendees ≥ 2 → medium; days_until=10 > 6 → early |
| 4 | `GET /calendar/status` before any OAuth2 | `is_active=false`, `current_alert_level=null` | ✅ No config → defaults returned |
| 5 | Calendar alert = urgent; session suggestions generated | At least 1 tier-1 room (kitchen/bathroom/hallway/living) task force-included | ✅ `is_forced=True` set for tier-1 tasks when `calendar_alert.value == "urgent"` |
| 6 | Calendar alert = panic; session generated | First suggestion has non-None `panic_prompt` field | ✅ `result[0].panic_prompt = "Guests arriving today..."` |
| 7 | `POST /calendar/sync` when no active config | Returns error string, no crash | ✅ `sync_calendar()` returns `SyncResult(error="No active calendar configuration found...")` |
| 8 | `GET /calendar/auth` with non-admin resident | HTTP 403 | ✅ `require_role("admin")` applied |

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
| R8 | CSRF token missing in OAuth2 state param | open, LAN-only acceptable — Milestone 3 review |

---

## Verdict

- [x] **Round approved — proceed to R9 (Web App UI)**

No blockers. All calendar integration features are implemented correctly and integrated
with the Suggestion Agent (scoring boosts + panic prompt), the APScheduler (07:00 job),
and the existing auth system (admin-only for OAuth2 and config management).
Google credentials are correctly loaded from `.env` and the refresh token is never exposed
in API responses.

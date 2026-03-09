# Review Report — Milestone 3: Full System Review (Pre-Deployment)
## Rounds covered: R7 – R9 (full system: R1–R9)

## Summary
Evenly is a complete, self-hosted household management tool ready for first deployment on GreenNAS. The full stack — FastAPI backend, Vue.js 3 + Vuetify 3 frontend, Docker Compose — is implemented across 9 rounds. The system is architecturally sound and suitable for v1.0 self-hosted use on a LAN. Two minor findings and three notes are raised; no blockers. Milestone 3 is approved with minor findings.

---

## Cross-Round Consistency

| Check | Status | Notes |
|-------|--------|-------|
| All API endpoints used by the frontend are implemented in the backend | ✅ | Verified: sessions, assignments, history, feed, gamification, panic, calendar, residents, rooms, devices, catalog all match |
| Frontend `residentsApi` field names match backend schema | ✅ | Fixed in R9: `color` (not `avatar_color`), `task_category` (not `category`), `setup_complete` added to `ResidentResponse` and `ResidentUpdate` |
| Bootstrap endpoint added for first-resident creation | ✅ | `POST /residents/bootstrap` — unprotected, 409 if residents exist |
| Router registration in `main.py` — all R1–R8 routers present | ✅ | Confirmed: 10 routers registered |
| Alembic migration chain sequential (0001→0009) | ✅ | No gaps; panic migration adds nullable FKs correctly |
| `setup_complete` flows from backend → frontend → router guard | ✅ | Backend responds with `setup_complete`; router redirects to `/first-login` when false |
| Scoring engine reads HouseholdContext for calendar boost | ✅ | `suggestion_agent.py` reads `current_alert_level` from `HouseholdContext` |
| Gamification triggered from assignment completion | ✅ | `assignments.py` calls `gamification_agent.award_points()` on complete |
| History feedback loop influences suggestions | ✅ | `history_agent.py` updates `ResidentScoringProfile`; `suggestion_agent.py` reads rejection_malus and imbalance_bonus |
| APScheduler jobs deduplicated | ✅ | Two jobs registered once in `main.py`: 00:01 (streak+delegation) and 07:00 (calendar sync) |
| No orphaned records (cascade deletes) | ⚠️ | `cascade="all, delete-orphan"` set on Resident→Preferences; not verified for all models (see Architecture Finding #1) |
| No duplicate business logic across agents | ✅ | Each agent owns its domain: suggestion, history, gamification, panic, calendar |
| VITE_API_URL passed as Docker build arg (not runtime env) | ✅ | Fixed in R9: Dockerfile uses `ARG VITE_API_URL`, docker-compose passes via `args:` |

---

## Security Findings

| # | Severity | Location | Finding | Recommendation |
|---|----------|----------|---------|----------------|
| 1 | NOTE | `backend/app/main.py:134` | `allow_origins=["*"]` in CORS config. Acceptable for LAN self-hosted (no internet-facing exposure), but worth documenting explicitly. | Document in README: only deploy on LAN; do not expose port 8000 to the internet without restricting CORS to the NAS IP. |
| 2 | NOTE | `backend/app/routers/residents.py` | `POST /residents/bootstrap` is unprotected but safeguarded by a 409 check (returns error if residents already exist). This is a reasonable bootstrap pattern. | Confirm the 409 guard is tested at deployment. The endpoint should be a dead-letter once the household is set up. |
| 3 | NOTE | `projects/evenly/.env` (excluded from review) | As per R8 QA: `google_refresh_token` stored plain text in SQLite. | Acceptable for LAN-only self-hosted as documented. Not a concern unless the NAS is exposed publicly. |
| 4 | NOTE | Frontend `src/api/client.js:9` | Fallback `|| 'http://localhost:8000'` is fine for local dev but will silently use localhost if `VITE_API_URL` is not set at build time. | Consider failing the build if `VITE_API_URL` is not set (Vite `.env.required` pattern) rather than silently falling back. Low priority for v1.0. |
| 5 | ✅ | All routers | `pin_hash` is never returned in any API response. `ResidentResponse` schema does not include it. | No action needed. |
| 6 | ✅ | All endpoints | No raw SQL queries; SQLAlchemy ORM used throughout. | No SQL injection risk. |

---

## Architecture Findings

| # | Severity | Location | Finding | Recommendation |
|---|----------|----------|---------|----------------|
| 1 | MINOR | `backend/app/models/` | Cascade delete behavior not verified for all foreign-keyed models. Specifically: if a `Household` is deleted, `Room`, `Device`, `DailySession`, `TaskAssignment`, `HistoryEntry`, `ResidentGameProfile`, `PointTransaction`, `Voucher`, `DelegationRecord`, `PanicSession`, `CalendarConfig`, `CalendarEvent`, `HouseholdContext` could become orphaned. For v1.0 single-household deployment this is not a runtime risk, but it is a data integrity concern. | Add `cascade="all, delete-orphan"` to Household relationships in future maintenance. Not urgent for v1.0. |
| 2 | NOTE | `frontend/src/views/PanicView.vue` | Individual task completion in panic mode now calls `assignmentsApi.complete(task.id)` per task, which triggers gamification (points, streaks). This is intentional but means panic tasks do earn points — verify this matches product intent. | Confirm: should panic task completions award points? If yes, current behavior is correct. If no, a `skip_gamification` flag would be needed on the complete endpoint. |
| 3 | ✅ | `backend/app/agents/` | All business logic is in agents; routers contain only HTTP handling and data mapping. Architectural boundary respected. | No action needed. |
| 4 | ✅ | `backend/app/database.py` | DB session managed via `get_db` dependency injection throughout. No ad-hoc session creation. | No action needed. |
| 5 | NOTE | `docker-compose.yml` | No `healthcheck` defined for the backend service. If the backend takes a few seconds to start, the frontend may serve 502 errors briefly. | Add a `healthcheck` using the existing `/health` endpoint: `test: ["CMD", "curl", "-f", "http://localhost:8000/health"]`. Low priority for v1.0. |
| 6 | NOTE | `frontend/src/router/index.js` | The `checkedSetup` flag is module-level and never resets, which means after the first page load it skips all setup/first-login checks. This is intentional (performance) but means a resident switching via the switcher won't be redirected to `/first-login` mid-session. | For v1.0 this is acceptable — the wizard redirect check runs on page reload/fresh navigation. Document as known limitation. |

---

## Open Items from Previous QA Reports

| QA Report | Finding | Status |
|-----------|---------|--------|
| qa-report-r2 | `Room.active == True` SQLAlchemy lint (NOTE) | Still open — accepted, low priority |
| qa-report-r2 | Seed default PINs 1234/5678 (NOTE) | Still open — dev-only, documented |
| qa-report-r4 | `_is_manual_suppressed()` matched by room_type (MINOR) | Still open — documented in code |
| qa-report-r5 | `_update_time_preference()` flush-Sichtbarkeit (MINOR) | Still open — comment added |
| qa-report-r6 | APScheduler in same process as FastAPI (NOTE) | Accepted for v1.0 self-hosted |
| qa-report-r7 | Panic plan ignores `delegation_locked` residents (NOTE) | Accepted, documented |
| qa-report-r8 | `google_refresh_token` plain text in SQLite (NOTE) | Accepted for LAN-only deployment |
| qa-report-r9 | MINOR 1: PanicView individual task API call (fixed in R9) | ✅ Resolved — individual assignments complete endpoint used |
| qa-report-r9 | MINOR 2: Bootstrap resident flow (fixed in R9) | ✅ Resolved — `/residents/bootstrap` endpoint added |

---

## Deployment Checklist (for GreenNAS DXP2800)

Before first `docker compose up` on GreenNAS:

1. **Set `VITE_API_URL`** in `.env` to the NAS LAN IP (e.g. `http://192.168.1.100:8000`)
2. **Run `docker compose build`** (not just `up`) to bake in `VITE_API_URL`
3. **Set `CLAUDE_API_KEY`** in `.env` for catalog generation
4. **Set `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET`** only if calendar integration is needed
5. **Run `docker compose up -d`**
6. **Run alembic migrations** inside the backend container: `docker exec evenly-backend alembic upgrade head`
7. **Open `http://<NAS-IP>:3000`** — Setup Wizard should appear
8. Follow the 8-step wizard to create the household, first admin resident, and generate the task catalog

---

## Verdict

- [x] **Milestone 3 approved with findings** — system is ready for v1.0 self-hosted deployment

**Must fix before going live:**
- None (no blockers)

**Should address before v1.1:**
- Cascade delete behavior for Household relationships (Architecture #1)
- Consider a `healthcheck` in docker-compose (Architecture #5)
- CORS documentation for LAN-only deployment (Security #1)

**Evenly R1–R9 is complete and ready for deployment on GreenNAS.**

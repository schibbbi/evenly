# Architecture Decision Record — Evenly

This document records the key architectural decisions made during the development of Evenly,
including context, rationale, and trade-offs for each choice.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [ADR-001 — SQLite as the Database](#adr-001--sqlite-as-the-database)
3. [ADR-002 — Stateless Header-Based Authentication](#adr-002--stateless-header-based-authentication)
4. [ADR-003 — Deterministic Rule-Based Task Scoring](#adr-003--deterministic-rule-based-task-scoring)
5. [ADR-004 — One-Shot AI for Catalog Generation](#adr-004--one-shot-ai-for-catalog-generation)
6. [ADR-005 — Two-Container Docker Compose Deployment](#adr-005--two-container-docker-compose-deployment)
7. [ADR-006 — Pinia + localStorage for Resident State](#adr-006--pinia--localstorage-for-resident-state)
8. [ADR-007 — In-Process Scheduling with APScheduler](#adr-007--in-process-scheduling-with-apscheduler)
9. [ADR-008 — Vite Build-Time API URL Injection](#adr-008--vite-build-time-api-url-injection)
10. [ADR-009 — Read-Only Google Calendar with Keyword Matching](#adr-009--read-only-google-calendar-with-keyword-matching)

---

## 1. System Overview

Evenly is a self-hosted household management tool designed to run on a NAS or local machine.
It replaces reactive weekend cleaning marathons with small daily tasks, distributed fairly
across all residents.

```mermaid
graph TB
    subgraph Browser["Browser (any LAN device)"]
        FE["Vue.js 3 + Vuetify\nSPA — port 3001"]
    end

    subgraph Container_Frontend["Container: evenly-frontend"]
        NGINX["nginx:alpine\n(static file server + SPA routing)"]
    end

    subgraph Container_Backend["Container: evenly-backend"]
        API["FastAPI\n(uvicorn — port 8000)"]
        SCHED["APScheduler\n(in-process)"]
        AGENTS["Business Logic Agents\n(suggestion, gamification, panic,\nhistory, calendar, catalog)"]
        API --> AGENTS
        SCHED --> AGENTS
    end

    subgraph Volume["Docker Volume: evenly-data"]
        DB[("SQLite\nevenly.db")]
    end

    subgraph External["External Services (optional)"]
        CLAUDE["Claude API\n(catalog generation, setup only)"]
        GCAL["Google Calendar API\n(daily sync)"]
    end

    Browser -->|"HTTP REST\nX-Resident-ID header"| Container_Backend
    Browser -->|"fetch static assets"| Container_Frontend
    Container_Frontend -->|"reverse proxy /\nnginx serves SPA"| Browser
    Container_Backend -->|"SQLAlchemy ORM"| Volume
    Container_Backend -.->|"one-shot at setup"| CLAUDE
    Container_Backend -.->|"OAuth2 read-only"| GCAL
```

---

## ADR-001 — SQLite as the Database

**Status:** Accepted

**Context:**
Evenly targets self-hosted deployment on consumer NAS devices (e.g. UGreen DXP2800) and
MacBooks via Podman Desktop. The expected household size is 1–8 residents. Write concurrency
is minimal — one daily session per resident, no concurrent writes from multiple processes.

**Decision:**
Use SQLite via SQLAlchemy with Alembic for schema migrations. The database file is stored
in a named Docker volume at `/app/data/evenly.db`.

**Rationale:**
- Zero external dependencies — no separate database container to manage
- Single file backup — copy one file to back up all data
- Alembic handles incremental schema evolution across all 12 migration rounds
- SQLAlchemy ORM provides the same API surface as PostgreSQL; migration path exists if needed

**Trade-offs:**
- No concurrent write support (acceptable for household-scale use)
- SQLite does not support `ALTER COLUMN` — table recreation pattern required (see migration `0008`)
- Not suitable for multi-household SaaS without a database swap

```mermaid
erDiagram
    households ||--o{ residents : "has"
    households ||--o{ rooms : "has"
    households ||--o{ task_templates : "has"
    households ||--o| household_game_profiles : "has"
    households ||--o| household_contexts : "has"
    households ||--o{ household_feed_entries : "has"

    residents ||--o{ resident_preferences : "has"
    residents ||--o| resident_game_profiles : "has"
    residents ||--o| resident_scoring_profiles : "has"
    residents ||--o{ daily_sessions : "creates"
    residents ||--o{ task_assignments : "assigned"
    residents ||--o{ point_transactions : "earns"
    residents ||--o{ vouchers : "earns"
    residents ||--o{ delegation_records : "sends/receives"
    residents ||--o{ pin_attempt_logs : "logs"

    rooms ||--o{ devices : "contains"

    daily_sessions ||--o{ task_assignments : "contains"
    panic_sessions ||--o{ task_assignments : "contains"

    task_templates ||--o{ task_assignments : "instantiated as"
    task_assignments ||--o{ history_entries : "generates"

    calendar_configs ||--o{ calendar_events : "syncs"
```

---

## ADR-002 — Stateless Header-Based Authentication

**Status:** Accepted

**Context:**
Evenly runs on a single shared device in the home (a tablet or wall-mounted screen). Multiple
residents use the same browser. Traditional session/JWT authentication assumes one user per
browser — this does not match the usage model.

**Decision:**
Identify the active resident via the `X-Resident-ID` HTTP header. Sensitive actions additionally
require a 4-digit PIN passed in `X-Resident-PIN`. No login sessions, no JWT tokens.

**Rationale:**
- Matches the shared-device model: switching residents is instant (tap avatar → enter PIN)
- Stateless backend — no session store required
- PIN is per-action (admin operations, PIN changes), not per-session — low friction for daily use
- LAN-only deployment removes most remote-attack surface

**Trade-offs:**
- Any browser on the LAN can send arbitrary `X-Resident-ID` headers — not suitable for internet exposure
- PIN brute-force is mitigated via `PINAttemptLog` (3 failures / 10 min → 429 with `Retry-After`)

```mermaid
sequenceDiagram
    actor Resident
    participant FE as Vue Frontend
    participant API as FastAPI Backend
    participant DB as SQLite

    Resident->>FE: Tap avatar
    FE->>FE: Store activeResidentId in localStorage
    FE->>API: GET /residents (X-Resident-ID: 2)
    API->>DB: SELECT * FROM residents WHERE id=2
    DB-->>API: Resident record
    API-->>FE: 200 OK

    Resident->>FE: Tap "Settings" (admin action)
    FE->>FE: Show PIN bottom sheet
    Resident->>FE: Enter PIN
    FE->>API: PUT /households/1 (X-Resident-ID: 2, X-Resident-PIN: 1234)
    API->>DB: Verify PIN (bcrypt)
    alt PIN valid
        API->>DB: UPDATE households
        API-->>FE: 200 OK
    else PIN invalid / throttled
        API-->>FE: 401 / 429
        FE-->>Resident: Show error
    end
```

---

## ADR-003 — Deterministic Rule-Based Task Scoring

**Status:** Accepted

**Context:**
The core value of Evenly is suggesting the *right* 2–3 tasks for each resident every day.
The suggestion algorithm needs to be predictable, tunable, and work fully offline without
any AI dependency at runtime.

**Decision:**
Implement a deterministic scoring engine (`suggestion_agent.py`) that ranks all eligible
tasks for a resident using a weighted formula. No machine learning or AI inference at runtime.

**Scoring formula:**
```
score = overdue_factor        (days since last done × weight, capped at 50)
      + seasonality_factor    (garden tasks in spring/summer; deep cleaning in autumn/winter)
      - rejection_malus       (decays 1 pt/day over 7 days after resident skips)
      + imbalance_bonus       (task done by others but not this resident recently)
      + random_factor         (0–3, for variety across repeated runs)
      + unpopular_bonus       (all residents dislike this category)
      + robot_bonus_or_malus  (energy-aware: robot variants preferred at energy=low)
      + calendar_boost        (+5/+10/+20 for visible-area tasks based on alert level)
```

**Rationale:**
- Fully offline — no API key required for daily operation
- Deterministic behavior is debuggable and explainable to residents
- Scoring weights can be tuned without retraining a model
- Imbalance detection and rejection decay create a natural fairness feedback loop

```mermaid
flowchart TD
    START([Daily Session Created]) --> FILTER

    subgraph FILTER["1 — Visibility Filter"]
        F1{Has children?} -->|No| F2{Has cats/dogs?}
        F2 -->|No| F3{Has garden?}
        F3 -->|No| F4{Has device?}
        F4 --> F5{Energy level OK?}
        F5 --> F6{Est. time ≤ available?}
    end

    FILTER --> SCORE

    subgraph SCORE["2 — Scoring"]
        S1[Overdue factor] --> SUM
        S2[Seasonality] --> SUM
        S3[Rejection malus] --> SUM
        S4[Imbalance bonus] --> SUM
        S5[Random factor] --> SUM
        S6[Unpopular bonus] --> SUM
        S7[Robot bonus/malus] --> SUM
        S8[Calendar boost] --> SUM
        SUM[Final Score]
    end

    SCORE --> FORCE

    subgraph FORCE["3 — Force-Include Rules"]
        FC1{Task 2× overdue\n+ all residents dislike?}
        FC2{Calendar alert = panic\nand no visible-area task?}
    end

    FORCE --> SELECT["4 — Select top N\n(energy=low → 2, else 3)"]
    SELECT --> ROBOT["5 — Robot suppression\n(suppress manual floor task\nif robot variant done <24h ago)"]
    ROBOT --> RESULT([ScoredTask list returned])
```

---

## ADR-004 — One-Shot AI for Catalog Generation

**Status:** Accepted

**Context:**
A task catalog of 100+ household tasks needs to be seeded once at setup. Maintaining a large
hand-curated static catalog is an option, but AI generation produces richer, more
household-specific content (localized names, descriptions, time estimates per room).

**Decision:**
Call the Claude API (`claude-sonnet-4-5`) exactly once during initial setup to generate the
task catalog. If no API key is present, fall back to a bundled static catalog of 136 tasks
defined in `default_catalog.py`. AI is never called again at runtime.

**Rationale:**
- AI is used where it adds value (content generation, natural language task descriptions)
- Zero runtime AI dependency — the app works fully offline after setup
- Static fallback ensures the app is immediately usable without an API key
- One-shot generation is idempotent — re-running does not duplicate tasks

```mermaid
flowchart LR
    SETUP([Setup Wizard\nFinish Step]) --> CHECK{CLAUDE_API_KEY\nset in .env?}

    CHECK -->|Yes| CLAUDE["Call Claude API\nclaude-sonnet-4-5\nGenerate 120+ tasks as JSON"]
    CHECK -->|No| STATIC["Load DEFAULT_TASKS\nfrom default_catalog.py\n(136 tasks, static)"]

    CLAUDE --> PARSE{Valid JSON\nreturned?}
    PARSE -->|Yes| SEED
    PARSE -->|No| STATIC

    STATIC --> SEED["Seed task_templates table\n(idempotent — skip if\nnon-custom tasks exist)"]
    SEED --> DONE([Catalog ready])
```

---

## ADR-005 — Two-Container Docker Compose Deployment

**Status:** Accepted

**Context:**
The target deployment environments are a UGreen NAS DXP2800 running UGOS (Docker-compatible)
and a MacBook running Podman Desktop. The deployment must be simple enough for non-technical
users to operate via a GUI.

**Decision:**
Package Evenly as two containers managed by a single `docker-compose.yml`:
1. `evenly-backend` — Python/FastAPI served by uvicorn on port 8000
2. `evenly-frontend` — Vue.js SPA served by nginx on port 3001

One named Docker volume (`evenly-data`) persists the SQLite database across restarts.

**Rationale:**
- Separation of concerns — frontend and backend can be rebuilt independently
- `docker compose up -d` is the entire deployment command
- Podman Desktop can manage the stack via its Compose extension
- Port 3000 conflicts with other local services (e.g. open-webui) — port 3001 used for frontend

```mermaid
graph LR
    subgraph Host["Host (NAS / MacBook)"]
        P1["Port 3001\n(browser access)"]
        P2["Port 8000\n(API access)"]

        subgraph Compose["docker-compose.yml"]
            subgraph FE_C["evenly-frontend"]
                NGINX2["nginx:alpine"]
            end

            subgraph BE_C["evenly-backend"]
                UVICORN["uvicorn\nFastAPI app"]
                ALEMBIC["alembic upgrade head\n(runs at startup)"]
            end

            VOL[("evenly-data\n/app/data/evenly.db")]
        end

        P1 --> NGINX2
        P2 --> UVICORN
        BE_C --> VOL
    end
```

---

## ADR-006 — Pinia + localStorage for Resident State

**Status:** Accepted

**Context:**
Multiple residents share a single browser on a shared household device (tablet or wall screen).
There is no concept of a "logged in" user — any resident can be the active resident at any time.
The app must survive page reloads without losing track of who is currently active.

**Decision:**
Store the active resident's ID in `localStorage` via a Pinia store (`resident.js`). All API
calls inject `X-Resident-ID` from this store via an Axios request interceptor.

**Rationale:**
- Survives page reloads without requiring a re-login
- Simple to implement without a full auth system
- Consistent with the header-based auth strategy (ADR-002)
- Pinia stores are reactive — any component that reads `activeResidentId` updates automatically

**Trade-offs:**
- If a resident clears `localStorage`, they see the last active resident on next load
- No isolation between browser tabs on the same device (acceptable — shared device model)

```mermaid
stateDiagram-v2
    [*] --> CheckLocalStorage : App loads

    CheckLocalStorage --> ResidentKnown : activeResidentId found
    CheckLocalStorage --> ResidentUnknown : not found

    ResidentUnknown --> CheckHousehold : GET /households
    CheckHousehold --> SetupWizard : no household exists
    CheckHousehold --> ResidentSwitcher : household exists, pick resident

    ResidentSwitcher --> ResidentKnown : resident selected

    ResidentKnown --> CheckSetupComplete : GET /residents/:id
    CheckSetupComplete --> FirstLoginWizard : setup_complete = false
    CheckSetupComplete --> HomeView : setup_complete = true

    HomeView --> SwitchResident : tap avatar → select other resident
    SwitchResident --> ResidentKnown : new activeResidentId stored
```

---

## ADR-007 — In-Process Scheduling with APScheduler

**Status:** Accepted

**Context:**
Two recurring background jobs are required:
- **00:01 daily** — streak check (consume streak-safe or reset streak for missed days) + delegation expiry
- **07:00 daily** — Google Calendar sync

**Decision:**
Run both jobs inside the FastAPI process using APScheduler (`BackgroundScheduler`). The scheduler
starts on app startup via the FastAPI lifespan context manager and stops on shutdown.

**Rationale:**
- No external infrastructure required (no Celery, no Redis, no cron on the host)
- Deployment remains a single `docker compose up -d` with no additional services
- Two low-frequency jobs (daily) do not justify the complexity of a task queue
- APScheduler is in-process — if the container restarts, the scheduler restarts automatically

**Trade-offs:**
- Jobs are lost if the container is down at trigger time (acceptable — missed streak checks
  are tolerated; calendar sync will run the next day or can be triggered manually)
- Not suitable for high-frequency or distributed job execution

```mermaid
sequenceDiagram
    participant Docker
    participant Uvicorn
    participant Lifespan as FastAPI Lifespan
    participant Scheduler as APScheduler
    participant Agents as Business Logic Agents

    Docker->>Uvicorn: Start container
    Uvicorn->>Lifespan: startup
    Lifespan->>Scheduler: scheduler.start()
    Scheduler-->>Lifespan: Running

    Note over Scheduler: Every day at 00:01
    Scheduler->>Agents: run_daily_streak_check()
    Agents->>Agents: Check each resident's last activity
    Agents->>Agents: Consume streak-safe or reset streak

    Scheduler->>Agents: run_delegation_expiry_check()
    Agents->>Agents: Mark expired delegations

    Note over Scheduler: Every day at 07:00
    Scheduler->>Agents: sync_calendar() for all CalendarConfigs
    Agents->>Agents: Fetch Google Calendar events
    Agents->>Agents: Update HouseholdContext alert level

    Docker->>Uvicorn: Stop container
    Uvicorn->>Lifespan: shutdown
    Lifespan->>Scheduler: scheduler.shutdown()
```

---

## ADR-008 — Vite Build-Time API URL Injection

**Status:** Accepted

**Context:**
The frontend needs to know the backend URL at runtime. In a self-hosted LAN deployment, this
URL is the NAS IP address (e.g. `http://192.168.1.100:8000`), which differs per household.
Vite replaces `import.meta.env.VITE_*` variables at compile time — they cannot be changed
at runtime without rebuilding the image.

**Decision:**
Pass `VITE_API_URL` as a Docker build argument (`ARG`). Vite bakes it into the JS bundle
during `npm run build`. The default value is `http://localhost:8000` for local development.

**Rationale:**
- Simple — no runtime config injection mechanism required
- Works with nginx serving pure static files (no server-side rendering)
- Consistent with standard Vite deployment practices

**Trade-offs:**
- Changing the backend URL requires rebuilding the frontend image
- The NAS deployment guide must instruct users to set `VITE_API_URL` before building

```mermaid
flowchart LR
    subgraph Build["Image Build (docker compose build)"]
        ARG["Build ARG:\nVITE_API_URL=http://192.168.1.100:8000"]
        VITE["Vite build\nnpm run build"]
        BUNDLE["JS bundle\n(VITE_API_URL baked in)"]
        ARG --> VITE --> BUNDLE
    end

    subgraph Runtime["Container Runtime"]
        NGINX3["nginx serves\nstatic files"]
        BUNDLE2["JS bundle\n(URL hardcoded)"]
        AXIOS["Axios baseURL\n= http://192.168.1.100:8000"]
        NGINX3 --> BUNDLE2 --> AXIOS
    end

    Build -->|COPY dist| Runtime
```

---

## ADR-009 — Read-Only Google Calendar with Keyword Matching

**Status:** Accepted

**Context:**
Evenly needs to detect upcoming guest visits to trigger Panic Mode suggestions proactively.
The most reliable signal is the household's Google Calendar. Privacy is a concern — residents
may not want calendar content stored or processed in detail.

**Decision:**
Integrate Google Calendar via read-only OAuth2. Store only the event title, start time, and
the computed guest probability. Never store event descriptions, attendee details, or location.
Guest probability is determined by keyword matching on the title (no AI).

**Keyword classification:**
- **High probability:** besuch, visit, birthday, party, geburtstag, hochzeit, wedding, feier, celebration
- **Medium probability:** treffen, meeting, brunch, dinner, lunch, grill, kommen
- **Medium probability upgrade:** ≥2 attendees on a calendar event

**Alert levels by days until event:**
| Days until event | Alert level | Effect on scoring |
|---|---|---|
| 7+ | early | +5 pts to visible-area tasks |
| 3–6 | medium | +10 pts to visible-area tasks |
| 1–2 | urgent | +20 pts to visible-area tasks |
| 0 | panic | Force ≥1 visible-area task; show Panic Mode prompt |

**Rationale:**
- Keyword matching is deterministic, explainable, and privacy-preserving
- No AI inference on calendar content — no data leaves the system during daily operation
- Graceful degradation — if no calendar is configured, scoring runs without calendar boost

```mermaid
flowchart TD
    SYNC([Daily sync at 07:00\nor manual trigger]) --> FETCH["Fetch next 14 days\nfrom Google Calendar API"]
    FETCH --> EVENTS["For each event"]

    EVENTS --> KW{Title contains\nhigh-probability\nkeyword?}
    KW -->|Yes| HIGH["GuestProbability = HIGH"]
    KW -->|No| KW2{Title contains\nmedium-probability\nkeyword?}
    KW2 -->|Yes| MED["GuestProbability = MEDIUM"]
    KW2 -->|No| KW3{≥ 2 attendees?}
    KW3 -->|Yes| MED
    KW3 -->|No| SKIP["Skip event\n(no guest signal)"]

    HIGH --> STORE["Upsert CalendarEvent\n(title + start_datetime +\nguest_probability only)"]
    MED --> STORE

    STORE --> WORST["Compute worst-case\nalert level across all\nupcoming events"]

    WORST --> ALERT{Days\nuntil event}
    ALERT -->|"7+"| EARLY["AlertLevel = EARLY"]
    ALERT -->|"3–6"| MEDIUM["AlertLevel = MEDIUM"]
    ALERT -->|"1–2"| URGENT["AlertLevel = URGENT"]
    ALERT -->|"0"| PANIC["AlertLevel = PANIC"]

    EARLY --> CTX["Upsert HouseholdContext\n(alert_level, event_date)"]
    MEDIUM --> CTX
    URGENT --> CTX
    PANIC --> CTX

    CTX --> SCORE["SuggestionAgent reads\nHouseholdContext on next\ndaily session"]
```

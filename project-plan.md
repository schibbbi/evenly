# Project: Evenly

## Vision
A smart household management tool that replaces reactive, conflict-prone cleaning sessions with short daily routines — personalized per resident, context-aware, and intrinsically motivating.

## Status: Phase 4

---

## Phase 1 — Understanding

### Problem
Household chores in a shared home run unorganized and reactively (only when guests arrive). This creates mental load, conflicts, and the persistent feeling that things are never truly done.

### Target Audience
Multi-person households — primarily two working adults with a toddler and pets. Designed to be configurable and open-source-ready for any household.

### Current State
No system in place. Cleaning happens reactively, coordination is manual, and the imbalance regularly causes conflict.

### Infrastructure
- Home server: GreenNAS DXP2800
- Google Calendar (shared calendars)
- Roborock Saros 10R robot vacuum/mop (manual trigger in v1.0)
- Kärcher WV2 cordless window cleaner
- Standard appliances: washing machine, dryer, dishwasher

---

## Phase 2 — Structure

### Areas
| No | Area | Description | Depends on | Version |
|----|------|-------------|------------|---------|
| A  | Household Configuration | Rooms, residents, devices, garden setup | — | v1.0 |
| B  | Task Catalog | Curated, AI-generated task library per room/category | A | v1.0 |
| C  | Daily Task Engine | Energy/time-based daily task suggestions incl. scoring engine | A, B | v1.0 |
| D  | Panic Mode | Prioritized 2–4h cleaning plan for unexpected guests | A, B | v1.0 |
| E  | History & Transparency | Log of completed/rejected tasks, feedback loop, imbalance tracking | C, D | v1.0 |
| F  | Gamification | Points, team multiplier, streaks, streak-safes, delegation, vouchers | E | v1.0 |
| G  | Calendar Integration | Google Calendar sync for guest detection and early warnings | C, D | v1.0 |
| H  | Device Integration | Roborock API status and last-run awareness | B, C | v2.0 |
| I  | Interface | Web app (home server) + optional WhatsApp bot | C, D, E, F | v1.0 |
| J  | Insight Agent | Monthly AI-powered analysis of usage patterns and recommendations | E | v2.0 |

### Dependencies

```mermaid
graph TD
    A[A: Household Configuration] --> B[B: Task Catalog]
    A --> C[C: Daily Task Engine]
    B --> C
    B --> D[D: Panic Mode]
    A --> D
    C --> E[E: History & Transparency]
    D --> E
    E --> F[F: Gamification]
    C --> G[G: Calendar Integration]
    D --> G
    C --> I[I: Interface]
    D --> I
    E --> I
    F --> I
    B -.->|v2.0| H[H: Device Integration]
    C -.->|v2.0| H
    E -.->|v2.0| J[J: Insight Agent]
```

### Workflows

#### Area A — Household Configuration

```mermaid
flowchart LR
    Start[First Setup] --> Residents[Add Residents & Profiles]
    Residents --> Prefs[Set Preferences per Resident\nlike / dislike / neutral]
    Prefs --> Rooms[Define Rooms]
    Rooms --> Devices[Add Devices]
    Devices --> Garden[Configure Garden]
    Garden --> Done[Household Ready]
```

#### Area B — Task Catalog

```mermaid
flowchart LR
    Catalog[AI-generated Catalog\nclaude-sonnet / claude-opus] --> Browse[Browse by Room & Category]
    Browse --> Toggle[Activate / Deactivate Tasks]
    Toggle --> Edit[Edit Duration, Frequency, Energy Level]
    Edit --> Custom[Add Custom Tasks]
    Custom --> Ready[Catalog Configured]
```

#### Area C — Daily Task Engine + Scoring

```mermaid
flowchart LR
    Trigger[Resident opens app\nor bot prompts] --> Energy[Enter Energy Level]
    Energy --> Time[Enter Available Time]
    Time --> Score[Calculate Priority Score per Task]
    Score --> Filter[Filter by energy + time]
    Filter --> Suggest[Show 2–3 task suggestions]
    Suggest --> Reroll{Not happy\nwith suggestions?}
    Reroll -->|Once free| NewSuggest[Reroll suggestions]
    Reroll -->|2nd+ time| MalusReroll[Reroll with point malus]
    NewSuggest --> Accept
    MalusReroll --> Accept
    Suggest --> Accept[Resident accepts task]
    Accept --> Log[Task logged as in progress]
    Log --> Done[Mark as done → History updated]
```

**Priority Score Formula:**
```
Score = Overdue Factor
      + Seasonality Factor
      + Imbalance Bonus
      - Rejection Malus (recovers over days)
      + Random Factor (wildcard)
      + Unpopular Task Bonus (if disliked by all residents)
```

**Unpopular Task Rules:**
- Score rises regardless of preference
- Rotation between residents — no one is permanently assigned
- No escape via reroll or delegation when overdue threshold is exceeded
- Bonus point modifier applied when completed voluntarily

#### Area D — Panic Mode

```mermaid
flowchart LR
    Trigger[Resident activates Panic Mode] --> Duration[Select available time: 2h / 3h / 4h]
    Duration --> Priority[Prioritize visible & shared areas first]
    Priority --> Plan[Generate step-by-step plan]
    Plan --> Assign[Assign tasks across available residents]
    Assign --> Execute[Residents execute plan]
    Execute --> Log[All tasks logged to History]
```

#### Area E — History, Transparency & Feedback Loop

```mermaid
flowchart LR
    Action[Task completed / rejected / delegated] --> Entry[Create history entry:\nwho, what, when, room, outcome]
    Entry --> Feed[Update shared activity feed]
    Feed --> Stats[Update personal & household stats]
    Stats --> Feedback[Feedback loop analysis]
    Feedback --> Imbalance{Imbalance\ndetected?}
    Imbalance -->|Yes| Adjust[Adjust scoring for affected resident]
    Feedback --> Rejection{Repeated\nrejections?}
    Rejection -->|2-3x same task| Prompt[Ask: pause task or reduce frequency?]
    Feedback --> TimePref[Detect time-of-day preferences]
    TimePref --> ScoreUpdate[Update scoring engine]
```

#### Area F — Gamification

```mermaid
flowchart LR
    Done[Task marked done] --> Personal[Add personal points]
    Personal --> Unpopular{Unpopular\ntask?}
    Unpopular -->|Yes| Modifier[Apply bonus point modifier]
    Unpopular -->|No| Team
    Modifier --> Team{Both residents\ncompleted tasks today?}
    Team -->|Yes| Multiplier[Apply team multiplier to both]
    Team -->|No| Streak[Update personal streak]
    Multiplier --> Streak
    Streak --> Safes{More than\n1 task today?}
    Safes -->|2 tasks| S1[Earn 1 Streak-Safe]
    Safes -->|3 tasks| S2[Earn 2 Streak-Safes]
    Safes -->|4+ tasks| S3[Earn 3 Streak-Safes max]
    S1 --> Voucher[Check voucher / reward thresholds]
    S2 --> Voucher
    S3 --> Voucher
    Streak --> Voucher
```

**Delegation Rules:**
- Delegating costs the sender points
- Receiver earns normal points on completion
- Only allowed if task is NOT in receiver's "dislike" category
- Receiver cannot decline
- Task is not re-rollable for receiver
- 3-day deadline for receiver
- After 3 days: only delegated task visible, no points awarded until completed

**Streak-Safe Rules:**
- 1 task/day → streak counted, no safe earned
- 2 tasks → streak + 1 streak-safe
- 3 tasks → streak + 2 streak-safes
- 4+ tasks → streak + 3 streak-safes (maximum per day)
- Streak-safes auto-apply on missed days
- No cap on streak length

#### Area G — Calendar Integration

```mermaid
flowchart LR
    Sync[Sync Google Calendar] --> Scan[Scan for upcoming events / guests]
    Scan --> Detect{Guest event\ndetected?}
    Detect -->|7+ days out| EarlyWarn[Early warning:\nfocus shared areas in daily suggestions]
    Detect -->|1-2 days out| UrgentWarn[Urgent mode:\nsuggest targeted visible-area tasks]
    Detect -->|Same day| Panic[Suggest activating Panic Mode]
    EarlyWarn --> Adjust[Adjust daily scoring weights]
    UrgentWarn --> Adjust
```

#### Area I — Interface

```mermaid
flowchart LR
    User[Resident] --> Choice{Interface}
    Choice -->|Web App| WebApp[Dashboard:\ntasks, history, stats, config, gamification]
    Choice -->|WhatsApp Bot| Bot[Daily prompt:\nenergy + time → task suggestions]
    WebApp --> Action[Accept / complete / skip / delegate / reroll]
    Bot --> Action
    Action --> Backend[Backend processes + updates state]
```

### Order
1. Round 1: Area A — Household Configuration
2. Round 2: Area B — Task Catalog (AI-generated via Claude)
3. Round 3: Area C — Daily Task Engine + Scoring Engine
4. Round 4: Area E — History, Transparency & Feedback Loop
5. Round 5: Area F — Gamification
6. Round 6: Area D — Panic Mode
7. Round 7: Area G — Calendar Integration
8. Round 8: Area I — Interface (Web App)
9. Round 9: Area I — Interface (WhatsApp Bot, optional)
10. Round 10: Area H — Device Integration (v2.0)
11. Round 11: Area J — Insight Agent (v2.0)

---

## Phase 3 — Technology

### Already in Use
- GreenNAS DXP2800 (home server, Docker-capable, 8GB DDR5 RAM)
- Google Calendar (shared calendars)
- Roborock Saros 10R (manual trigger in v1.0)
- Kärcher WV2

### Technology Decisions

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend / API | Python + FastAPI | Simple, well-documented, excellent for rule-based logic, highly AI-generatable |
| Database | SQLite (v1.0) | Zero-config, single file, no extra service, sufficient for household scale |
| Frontend | Vue.js + Vuetify | Gentle learning curve, beautiful UI components out of the box, AI-generatable |
| Deployment | Docker Compose | Single config file, easy to manage on GreenNAS, all services in one place |
| AI / Catalog Generation | Claude API (claude-sonnet) | One-time call at setup, cost-efficient, no local model needed |
| Calendar | Google Calendar API + OAuth2 | Direct integration, free, official |
| Bot Interface | WhatsApp Business API (v1.5) | Free up to 1,000 conversations/month, used daily by residents |
| Bot Interface alt. | Signal Bot (v2.0+) | Only when Signal API matures sufficiently |

### Design Principles
- **No AI at runtime** — all daily logic is rule-based (scoring engine, suggestions, gamification)
- **AI used once** — Claude API called once at setup to generate the task catalog, result stored in DB
- **Minimal services** — SQLite avoids a separate DB container; Docker Compose keeps everything manageable
- **Mobile-first web UI** — residents interact primarily on phone via browser, UX focus on speed and clarity
- **Offline-capable core** — task suggestions and history work without internet; only Calendar sync and Claude API require connectivity

### Agents Overview

| Agent | Area | Trigger | Technology |
|-------|------|---------|-----------|
| Catalog Agent | B | One-time at setup | Python + Claude API |
| Suggestion Agent | C | Daily per resident / on demand | Python, rule-based scoring |
| Panic Agent | D | Manual activation | Python, rule-based prioritization |
| Gamification Agent | F | Event-driven (task completed) | Python, rule-based |
| Calendar Agent | G | Scheduled background job (daily) | Python + Google Calendar API |
| Orchestrator | — | Routes all requests | FastAPI router layer |

### System Architecture

```mermaid
graph TD
    User[Resident: Browser on Phone/Desktop] --> WebApp[Vue.js Frontend]
    User2[Resident: WhatsApp - v1.5] --> WABot[WhatsApp Business API]
    WABot --> API

    WebApp --> API[FastAPI Backend / Orchestrator]

    API --> SuggestionAgent[Suggestion Agent\nrule-based scoring]
    API --> PanicAgent[Panic Agent\nprioritized plan]
    API --> GamificationAgent[Gamification Agent\npoints, streaks, safes]
    API --> CalendarAgent[Calendar Agent\nbackground job]
    API --> CatalogAgent[Catalog Agent\none-time setup]

    CatalogAgent --> ClaudeAPI[Claude API\nclaude-sonnet]
    CalendarAgent --> GoogleCal[Google Calendar API]

    SuggestionAgent --> DB[(SQLite Database)]
    PanicAgent --> DB
    GamificationAgent --> DB
    CalendarAgent --> DB
    CatalogAgent --> DB
    API --> DB

    DB --> History[History & Feedback Loop]
    History --> SuggestionAgent
```

---

## Phase 4 — Implementation

### Rounds

| Round | Scope | Area | Agent Briefing | Status |
|-------|-------|------|---------------|--------|
| 1 | Project scaffolding: Docker Compose, FastAPI skeleton, SQLite setup, folder structure | Infrastructure | briefing-r1-scaffolding.md | ⬜ |
| 2 | Household Configuration: residents, rooms, devices, preferences, role + PIN fields | A | briefing-r2-configuration.md | ⬜ |
| 2b | Roles & Access Control: PIN verification, role guards on all endpoints, attempt throttling | A (ext.) | briefing-r2b-access-control.md | ⬜ |
| 3 | Task Catalog: Claude API integration, catalog generation, activate/deactivate | B | briefing-r3-catalog.md | ⬜ |
| 4 | Daily Task Engine: scoring engine, energy/time input, suggestion logic, reroll | C | briefing-r4-engine.md | ⬜ |
| 5 | History & Feedback Loop: task logging, activity feed, rejection tracking, imbalance detection | E | briefing-r5-history.md | ⬜ |
| 6 | Gamification: points, team multiplier, streaks, streak-safes, delegation, vouchers | F | briefing-r6-gamification.md | ⬜ |
| 7 | Panic Mode: activation flow, prioritized plan generation, multi-resident assignment | D | briefing-r7-panic.md | ⬜ |
| 8 | Calendar Integration: Google Calendar API, OAuth2, guest detection, scoring adjustments | G | briefing-r8-calendar.md | ⬜ |
| 9 | Web App UI: Vue.js + Vuetify frontend, all screens, mobile-first, PIN UI, role guards | I | briefing-r9-webapp.md | ⬜ |

### Timeline

```mermaid
gantt
    title Evenly — Implementation Plan v1.0
    dateFormat  YYYY-MM-DD
    section Foundation
    R1 Scaffolding              :r1, 2026-03-09, 5d
    section Core Data
    R2 Household Configuration  :r2, after r1, 7d
    R2b Roles & Access Control  :r2b, after r2, 5d
    R3 Task Catalog             :r3, after r2b, 7d
    section Core Logic
    R4 Daily Task Engine        :r4, after r3, 10d
    R5 History & Feedback Loop  :r5, after r4, 7d
    section Engagement
    R6 Gamification             :r6, after r5, 10d
    section Extended Features
    R7 Panic Mode               :r7, after r6, 5d
    R8 Calendar Integration     :r8, after r7, 7d
    section Interface
    R9 Web App UI               :r9, after r8, 14d
```

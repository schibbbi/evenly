# Evenly — Session Context (für neuen Chat)

## Ziel

Selbst-gehostetes Haushaltsmanagement-Tool **Evenly** — Web-App die Haushaltsmitglieder täglich mit personalisierten Reinigungsaufgaben (15–30 Min.) unterstützt, statt reaktiver Großputzaktionen. Geplant und umgesetzt durch Meta-Agent + spezialisierte Agenten.

---

## Instructions

- **Kommunikation:** Deutsch mit dem Nutzer, alle Dateien/Code/Dokumentation auf Englisch
- **Regelwerk:** `agents/meta-planner.md` — Phasen nicht überspringen, Ergebnisse immer in Dateien schreiben
- **QA-Pflicht:** Nach jeder abgeschlossenen Runde automatisch den QA Agent (`agents/qa-agent.md`) ausführen und Report nach `projects/evenly/qa/qa-report-r[X].md` schreiben — ohne dass der Nutzer explizit darum bitten muss
- **Milestone-Reviews:** Nach R9 → Milestone 3 Review Agent (`agents/review-agent.md`) ausführen, Report nach `qa/review-report-milestone-3.md`
- **LSP-Fehler** (SQLAlchemy/FastAPI/bcrypt not resolved) sind erwartet und können ignoriert werden — Packages laufen nur im Docker-Container, kein lokales Python-Env vorhanden
- **Stack:** Python 3.11 + FastAPI, SQLite + SQLAlchemy + Alembic, Vue.js 3 + Vuetify 3 (Material Design 3), Docker Compose auf GreenNAS DXP2800
- **Alle Briefings** liegen unter `projects/evenly/briefing-r*.md` — immer vor Beginn einer Runde lesen
- **Kein Docker lokal** — Stack läuft auf GreenNAS, Code wird geschrieben aber nicht lokal ausgeführt

---

## Discoveries

- **Nutzer:** UX Designer, kaum Programmiererfahrung (HTML/CSS) — Code muss KI-generierbar und wartbar sein
- **Roboter-Logik:** Bei `energy=low` + Roboter vorhanden → `ROBOT_LOW_ENERGY_BONUS = 20` auf Roboter-Variante, `ROBOT_MANUAL_LOW_ENERGY_MALUS = 10` auf manuelle Variante. Nach Roboter-Lauf innerhalb 24h: manuelle Variante komplett unterdrückt. `robot_frequency_multiplier` reduziert Basis-Frequenz manueller Tasks.
- **Household-Flags:** 4 Composition-Flags (`has_children`, `has_cats`, `has_dogs`, `has_garden`) + 9 Device-Flags steuern Katalog-Sichtbarkeit und Scoring
- **setup_complete** Flag auf `Resident` steuert ob First-Login-Wizard gezeigt wird
- **Wizard-Flow:** 8-Schritte-Admin-Setup-Wizard + 4-Schritte-Co-Resident-Wizard — in `briefing-r9-webapp.md` vollständig dokumentiert
- **Gamification (White-Hat):** Streaks ohne Cap, Streak-Safes (max 3/Tag verdienbar, kein Cap auf Vorrat), Delegation kostet Punkte beim Sender, Unpopular-Task-Bonus-Multiplier
- **Delegation-Logik:** 3-Tage-Deadline; bei Ablauf → `delegation_locked=True` auf Receiver, nur noch delegierter Task sichtbar, kein Punkte-Award
- **Calendar-Alerts:** 3 Stufen (low/medium/high); Scoring-Boost für Tier-1-Räume bei aktivem Alert; `panic_prompt_active` auf `HouseholdContext` bei high-Alert
- **Alembic-Migrationskette:** 0001 → 0002 → 0002b → 0002c → 0002d → 0003 → 0004 → 0005 → 0006 → 0007 → 0008 → 0009 (alle existieren)
- **R4 QA Finding:** Mehrere Sessions pro Tag erlaubt — Streak-Logik verwendet erste Session pro Tag (`GROUP BY date`)
- **R7:** `task_assignments.session_id` ist nullable (Panic-Assignments haben keine Daily Session); `task_assignments.panic_session_id` ist neue nullable FK-Spalte

---

## Accomplished

### ✅ Vollständig abgeschlossen (R1–R8):

- **R1 — Scaffolding:** Docker Compose, FastAPI skeleton, SQLite, Alembic (0001), `/health`
- **R2 — Household Configuration:** 5 Models, 11 Endpoints, Seed Script, Migration 0002; QA approved
- **Post-R2:** Composition + Device Flags, `setup_complete`, Migrations 0002b/c/d
- **R2b — Roles & Access Control:** `PINAttemptLog`, `app/auth.py` (verify_pin, hash_pin, throttle, require_role), `routers/auth.py`, Role Guards auf allen Write-Endpoints, Migration 0003; QA + Milestone 1 approved
- **R3 — Task Catalog:** `TaskTemplate`, 4 Enums, `catalog_agent.py` (Claude API, idempotent, 120+ Tasks), `routers/catalog.py` (6 Endpoints), Migration 0004; QA approved
- **R4 — Daily Task Engine:** `DailySession` + `TaskAssignment`, `suggestion_agent.py` (8 Scoring-Komponenten, vollständige Roboter-Logik, Unpopular-Escalation), `routers/sessions.py` + `routers/assignments.py`, Migration 0005; QA approved
- **R5 — History & Feedback Loop:** `HistoryEntry` + `ResidentScoringProfile` + `HouseholdFeedEntry`, `history_agent.py` (record_completion/skip, rejection tracking/decay, imbalance detection, time-of-day preference), `routers/history.py` (5 Endpoints), Migration 0006; QA approved
- **R6 — Gamification:** `ResidentGameProfile` + `HouseholdGameProfile` + `PointTransaction` + `Voucher` + `DelegationRecord`, `gamification_agent.py` (award_points, process_streak, earn_voucher, delegation, run_daily_streak_check, run_delegation_expiry_check), `routers/gamification.py`, APScheduler in `main.py` (00:01 täglich), Migration 0007; QA + Milestone 2 approved
- **R7 — Panic Mode:** `PanicSession`, `task_assignments.panic_session_id` (nullable FK), `task_assignments.session_id` nullable, `panic_agent.py` (Tier-1/2/3 Priorisierung, Round-Robin-Verteilung, Time-Box), `routers/panic.py` (3 Endpoints), Migration 0008; QA approved
- **R8 — Calendar Integration:** `CalendarConfig` + `CalendarEvent` + `HouseholdContext` + `AlertLevelEnum`, `calendar_agent.py` (OAuth2 flow, Google Calendar sync, keyword-based guest detection, alert assignment, scoring boost injection), `routers/calendar.py` (OAuth2 + CRUD + context), APScheduler-Job (07:00 täglich), Migration 0009; QA approved

- **R9 — Web App UI:** Vue.js 3 + Vuetify 3, alle 9 Screens, Setup-Wizard (8 Schritte), Co-Resident-Wizard (4 Schritte), PIN-System, Light/Dark Mode; QA + Milestone 3 Review approved

---

## Pending QA Findings (offen, kein Blocker)

| Runde | Finding | Status |
|-------|---------|--------|
| R2 | `Room.active == True` SQLAlchemy lint (NOTE) | akzeptiert |
| R2 | Seed default PINs 1234/5678 (NOTE) | Dev-only |
| R4 | `_is_manual_suppressed()` matched by room_type (MINOR) | dokumentiert im Code |
| R5 | `_update_time_preference()` flush-Sichtbarkeit (MINOR) | Kommentar ergänzt |
| R6 | APScheduler läuft im selben Prozess wie FastAPI (NOTE) | akzeptiert für v1.0 self-hosted |
| R7 | Panic-Plan ignoriert aktive `delegation_locked` Residents (NOTE) | akzeptiert, dokumentiert |
| R8 | `google_refresh_token` plain text in SQLite (NOTE) | akzeptiert für LAN-only self-hosted |

---

## Vollständige Dateistruktur

```
agenticWorkbench/
├── agents/
│   ├── meta-planner.md
│   ├── qa-agent.md
│   └── review-agent.md
└── projects/evenly/
    ├── SESSION-CONTEXT.md          ← diese Datei
    ├── project-plan.md
    ├── README.md
    ├── docker-compose.yml
    ├── .env.example
    ├── briefing-r1-scaffolding.md
    ├── briefing-r2-configuration.md
    ├── briefing-r2b-access-control.md
    ├── briefing-r3-catalog.md
    ├── briefing-r4-engine.md
    ├── briefing-r5-history.md
    ├── briefing-r6-gamification.md
    ├── briefing-r7-panic.md
    ├── briefing-r8-calendar.md
    ├── briefing-r9-webapp.md       ← nächstes Briefing lesen!
    ├── qa/
    │   ├── qa-report-r2.md         — approved
    │   ├── qa-report-r2b.md        — approved
    │   ├── qa-report-r3.md         — approved
    │   ├── qa-report-r4.md         — approved (2 minor)
    │   ├── qa-report-r5.md         — approved (2 minor)
    │   ├── qa-report-r6.md         — approved (3 minor)
    │   ├── qa-report-r7.md         — approved (1 minor, 2 notes)
    │   ├── qa-report-r8.md         — approved (1 minor, 3 notes)
    │   ├── review-report-milestone-1.md  — approved (R1–R2b)
    │   └── review-report-milestone-2.md  — approved (R1–R6)
    └── backend/
        ├── Dockerfile
        ├── requirements.txt         — fastapi, uvicorn, sqlalchemy, alembic, python-dotenv,
        │                              anthropic==0.26.0, httpx, bcrypt, google-api-python-client,
        │                              google-auth-oauthlib, apscheduler
        ├── alembic.ini
        ├── seed.py
        ├── alembic/versions/
        │   ├── 0001_initial.py
        │   ├── 0002_household_configuration.py
        │   ├── 0002b_household_flags.py
        │   ├── 0002c_household_device_flags.py
        │   ├── 0002d_resident_setup_complete.py
        │   ├── 0003_pin_attempt_log.py
        │   ├── 0004_task_template.py
        │   ├── 0005_sessions_assignments.py
        │   ├── 0006_history.py
        │   ├── 0007_gamification.py
        │   ├── 0008_panic.py          — session_id nullable, panic_session_id hinzugefügt
        │   └── 0009_calendar.py
        └── app/
            ├── main.py               — alle Router R1–R8 registriert; APScheduler (00:01 + 07:00)
            ├── database.py
            ├── auth.py               — get_active_resident, require_role, verify_pin, hash_pin
            ├── models/
            │   ├── __init__.py       — alle 18 Models registriert
            │   ├── enums.py          — RoleEnum, RoomTypeEnum, DeviceTypeEnum, PreferenceEnum,
            │   │                       EnergyLevelEnum, AssignmentStatusEnum, CategoryEnum,
            │   │                       HouseholdFlagEnum, DeviceFlagEnum,
            │   │                       PointReasonEnum, VoucherTypeEnum, AlertLevelEnum
            │   ├── household.py      — 13 Boolean-Flags (4 composition + 9 device)
            │   ├── resident.py       — role, pin_hash, setup_complete
            │   ├── room.py
            │   ├── device.py
            │   ├── resident_preference.py
            │   ├── pin_attempt_log.py
            │   ├── task_template.py  — is_robot_variant, robot_frequency_multiplier,
            │   │                       household_flag, device_flag, is_active, is_custom
            │   ├── daily_session.py  — energy_level, available_minutes, reroll_count, reroll_malus
            │   ├── task_assignment.py — status, score, is_forced, points_awarded,
            │   │                        session_id (nullable!), panic_session_id (nullable)
            │   ├── history_entry.py  — action, was_unpopular, was_forced
            │   ├── resident_scoring_profile.py — rejection_count, imbalance_flag, preferred_time_of_day
            │   ├── household_feed_entry.py — text, action_type, task_name (denorm.)
            │   ├── resident_game_profile.py — total_points, current_streak, longest_streak,
            │   │                               streak_safes_available/used, last_activity_date,
            │   │                               voucher_threshold_watermark, delegation_locked
            │   ├── household_game_profile.py — team_points, team_streak, last_team_activity_date
            │   ├── point_transaction.py — amount, reason (PointReasonEnum), reference_id
            │   ├── voucher.py        — type (VoucherTypeEnum), label, earned_at, is_redeemed
            │   ├── delegation_record.py — from/to resident_id, deadline_at, no_points_on_completion
            │   ├── panic_session.py  — available_minutes, available_resident_ids (JSON), status
            │   ├── calendar_config.py — google_refresh_token, calendar_ids (JSON), is_active
            │   ├── calendar_event.py  — google_event_id, start/end_datetime, guest_probability, alert_level
            │   └── household_context.py — current_alert_level (AlertLevelEnum), event_date,
            │                              panic_prompt_active
            ├── agents/
            │   ├── catalog_agent.py   — generate_catalog() → Claude API, idempotent
            │   ├── suggestion_agent.py — get_suggestions() → 8-Komponenten Scoring + Calendar-Boost
            │   ├── history_agent.py   — record_completion(), record_skip(), feedback loop
            │   ├── gamification_agent.py — award_points(), process_streak(), earn_voucher(),
            │   │                           delegate_task(), run_daily_streak_check(),
            │   │                           run_delegation_expiry_check()
            │   ├── panic_agent.py     — generate_panic_plan() → Tier-Priorisierung, Round-Robin
            │   └── calendar_agent.py  — oauth2_flow(), sync_calendar(), keyword detection,
            │                            alert assignment, HouseholdContext upsert
            └── routers/
                ├── households.py     — CRUD + alle flags; POST ungeschützt (bootstrap)
                ├── residents.py      — CRUD + preferences
                ├── rooms.py
                ├── devices.py
                ├── auth.py           — verify-pin, change-pin, reset-pin
                ├── catalog.py        — generate, list (flag-filtered), export, CRUD
                ├── sessions.py       — POST /sessions, GET suggestions, POST reroll
                ├── assignments.py    — accept, complete (→ history + gamification), skip (→ history + prompt)
                ├── history.py        — feed, history, resident stats, household stats, scoring-profile
                ├── gamification.py   — profile, transactions, vouchers, delegate, leaderboard
                ├── panic.py          — POST /panic, GET /panic/{id}, POST /panic/{id}/complete
                └── calendar.py       — OAuth2 endpoints, config CRUD, context, manual sync trigger
```

---

## Scoring Engine (suggestion_agent.py) — aktueller Stand

```
score = overdue_factor          (days_since/effective_freq * 10, cap 50)
      + seasonality_factor      (+5 garden spring/summer; +5 cleaning autumn/winter)
      - rejection_malus         (-3/rejection letzte 7T, +1/Tag Recovery)
      + imbalance_bonus         (+8 wenn Task bisher nur von anderen erledigt)
      + random_factor           (uniform 0.0–3.0)
      + unpopular_bonus         (+5 wenn alle dislike)
      + robot_preference_bonus  (+20 robot variant bei energy=low)
      - robot_manual_malus      (-10 manuelle Variante bei energy=low + Roboter vorhanden)
      + calendar_alert_boost    (+15 Tier-1-Räume bei medium Alert; +30 bei high Alert)  ← R8
```

Konstanten in `suggestion_agent.py`. Effektive Frequenz: `freq / robot_frequency_multiplier` wenn Gerät vorhanden. Calendar-Boost liest `HouseholdContext.current_alert_level`.

---

## Gamification-Logik (gamification_agent.py)

- **Punkte:** Basis 10 Pkt/Task; +5 Unpopular-Bonus; +3 Streak-Bonus (ab Tag 7); Reroll-Malus -2; Delegation-Kosten -5 für Sender
- **Streak:** +1 pro Tag mit ≥1 Abschluss; Streak-Safe verbraucht bei Lücke; kein Cap
- **Streak-Safes:** Verdient beim ersten Abschluss des Tages; max 3/Tag verdienbar; kein Cap auf Vorrat
- **Vouchers:** Pro 100 Punkte ein Voucher; Watermark verhindert Doppelvergabe
- **Delegation:** 3-Tage-Deadline; Ablauf → `delegation_locked=True`; kein Punkte-Award bei Ablauf
- **Daily Jobs (APScheduler 00:01):** `run_daily_streak_check()` + `run_delegation_expiry_check()`

---

## Status: Deployment-ready (v1.0)

**R1–R9 vollständig. Milestone 3 approved.**

Nächste mögliche Schritte:
- Deployment auf GreenNAS (Checklist in `qa/review-report-milestone-3.md`)
- v1.1: Offene MINORs beheben (Cascade-Delete, _is_manual_suppressed, flush)
- v1.5: WhatsApp-Bot (separates Briefing ausstehend)

**Letzte Änderung:** Projekt von `HomeKeep` auf `Evenly` umbenannt.

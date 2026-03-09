# Evenly

> **Evenly – Home. A little every day.**

A clean home doesn't come from big cleaning sessions on the weekend—it comes from small tasks at the right moment.
Evenly helps everyone in the household keep things running smoothly, without stress or endless to-do lists.

Every day, Evenly suggests 2–3 small tasks for each resident, tailored to their available time and energy. Maybe it's just starting the robot vacuum. Maybe it's cleaning the oven. The goal is simple: 15–30 minutes a day instead of four hours on the weekend.

Evenly also makes sure tasks are shared fairly. If the same person keeps doing the same chores, the system balances things automatically. The household stays in sync—without arguments or rigid cleaning schedules.

And when guests are on the way?
Panic Mode instantly creates a realistic plan and distributes tasks among everyone who's available.

Evenly keeps your home organized, fair, and manageable.
Just a little every day.

## Quick Start

```bash
# 1. Copy and fill environment variables
cp .env.example .env

# 2. Start the stack
docker compose up -d

# 3. Verify
curl http://localhost:8000/health
# → { "status": "ok", "version": "0.1.0" }
```

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Database | SQLite (via SQLAlchemy + Alembic) |
| Frontend | Vue.js 3 + Vuetify 3 (added in R9) |
| Deployment | Docker Compose |

## Project Structure

```
evenly/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app entry point
│   │   ├── database.py      # SQLite connection + session
│   │   ├── models/          # SQLAlchemy models (added per round)
│   │   ├── routers/         # API route handlers (added per round)
│   │   └── agents/          # Business logic agents (added per round)
│   ├── alembic/             # Database migrations
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Vue.js app (added in R9)
├── docker-compose.yml
├── .env.example
└── README.md
```

## Implementation Rounds

| Round | Scope | Status |
|-------|-------|--------|
| R1 | Scaffolding | ✅ |
| R2 | Household Configuration | ✅ |
| R2b | Roles & Access Control | ✅ |
| R3 | Task Catalog | ✅ |
| R4 | Daily Task Engine | ✅ |
| R5 | History & Feedback Loop | ✅ |
| R6 | Gamification | ✅ |
| R7 | Panic Mode | ✅ |
| R8 | Calendar Integration | ✅ |
| R9 | Web App UI | ✅ |
| R10 | i18n (de-DE + en-US) | ✅ |

## Installation

| Guide | Description |
|-------|-------------|
| [Podman Desktop — GUI (macOS)](docs/install-podman-desktop.md) | Recommended for local use on a MacBook, GUI-first |
| [Podman Desktop — CLI (macOS)](docs/install-podman.md) | Podman via terminal on macOS |
| [CLI — Docker / Podman / Native](docs/install-cli.md) | Terminal-based install for macOS and Linux |
| [UGreen NAS DXP2800](docs/install-ugreennas.md) | Self-hosted on UGreen NAS via UGOS |
| [Architecture Decision Record](docs/architecture-decision-record.md) | Key technical decisions with diagrams |

## Deployment Notes

### First deployment on GreenNAS (or any fresh host)

After cloning and before starting the stack, the frontend dependencies must be
installed inside the container. `vue-i18n` was added to `package.json` and
requires an explicit install step if `node_modules` is not committed (which it
isn't, by design).

```bash
# 1. Copy environment file
cp .env.example .env
# Edit .env — set VITE_API_URL, CLAUDE_API_KEY (optional), etc.

# 2. Install frontend dependencies (only needed on first deploy or after package.json changes)
docker compose run --rm frontend npm install

# 3. Start the full stack
docker compose up -d

# 4. Verify backend
curl http://localhost:8000/health
# → { "status": "ok", "version": "0.1.0" }
```

> **Why is `npm install` needed?** The Dockerfile builds the frontend at image
> build time via `npm run build`. If the image is rebuilt (`docker compose build`
> or `--build` flag), npm install runs automatically inside the build. The manual
> step above is only required when running the container directly without
> rebuilding (e.g. during development with a volume-mounted `src/`).

### Re-deploying after a `package.json` change

```bash
docker compose build frontend
docker compose up -d frontend
```

## AI Involvement

This project was built with significant assistance from Claude (Anthropic) as an AI coding agent.
See [AGENTS.md](AGENTS.md) for details.

import os
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler

# ---------------------------------------------------------------------------
# Routers — added here as each round is implemented
# ---------------------------------------------------------------------------
from app.routers import households, residents, rooms, devices  # R2
from app.routers import auth  # R2b
from app.routers import catalog  # R3
from app.routers import sessions, assignments  # R4
from app.routers import history  # R5
from app.routers import gamification  # R6
from app.routers import panic         # R7
from app.routers import calendar      # R8

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

logger = logging.getLogger("evenly.scheduler")


# ---------------------------------------------------------------------------
# Scheduler — APScheduler background jobs (R6)
# ---------------------------------------------------------------------------

def _run_daily_jobs() -> None:
    """
    Runs at 00:01 every day.
    1. Streak check: auto-apply streak-safes or reset streaks for inactive residents.
    2. Delegation expiry: lock receivers for expired delegations.
    """
    from app.database import SessionLocal
    from app.agents.gamification_agent import (
        run_daily_streak_check,
        run_delegation_expiry_check,
    )

    db = SessionLocal()
    try:
        logger.info("Running daily streak check...")
        run_daily_streak_check(db)
        logger.info("Running delegation expiry check...")
        run_delegation_expiry_check(db)
        logger.info("Daily gamification jobs complete.")
    except Exception as exc:
        logger.exception("Daily gamification job failed: %s", exc)
    finally:
        db.close()


def _run_calendar_sync() -> None:
    """
    R8: Runs at 07:00 every day.
    Syncs Google Calendar for all households that have an active CalendarConfig.
    """
    from app.database import SessionLocal
    from app.models.calendar_config import CalendarConfig
    from app.agents.calendar_agent import sync_calendar

    db = SessionLocal()
    try:
        active_configs = (
            db.query(CalendarConfig)
            .filter(CalendarConfig.is_active == True)  # noqa: E712
            .all()
        )
        for config in active_configs:
            try:
                logger.info("Syncing calendar for household %d...", config.household_id)
                result = sync_calendar(config.household_id, db)
                logger.info(
                    "Calendar sync for household %d: %d events detected, alert=%s",
                    config.household_id,
                    result.events_detected,
                    result.active_alert_level,
                )
            except Exception as exc:
                logger.exception(
                    "Calendar sync failed for household %d: %s", config.household_id, exc
                )
    except Exception as exc:
        logger.exception("Calendar sync job failed: %s", exc)
    finally:
        db.close()


scheduler = BackgroundScheduler()
scheduler.add_job(
    _run_daily_jobs,
    trigger="cron",
    hour=0,
    minute=1,
    id="daily_gamification",
    replace_existing=True,
)
scheduler.add_job(
    _run_calendar_sync,
    trigger="cron",
    hour=7,
    minute=0,
    id="daily_calendar_sync",
    replace_existing=True,
)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    logger.info("APScheduler started — daily gamification job registered at 00:01.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped.")


app = FastAPI(
    title="Evenly API",
    description="Smart household task distribution — backend API",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS — allow all origins in v1.0 (self-hosted, local network only)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(households.router)
app.include_router(residents.router)
app.include_router(rooms.router)
app.include_router(devices.router)
app.include_router(auth.router)         # R2b — PIN verification + PIN management
app.include_router(catalog.router)      # R3 — Task catalog
app.include_router(sessions.router)     # R4 — Daily sessions
app.include_router(assignments.router)  # R4 — Task assignments
app.include_router(history.router)      # R5 — History, feed, stats
app.include_router(gamification.router) # R6
app.include_router(panic.router)        # R7 — Panic Mode
app.include_router(calendar.router)     # R8 — Calendar Integration — Points, streaks, vouchers


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "version": APP_VERSION}

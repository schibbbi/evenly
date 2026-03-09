"""
calendar router — Google Calendar OAuth2 setup, sync, and status endpoints.

Endpoints:
    GET  /calendar/auth          — start OAuth2 flow (redirect to Google)
    GET  /calendar/callback      — OAuth2 callback, store refresh token
    GET  /calendar/status        — sync status, last synced, active alert level
    POST /calendar/sync          — manual sync trigger
    GET  /calendar/events        — list detected guest events (next 14 days)
    PUT  /calendar/config        — update which calendar IDs to monitor

Security:
    - google_refresh_token is NEVER included in any API response
    - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are loaded from .env only
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.agents.calendar_agent import sync_calendar, SyncResult, CALENDAR_SCOPE
from app.models.calendar_config import CalendarConfig
from app.models.calendar_event import CalendarEvent
from app.models.household_context import HouseholdContext
from app.models.resident import Resident

router = APIRouter(prefix="/calendar", tags=["calendar"])

# OAuth2 redirect URI — must match what's registered in Google Cloud Console
OAUTH2_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/calendar/callback"
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CalendarStatusResponse(BaseModel):
    is_active: bool
    last_synced_at: Optional[str]
    calendar_ids: list[str]
    current_alert_level: Optional[str]
    event_date: Optional[str]
    event_title: Optional[str]
    panic_prompt_active: bool


class CalendarEventResponse(BaseModel):
    id: int
    google_event_id: str
    title: str
    start_datetime: str
    end_datetime: Optional[str]
    guest_probability: str
    alert_level: str
    processed_at: str


class CalendarSyncResponse(BaseModel):
    household_id: int
    events_detected: int
    events_cleared: int
    active_alert_level: Optional[str]
    panic_prompt_active: bool
    error: Optional[str]


class CalendarConfigUpdateRequest(BaseModel):
    calendar_ids: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_config(household_id: int, db: Session) -> CalendarConfig:
    config = (
        db.query(CalendarConfig)
        .filter(CalendarConfig.household_id == household_id)
        .first()
    )
    if not config:
        config = CalendarConfig(
            household_id=household_id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _event_to_response(ev: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=ev.id,
        google_event_id=ev.google_event_id,
        title=ev.title,
        start_datetime=ev.start_datetime.isoformat(),
        end_datetime=ev.end_datetime.isoformat() if ev.end_datetime else None,
        guest_probability=ev.guest_probability.value,
        alert_level=ev.alert_level.value,
        processed_at=ev.processed_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /calendar/auth — start OAuth2 flow
# ---------------------------------------------------------------------------

@router.get("/auth")
def calendar_auth(
    caller: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Start the Google Calendar OAuth2 authorization flow.
    Redirects the browser to Google's consent screen.
    Only admin residents can authorize the calendar integration.
    """
    from google_auth_oauthlib.flow import Flow

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth2 credentials not configured. "
                   "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
        )

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[CALENDAR_SCOPE],
        redirect_uri=OAUTH2_REDIRECT_URI,
    )

    # Store household_id in state param for callback
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=str(caller.household_id),
    )

    return RedirectResponse(url=authorization_url)


# ---------------------------------------------------------------------------
# GET /calendar/callback — handle OAuth2 callback
# ---------------------------------------------------------------------------

@router.get("/callback")
def calendar_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """
    Google OAuth2 callback. Exchanges the authorization code for a refresh token.
    Stores the refresh token in CalendarConfig.
    State parameter contains the household_id.
    """
    from google_auth_oauthlib.flow import Flow

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth2 credentials not configured.")

    try:
        household_id = int(state)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter.")

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[CALENDAR_SCOPE],
        redirect_uri=OAUTH2_REDIRECT_URI,
    )

    # Exchange code for tokens
    flow.fetch_token(code=code)
    credentials = flow.credentials

    if not credentials.refresh_token:
        raise HTTPException(
            status_code=400,
            detail="No refresh token received. "
                   "Ensure the app is authorized with access_type=offline and prompt=consent.",
        )

    # Store refresh token — never returned in API responses
    config = _get_or_create_config(household_id, db)
    config.google_refresh_token = credentials.refresh_token
    config.is_active = True
    db.commit()

    return {
        "status": "ok",
        "message": "Google Calendar authorization complete. "
                   "Calendar sync is now active for your household.",
        "household_id": household_id,
    }


# ---------------------------------------------------------------------------
# GET /calendar/status — sync status and active alert level
# ---------------------------------------------------------------------------

@router.get("/status", response_model=CalendarStatusResponse)
def get_calendar_status(
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Return the calendar sync status and current alert level for the household."""
    config = (
        db.query(CalendarConfig)
        .filter(CalendarConfig.household_id == caller.household_id)
        .first()
    )
    context = (
        db.query(HouseholdContext)
        .filter(HouseholdContext.household_id == caller.household_id)
        .first()
    )

    return CalendarStatusResponse(
        is_active=config.is_active if config else False,
        last_synced_at=config.last_synced_at.isoformat() if config and config.last_synced_at else None,
        calendar_ids=config.get_calendar_ids() if config else ["primary"],
        current_alert_level=context.current_alert_level.value if context and context.current_alert_level else None,
        event_date=context.event_date if context else None,
        event_title=context.event_title if context else None,
        panic_prompt_active=bool(context.panic_prompt_active) if context else False,
    )


# ---------------------------------------------------------------------------
# POST /calendar/sync — manual sync trigger
# ---------------------------------------------------------------------------

@router.post("/sync", response_model=CalendarSyncResponse)
def manual_sync(
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Manually trigger an immediate calendar sync for the household.
    Returns a summary of detected events and the resulting alert level.
    """
    result = sync_calendar(caller.household_id, db)

    return CalendarSyncResponse(
        household_id=result.household_id,
        events_detected=result.events_detected,
        events_cleared=result.events_cleared,
        active_alert_level=result.active_alert_level,
        panic_prompt_active=result.panic_prompt_active,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# GET /calendar/events — list detected guest events
# ---------------------------------------------------------------------------

@router.get("/events", response_model=list[CalendarEventResponse])
def list_calendar_events(
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    List all detected guest events for the next 14 days.
    Returns events ordered by start_datetime ascending.
    """
    config = (
        db.query(CalendarConfig)
        .filter(CalendarConfig.household_id == caller.household_id)
        .first()
    )
    if not config:
        return []

    now = datetime.now(timezone.utc)
    events = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.calendar_config_id == config.id,
            CalendarEvent.start_datetime >= now,
        )
        .order_by(CalendarEvent.start_datetime.asc())
        .all()
    )
    return [_event_to_response(ev) for ev in events]


# ---------------------------------------------------------------------------
# PUT /calendar/config — update monitored calendar IDs
# ---------------------------------------------------------------------------

@router.put("/config", response_model=CalendarStatusResponse)
def update_calendar_config(
    payload: CalendarConfigUpdateRequest,
    caller: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Update the list of Google Calendar IDs to monitor.
    Only admin residents can change the calendar configuration.
    """
    if not payload.calendar_ids:
        raise HTTPException(
            status_code=422,
            detail="calendar_ids must contain at least one calendar ID.",
        )

    config = _get_or_create_config(caller.household_id, db)
    config.set_calendar_ids(payload.calendar_ids)
    db.commit()

    context = (
        db.query(HouseholdContext)
        .filter(HouseholdContext.household_id == caller.household_id)
        .first()
    )

    return CalendarStatusResponse(
        is_active=config.is_active,
        last_synced_at=config.last_synced_at.isoformat() if config.last_synced_at else None,
        calendar_ids=config.get_calendar_ids(),
        current_alert_level=context.current_alert_level.value if context and context.current_alert_level else None,
        event_date=context.event_date if context else None,
        event_title=context.event_title if context else None,
        panic_prompt_active=bool(context.panic_prompt_active) if context else False,
    )

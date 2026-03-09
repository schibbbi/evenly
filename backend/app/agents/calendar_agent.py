"""
calendar_agent.py — Google Calendar sync and guest-event detection.

Runs daily at 07:00 via APScheduler.
Fetches events for the next 14 days, detects guest indicators via keyword matching,
assigns alert levels, and updates HouseholdContext so the Suggestion Agent
can apply scoring boosts.

Boundaries:
  - Read-only — never creates, modifies, or deletes calendar events
  - No AI — keyword matching only
  - Monitors max 14 days ahead
  - Stores event title only (not full description) for privacy

Public API:
    sync_calendar(household_id, db) -> SyncResult
    get_active_context(household_id, db) -> HouseholdContext | None
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.calendar_config import CalendarConfig
from app.models.calendar_event import CalendarEvent
from app.models.household_context import HouseholdContext
from app.models.enums import GuestProbabilityEnum, AlertLevelEnum

logger = logging.getLogger("evenly.calendar")

# ---------------------------------------------------------------------------
# Constants — all configurable here
# ---------------------------------------------------------------------------

# Guest detection keywords — HIGH probability (event almost certainly involves guests)
GUEST_KEYWORDS_HIGH: list[str] = [
    "besuch", "visit", "guests", "guest",
    "birthday", "geburtstag",
    "party", "feier",
    "dinner", "dinner party",
    "kommt vorbei", "coming over",
]

# Guest detection keywords — MEDIUM probability
GUEST_KEYWORDS_MEDIUM: list[str] = [
    "treffen", "meeting", "gathering",
    "brunch", "lunch", "abendessen",
    "get together", "get-together",
    "celebration", "event",
]

# Lookahead window in days
CALENDAR_LOOKAHEAD_DAYS = 14

# Alert level thresholds (days until event, inclusive)
ALERT_PANIC_MAX_DAYS = 0
ALERT_URGENT_MAX_DAYS = 2
ALERT_MEDIUM_MAX_DAYS = 6
# >= 7 days → early

# Alert level priority order (for selecting the worst when multiple events)
ALERT_PRIORITY: dict[AlertLevelEnum, int] = {
    AlertLevelEnum.panic:  4,
    AlertLevelEnum.urgent: 3,
    AlertLevelEnum.medium: 2,
    AlertLevelEnum.early:  1,
}

# Google Calendar API scope
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class DetectedEvent:
    google_event_id: str
    title: str
    start_datetime: datetime
    end_datetime: Optional[datetime]
    guest_probability: GuestProbabilityEnum
    alert_level: AlertLevelEnum
    days_until: int


@dataclass
class SyncResult:
    household_id: int
    events_detected: int
    events_cleared: int
    active_alert_level: Optional[str]
    panic_prompt_active: bool
    detected: list[DetectedEvent] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def sync_calendar(household_id: int, db: Session) -> SyncResult:
    """
    Main sync function. Called daily at 07:00 and on manual trigger.
    1. Load CalendarConfig for the household
    2. Authenticate with Google Calendar API
    3. Fetch events for next 14 days
    4. Detect guest events via keyword matching
    5. Upsert CalendarEvent records
    6. Clear expired events
    7. Update HouseholdContext
    """
    config = (
        db.query(CalendarConfig)
        .filter(
            CalendarConfig.household_id == household_id,
            CalendarConfig.is_active == True,  # noqa: E712
        )
        .first()
    )

    if not config:
        return SyncResult(
            household_id=household_id,
            events_detected=0,
            events_cleared=0,
            active_alert_level=None,
            panic_prompt_active=False,
            error="No active calendar configuration found for this household.",
        )

    # Fetch events from Google Calendar
    try:
        raw_events = _fetch_google_events(config)
    except Exception as exc:
        logger.exception("Google Calendar fetch failed for household %d: %s", household_id, exc)
        return SyncResult(
            household_id=household_id,
            events_detected=0,
            events_cleared=0,
            active_alert_level=None,
            panic_prompt_active=False,
            error=f"Google Calendar API error: {exc}",
        )

    now = datetime.now(timezone.utc)
    today = now.date()

    # Detect guest events
    detected: list[DetectedEvent] = []
    for raw in raw_events:
        start_dt = _parse_google_datetime(raw.get("start", {}))
        end_dt = _parse_google_datetime(raw.get("end", {}))
        if not start_dt:
            continue

        title = raw.get("summary", "")
        description = raw.get("description", "") or ""
        attendees = raw.get("attendees", [])

        probability = _detect_guest_probability(title, description, attendees)
        if probability == GuestProbabilityEnum.low:
            continue  # Low-probability events are ignored (per briefing)

        days_until = (start_dt.date() - today).days
        if days_until < 0:
            continue  # Past events — will be cleared separately

        alert_level = _assign_alert_level(days_until)

        detected.append(DetectedEvent(
            google_event_id=raw.get("id", ""),
            title=title[:500],  # truncate for DB
            start_datetime=start_dt,
            end_datetime=end_dt,
            guest_probability=probability,
            alert_level=alert_level,
            days_until=days_until,
        ))

    # Upsert CalendarEvent records
    for event in detected:
        existing = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.calendar_config_id == config.id,
                CalendarEvent.google_event_id == event.google_event_id,
            )
            .first()
        )
        if existing:
            # Update alert level (may have changed as event gets closer)
            existing.alert_level = event.alert_level
            existing.guest_probability = event.guest_probability
            existing.processed_at = now
        else:
            new_event = CalendarEvent(
                calendar_config_id=config.id,
                google_event_id=event.google_event_id,
                title=event.title,
                start_datetime=event.start_datetime,
                end_datetime=event.end_datetime,
                guest_probability=event.guest_probability,
                alert_level=event.alert_level,
                processed_at=now,
            )
            db.add(new_event)

    # Clear expired events (started in the past)
    expired = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.calendar_config_id == config.id,
            CalendarEvent.start_datetime < now,
        )
        .all()
    )
    cleared_count = len(expired)
    for e in expired:
        db.delete(e)

    # Update CalendarConfig last_synced_at
    config.last_synced_at = now

    db.flush()

    # Determine current worst-case alert level across all active events
    active_events = (
        db.query(CalendarEvent)
        .filter(CalendarEvent.calendar_config_id == config.id)
        .all()
    )

    best_alert: Optional[AlertLevelEnum] = None
    soonest_event: Optional[CalendarEvent] = None

    for ev in active_events:
        if best_alert is None or ALERT_PRIORITY[ev.alert_level] > ALERT_PRIORITY[best_alert]:
            best_alert = ev.alert_level
            soonest_event = ev

    panic_active = best_alert == AlertLevelEnum.panic

    # Upsert HouseholdContext
    _upsert_household_context(
        household_id=household_id,
        alert_level=best_alert,
        soonest_event=soonest_event,
        panic_active=panic_active,
        db=db,
    )

    db.commit()

    return SyncResult(
        household_id=household_id,
        events_detected=len(detected),
        events_cleared=cleared_count,
        active_alert_level=best_alert.value if best_alert else None,
        panic_prompt_active=panic_active,
        detected=detected,
    )


def get_active_context(household_id: int, db: Session) -> Optional[HouseholdContext]:
    """
    Return the current HouseholdContext for the household, or None if not set.
    Called by Suggestion Agent on each session to apply scoring boosts.
    """
    return (
        db.query(HouseholdContext)
        .filter(HouseholdContext.household_id == household_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Google Calendar API interaction
# ---------------------------------------------------------------------------

def _fetch_google_events(config: CalendarConfig) -> list[dict]:
    """
    Authenticate with Google and fetch events for the next CALENDAR_LOOKAHEAD_DAYS days.
    Returns raw event dicts from the Google API.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

    creds = Credentials(
        token=None,
        refresh_token=config.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[CALENDAR_SCOPE],
    )

    # Refresh token if needed
    if not creds.valid:
        creds.refresh(Request())

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    now_utc = datetime.now(timezone.utc)
    time_min = now_utc.isoformat()
    time_max = (now_utc + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)).isoformat()

    calendar_ids = config.get_calendar_ids()
    all_events: list[dict] = []

    for cal_id in calendar_ids:
        try:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                )
                .execute()
            )
            all_events.extend(result.get("items", []))
        except Exception as exc:
            logger.warning("Failed to fetch events from calendar %s: %s", cal_id, exc)

    return all_events


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_guest_probability(
    title: str, description: str, attendees: list[dict]
) -> GuestProbabilityEnum:
    """
    Determine guest probability from event metadata.
    High: keyword match in title/description
    Medium: multiple external attendees
    Low: none of the above
    """
    combined = (title + " " + description).lower()

    for keyword in GUEST_KEYWORDS_HIGH:
        if keyword.lower() in combined:
            return GuestProbabilityEnum.high

    for keyword in GUEST_KEYWORDS_MEDIUM:
        if keyword.lower() in combined:
            return GuestProbabilityEnum.medium

    # Multiple attendees (external guests likely)
    if len(attendees) >= 2:
        return GuestProbabilityEnum.medium

    return GuestProbabilityEnum.low


def _assign_alert_level(days_until: int) -> AlertLevelEnum:
    """Map days until event to alert level."""
    if days_until <= ALERT_PANIC_MAX_DAYS:
        return AlertLevelEnum.panic
    elif days_until <= ALERT_URGENT_MAX_DAYS:
        return AlertLevelEnum.urgent
    elif days_until <= ALERT_MEDIUM_MAX_DAYS:
        return AlertLevelEnum.medium
    else:
        return AlertLevelEnum.early


def _parse_google_datetime(dt_dict: dict) -> Optional[datetime]:
    """
    Parse a Google Calendar datetime dict.
    Google returns either {"dateTime": "..."} or {"date": "..."} for all-day events.
    """
    if "dateTime" in dt_dict:
        raw = dt_dict["dateTime"]
        try:
            # Python 3.11+ handles ISO format with timezone offset
            return datetime.fromisoformat(raw).astimezone(timezone.utc)
        except ValueError:
            return None
    elif "date" in dt_dict:
        # All-day event — treat as midnight UTC
        try:
            d = date.fromisoformat(dt_dict["date"])
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _upsert_household_context(
    household_id: int,
    alert_level: Optional[AlertLevelEnum],
    soonest_event: Optional[CalendarEvent],
    panic_active: bool,
    db: Session,
) -> None:
    """Upsert the HouseholdContext row for this household."""
    now = datetime.now(timezone.utc)
    context = (
        db.query(HouseholdContext)
        .filter(HouseholdContext.household_id == household_id)
        .first()
    )

    if context:
        context.current_alert_level = alert_level
        context.event_date = soonest_event.start_datetime.date().isoformat() if soonest_event else None
        context.event_title = soonest_event.title if soonest_event else None
        context.panic_prompt_active = panic_active
        context.updated_at = now
    else:
        context = HouseholdContext(
            household_id=household_id,
            current_alert_level=alert_level,
            event_date=soonest_event.start_datetime.date().isoformat() if soonest_event else None,
            event_title=soonest_event.title if soonest_event else None,
            panic_prompt_active=panic_active,
            updated_at=now,
        )
        db.add(context)

    db.flush()

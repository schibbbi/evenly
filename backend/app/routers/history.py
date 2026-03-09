"""
history router — Activity history, feed, and stats endpoints.

Endpoints:
    GET /feed                           — shared activity feed (last 50 entries)
    GET /history                        — full history log with filters
    GET /residents/{id}/stats           — personal stats
    GET /household/stats                — household-wide stats
    GET /residents/{id}/scoring-profile — internal scoring profile (rejection, imbalance, time pref)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_active_resident, require_role
from app.models.history_entry import HistoryEntry
from app.models.household_feed_entry import HouseholdFeedEntry
from app.models.resident_scoring_profile import ResidentScoringProfile
from app.models.resident import Resident
from app.models.task_template import TaskTemplate

router = APIRouter(tags=["history"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FeedEntryResponse(BaseModel):
    id: int
    resident_id: int
    text: str
    action_type: str
    task_name: str
    timestamp: str


class HistoryEntryResponse(BaseModel):
    id: int
    resident_id: int
    task_template_id: int
    assignment_id: Optional[int]
    action: str
    timestamp: str
    room_type: str
    points_awarded: Optional[int]
    was_unpopular: bool
    was_forced: bool


class ResidentStatsResponse(BaseModel):
    resident_id: int
    completed_all_time: int
    completed_this_week: int
    completed_this_month: int
    skipped_this_week: int
    favorite_room: Optional[str]
    favorite_category: Optional[str]
    current_streak: int   # placeholder — computed by R6


class HouseholdStatsResponse(BaseModel):
    completed_this_week: int
    completed_this_month: int
    most_completed_task: Optional[str]
    most_skipped_task: Optional[str]
    resident_breakdown: list[dict]   # [{ resident_id, display_name, completed_count, pct }]


class ScoringProfileResponse(BaseModel):
    resident_id: int
    task_template_id: int
    rejection_count: int
    last_rejected_at: Optional[str]
    preferred_time_of_day: str
    imbalance_flag: bool
    last_updated: str


# ---------------------------------------------------------------------------
# GET /feed
# ---------------------------------------------------------------------------

@router.get("/feed", response_model=list[FeedEntryResponse])
def get_feed(
    limit: int = Query(default=50, ge=1, le=200),
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Return the shared activity feed, newest first."""
    entries = (
        db.query(HouseholdFeedEntry)
        .order_by(HouseholdFeedEntry.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        FeedEntryResponse(
            id=e.id,
            resident_id=e.resident_id,
            text=e.text,
            action_type=e.action_type,
            task_name=e.task_name,
            timestamp=e.timestamp.isoformat(),
        )
        for e in entries
    ]


# ---------------------------------------------------------------------------
# GET /history
# ---------------------------------------------------------------------------

@router.get("/history", response_model=list[HistoryEntryResponse])
def get_history(
    resident_id: Optional[int] = Query(None),
    room_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    limit: int = Query(default=100, ge=1, le=500),
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Full history log with optional filters."""
    query = db.query(HistoryEntry).order_by(HistoryEntry.timestamp.desc())

    if resident_id is not None:
        query = query.filter(HistoryEntry.resident_id == resident_id)
    if room_type is not None:
        query = query.filter(HistoryEntry.room_type == room_type)
    if date_from:
        dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        query = query.filter(HistoryEntry.timestamp >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
        query = query.filter(HistoryEntry.timestamp < dt_to)

    entries = query.limit(limit).all()
    return [
        HistoryEntryResponse(
            id=e.id,
            resident_id=e.resident_id,
            task_template_id=e.task_template_id,
            assignment_id=e.assignment_id,
            action=e.action,
            timestamp=e.timestamp.isoformat(),
            room_type=e.room_type,
            points_awarded=e.points_awarded,
            was_unpopular=e.was_unpopular,
            was_forced=e.was_forced,
        )
        for e in entries
    ]


# ---------------------------------------------------------------------------
# GET /residents/{id}/stats
# ---------------------------------------------------------------------------

@router.get("/residents/{resident_id}/stats", response_model=ResidentStatsResponse)
def get_resident_stats(
    resident_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Personal stats for a resident."""
    resident = db.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    base = db.query(HistoryEntry).filter(
        HistoryEntry.resident_id == resident_id,
        HistoryEntry.action == "completed",
    )

    completed_all_time = base.count()
    completed_this_week = base.filter(HistoryEntry.timestamp >= week_start).count()
    completed_this_month = base.filter(HistoryEntry.timestamp >= month_start).count()

    skipped_this_week = (
        db.query(HistoryEntry)
        .filter(
            HistoryEntry.resident_id == resident_id,
            HistoryEntry.action == "skipped",
            HistoryEntry.timestamp >= week_start,
        )
        .count()
    )

    # Favorite room (most completed)
    room_row = (
        db.query(HistoryEntry.room_type, func.count(HistoryEntry.id).label("cnt"))
        .filter(
            HistoryEntry.resident_id == resident_id,
            HistoryEntry.action == "completed",
        )
        .group_by(HistoryEntry.room_type)
        .order_by(func.count(HistoryEntry.id).desc())
        .first()
    )
    favorite_room = room_row[0] if room_row else None

    # Favorite category (most completed)
    cat_row = (
        db.query(TaskTemplate.category, func.count(HistoryEntry.id).label("cnt"))
        .join(TaskTemplate, HistoryEntry.task_template_id == TaskTemplate.id)
        .filter(
            HistoryEntry.resident_id == resident_id,
            HistoryEntry.action == "completed",
        )
        .group_by(TaskTemplate.category)
        .order_by(func.count(HistoryEntry.id).desc())
        .first()
    )
    favorite_category = cat_row[0] if cat_row else None

    return ResidentStatsResponse(
        resident_id=resident_id,
        completed_all_time=completed_all_time,
        completed_this_week=completed_this_week,
        completed_this_month=completed_this_month,
        skipped_this_week=skipped_this_week,
        favorite_room=favorite_room,
        favorite_category=favorite_category,
        current_streak=0,  # placeholder — computed by Gamification Agent in R6
    )


# ---------------------------------------------------------------------------
# GET /household/stats
# ---------------------------------------------------------------------------

@router.get("/household/stats", response_model=HouseholdStatsResponse)
def get_household_stats(
    household_id: int = Query(...),
    active_resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Household-wide aggregated stats."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    # All residents in household
    residents = db.query(Resident).filter(Resident.household_id == household_id).all()
    resident_ids = [r.id for r in residents]

    completed_this_week = (
        db.query(HistoryEntry)
        .filter(
            HistoryEntry.resident_id.in_(resident_ids),
            HistoryEntry.action == "completed",
            HistoryEntry.timestamp >= week_start,
        )
        .count()
    )
    completed_this_month = (
        db.query(HistoryEntry)
        .filter(
            HistoryEntry.resident_id.in_(resident_ids),
            HistoryEntry.action == "completed",
            HistoryEntry.timestamp >= month_start,
        )
        .count()
    )

    # Most completed task (by task_template_id)
    most_completed_row = (
        db.query(TaskTemplate.name, func.count(HistoryEntry.id).label("cnt"))
        .join(TaskTemplate, HistoryEntry.task_template_id == TaskTemplate.id)
        .filter(
            HistoryEntry.resident_id.in_(resident_ids),
            HistoryEntry.action == "completed",
        )
        .group_by(TaskTemplate.name)
        .order_by(func.count(HistoryEntry.id).desc())
        .first()
    )
    most_completed_task = most_completed_row[0] if most_completed_row else None

    # Most skipped task
    most_skipped_row = (
        db.query(TaskTemplate.name, func.count(HistoryEntry.id).label("cnt"))
        .join(TaskTemplate, HistoryEntry.task_template_id == TaskTemplate.id)
        .filter(
            HistoryEntry.resident_id.in_(resident_ids),
            HistoryEntry.action == "skipped",
        )
        .group_by(TaskTemplate.name)
        .order_by(func.count(HistoryEntry.id).desc())
        .first()
    )
    most_skipped_task = most_skipped_row[0] if most_skipped_row else None

    # Resident breakdown
    total = completed_this_month or 1  # avoid div-by-zero
    breakdown = []
    for r in residents:
        cnt = (
            db.query(HistoryEntry)
            .filter(
                HistoryEntry.resident_id == r.id,
                HistoryEntry.action == "completed",
                HistoryEntry.timestamp >= month_start,
            )
            .count()
        )
        breakdown.append({
            "resident_id": r.id,
            "display_name": r.display_name,
            "completed_count": cnt,
            "pct": round(cnt / total * 100, 1),
        })

    return HouseholdStatsResponse(
        completed_this_week=completed_this_week,
        completed_this_month=completed_this_month,
        most_completed_task=most_completed_task,
        most_skipped_task=most_skipped_task,
        resident_breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# GET /residents/{id}/scoring-profile
# ---------------------------------------------------------------------------

@router.get("/residents/{resident_id}/scoring-profile", response_model=list[ScoringProfileResponse])
def get_scoring_profile(
    resident_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Internal scoring profile for a resident — all task entries."""
    resident = db.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    profiles = (
        db.query(ResidentScoringProfile)
        .filter(ResidentScoringProfile.resident_id == resident_id)
        .all()
    )
    return [
        ScoringProfileResponse(
            resident_id=p.resident_id,
            task_template_id=p.task_template_id,
            rejection_count=p.rejection_count,
            last_rejected_at=p.last_rejected_at.isoformat() if p.last_rejected_at else None,
            preferred_time_of_day=p.preferred_time_of_day,
            imbalance_flag=p.imbalance_flag,
            last_updated=p.last_updated.isoformat(),
        )
        for p in profiles
    ]

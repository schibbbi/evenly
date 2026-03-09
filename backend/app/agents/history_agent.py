"""
history_agent.py — History recording and feedback loop.

Called synchronously after every task action (complete, skip).
Writes HistoryEntry, optionally HouseholdFeedEntry,
and updates ResidentScoringProfile.

Public API:
    record_completion(assignment, db) -> RecordResult
    record_skip(assignment, db) -> RecordResult
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident
from app.models.history_entry import HistoryEntry
from app.models.household_feed_entry import HouseholdFeedEntry
from app.models.resident_scoring_profile import ResidentScoringProfile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REJECTION_WARNING_THRESHOLD = 2       # log warning at this count
REJECTION_PROMPT_THRESHOLD = 3        # surface prompt to resident at this count
REJECTION_DECAY_DAYS = 14             # decay rejection_count by 1 per 14 days without rejection
TIME_PREF_MIN_COMPLETIONS = 5         # minimum completions to establish time preference
IMBALANCE_WINDOW_DAYS = 30            # look-back window for imbalance detection

# Time-of-day windows (hour, inclusive start, exclusive end)
TIME_WINDOWS = {
    "morning":   (5, 12),
    "afternoon": (12, 18),
    "evening":   (18, 23),
}


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class RecordResult:
    history_entry_id: int
    feed_entry_id: Optional[int] = None
    rejection_prompt: Optional[str] = None   # non-None when user should be prompted
    rejection_count: int = 0


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def record_completion(assignment: TaskAssignment, db: Session) -> RecordResult:
    """
    Called after POST /assignments/{id}/complete.
    - Creates HistoryEntry (action=completed)
    - Creates HouseholdFeedEntry
    - Runs feedback loop: imbalance detection, time preference
    """
    task = db.get(TaskTemplate, assignment.task_template_id)
    resident = db.get(Resident, assignment.resident_id)
    now = datetime.now(timezone.utc)

    # Write HistoryEntry
    entry = HistoryEntry(
        resident_id=assignment.resident_id,
        task_template_id=assignment.task_template_id,
        assignment_id=assignment.id,
        action="completed",
        timestamp=now,
        room_type=task.room_type,
        was_unpopular=False,  # populated by gamification agent in R6
        was_forced=assignment.is_forced,
    )
    db.add(entry)
    db.flush()  # get entry.id

    # Write HouseholdFeedEntry
    feed_text = f"{resident.display_name} completed: {task.name}"
    feed = HouseholdFeedEntry(
        resident_id=assignment.resident_id,
        text=feed_text,
        action_type="completed",
        task_name=task.name,
        timestamp=now,
    )
    db.add(feed)
    db.flush()

    # Feedback loop
    _update_time_preference(assignment, task, resident, now, db)
    _update_imbalance(assignment.task_template_id, assignment.resident_id, db, now)

    db.commit()

    return RecordResult(
        history_entry_id=entry.id,
        feed_entry_id=feed.id,
    )


def record_skip(assignment: TaskAssignment, db: Session) -> RecordResult:
    """
    Called after POST /assignments/{id}/skip.
    - Creates HistoryEntry (action=skipped) — NO feed entry
    - Increments rejection_count on ResidentScoringProfile
    - Returns prompt message if threshold reached
    """
    task = db.get(TaskTemplate, assignment.task_template_id)
    now = datetime.now(timezone.utc)

    # Write HistoryEntry (no feed entry — skips are private)
    entry = HistoryEntry(
        resident_id=assignment.resident_id,
        task_template_id=assignment.task_template_id,
        assignment_id=assignment.id,
        action="skipped",
        timestamp=now,
        room_type=task.room_type,
        was_unpopular=False,
        was_forced=assignment.is_forced,
    )
    db.add(entry)
    db.flush()

    # Feedback loop: rejection tracking
    profile = _get_or_create_profile(assignment.resident_id, assignment.task_template_id, db)
    _decay_rejection_count(profile, now)
    profile.rejection_count += 1
    profile.last_rejected_at = now
    profile.last_updated = now

    prompt = None
    if profile.rejection_count >= REJECTION_PROMPT_THRESHOLD:
        prompt = (
            f"You've skipped \"{task.name}\" {profile.rejection_count} times. "
            "Want to pause it or reduce its frequency? "
            "You can edit it in the catalog settings."
        )

    db.commit()

    return RecordResult(
        history_entry_id=entry.id,
        feed_entry_id=None,
        rejection_prompt=prompt,
        rejection_count=profile.rejection_count,
    )


# ---------------------------------------------------------------------------
# Feedback loop helpers
# ---------------------------------------------------------------------------

def _update_time_preference(
    assignment: TaskAssignment,
    task: TaskTemplate,
    resident: Resident,
    now: datetime,
    db: Session,
) -> None:
    """
    After 5+ completions in the same time window for a task category,
    set preferred_time_of_day on the scoring profile.
    """
    hour = now.hour
    current_window = _hour_to_window(hour)
    if current_window == "none":
        return

    # Count completions in this window for this category (last 90 days).
    # Note: flush() above makes the just-inserted HistoryEntry visible within
    # this transaction, so the count includes the current completion. Correct.
    cutoff = now - timedelta(days=90)
    completions_in_window = (
        db.query(HistoryEntry)
        .join(TaskTemplate, HistoryEntry.task_template_id == TaskTemplate.id)
        .filter(
            HistoryEntry.resident_id == resident.id,
            HistoryEntry.action == "completed",
            HistoryEntry.timestamp >= cutoff,
            TaskTemplate.category == task.category,
        )
        .all()
    )

    window_count = sum(
        1 for h in completions_in_window
        if _hour_to_window(_utc_hour(h.timestamp)) == current_window
    )

    if window_count >= TIME_PREF_MIN_COMPLETIONS:
        # Update all profiles for this resident + category
        profiles = (
            db.query(ResidentScoringProfile)
            .join(TaskTemplate, ResidentScoringProfile.task_template_id == TaskTemplate.id)
            .filter(
                ResidentScoringProfile.resident_id == resident.id,
                TaskTemplate.category == task.category,
            )
            .all()
        )
        for p in profiles:
            p.preferred_time_of_day = current_window
            p.last_updated = now

        # Also update/create profile for current task
        profile = _get_or_create_profile(resident.id, task.id, db)
        profile.preferred_time_of_day = current_window
        profile.last_updated = now


def _update_imbalance(
    task_template_id: int,
    completing_resident_id: int,
    db: Session,
    now: datetime,
) -> None:
    """
    Check if this task was done exclusively by one resident in last 30 days.
    If yes: set imbalance_flag=True for all OTHER residents.
    Reset imbalance_flag for the completing resident.
    """
    cutoff = now - timedelta(days=IMBALANCE_WINDOW_DAYS)

    # Who completed this task in the window?
    completions = (
        db.query(HistoryEntry.resident_id)
        .filter(
            HistoryEntry.task_template_id == task_template_id,
            HistoryEntry.action == "completed",
            HistoryEntry.timestamp >= cutoff,
        )
        .distinct()
        .all()
    )
    completing_residents = {row[0] for row in completions}

    if len(completing_residents) == 1:
        # Only one resident did this task — imbalance detected
        sole_doer = next(iter(completing_residents))

        # Find all household residents via one of the completing resident's household
        resident = db.get(Resident, completing_resident_id)
        all_residents = (
            db.query(Resident)
            .filter(Resident.household_id == resident.household_id)
            .all()
        )

        for r in all_residents:
            profile = _get_or_create_profile(r.id, task_template_id, db)
            if r.id == sole_doer:
                # The one who always does it — no imbalance bonus for them
                profile.imbalance_flag = False
            else:
                # Others should do it — give them the imbalance boost
                profile.imbalance_flag = True
            profile.last_updated = now
    else:
        # Multiple residents contributed — clear imbalance flags
        profiles = (
            db.query(ResidentScoringProfile)
            .filter(ResidentScoringProfile.task_template_id == task_template_id)
            .all()
        )
        for p in profiles:
            p.imbalance_flag = False
            p.last_updated = now


def _decay_rejection_count(profile: ResidentScoringProfile, now: datetime) -> None:
    """
    Decay rejection_count by 1 per REJECTION_DECAY_DAYS without a rejection.
    Called before incrementing on a new skip.
    """
    if profile.last_rejected_at is None or profile.rejection_count <= 0:
        return
    last = profile.last_rejected_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    days_since = (now - last).days
    decay = days_since // REJECTION_DECAY_DAYS
    if decay > 0:
        profile.rejection_count = max(0, profile.rejection_count - decay)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _get_or_create_profile(
    resident_id: int,
    task_template_id: int,
    db: Session,
) -> ResidentScoringProfile:
    profile = (
        db.query(ResidentScoringProfile)
        .filter(
            ResidentScoringProfile.resident_id == resident_id,
            ResidentScoringProfile.task_template_id == task_template_id,
        )
        .first()
    )
    if not profile:
        profile = ResidentScoringProfile(
            resident_id=resident_id,
            task_template_id=task_template_id,
            last_updated=datetime.now(timezone.utc),
        )
        db.add(profile)
        db.flush()
    return profile


def _hour_to_window(hour: int) -> str:
    for window, (start, end) in TIME_WINDOWS.items():
        if start <= hour < end:
            return window
    return "none"


def _utc_hour(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.hour

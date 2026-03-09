"""
suggestion_agent.py — Rule-based daily task scoring and suggestion engine.

Entry point: get_suggestions(session, db) → list[ScoredTask]

Scoring formula:
    score = overdue_factor
          + seasonality_factor
          - rejection_malus
          + imbalance_bonus
          + random_factor
          + unpopular_bonus
          + robot_preference_bonus
          - robot_manual_malus

All weights are configurable constants at the top of this file.
No AI is used at runtime — purely deterministic rule-based logic.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.daily_session import DailySession
from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident
from app.models.resident_preference import ResidentPreference
from app.models.household import Household
from app.models.household_context import HouseholdContext  # R8

# ---------------------------------------------------------------------------
# Scoring constants — tune here, not in formula code
# ---------------------------------------------------------------------------

OVERDUE_FACTOR_WEIGHT = 10          # multiplier: (days_overdue / freq) * weight
OVERDUE_FACTOR_CAP = 50             # maximum overdue contribution
SEASONALITY_BONUS = 5               # garden in spring/summer; indoor in autumn/winter
REJECTION_MALUS_PER_DAY = 3        # per rejection in last 7 days
REJECTION_RECOVERY_PER_DAY = 1     # recover 1 point per day since rejection
IMBALANCE_BONUS = 8                 # task always done by others
RANDOM_FACTOR_MAX = 3.0             # uniform [0.0, 3.0]
UNPOPULAR_BONUS = 5                 # all residents dislike this category
ROBOT_LOW_ENERGY_BONUS = 20        # robot variant at energy=low
ROBOT_MANUAL_LOW_ENERGY_MALUS = 10 # manual task when robot exists and energy=low
ROBOT_RECENT_RUN_HOURS = 24        # hours after robot run to suppress manual variant

# Unpopular overdue escalation threshold
UNPOPULAR_OVERDUE_MULTIPLIER = 2   # task is 2x overdue AND all dislike → force-include

# R8: Calendar alert scoring boosts (applied to tier-1 / shared-area room tasks)
# Tier-1 rooms as defined in panic_agent — rooms guests are most likely to see
CALENDAR_TIER1_ROOMS = {"hallway", "bathroom", "kitchen", "living"}

CALENDAR_BOOST_EARLY = 5    # +5 to shared/visible room tasks — 7+ days out
CALENDAR_BOOST_MEDIUM = 10  # +10 to tier-1 rooms — 3–6 days out
CALENDAR_BOOST_URGENT = 20  # +20 to tier-1 rooms — 1–2 days out
# panic: no score boost — panic prompt surfaced instead (handled in sessions router)

# Device flag → Household attribute mapping (mirrors catalog router)
DEVICE_FLAG_TO_HOUSEHOLD_ATTR = {
    "robot_vacuum":   "has_robot_vacuum",
    "robot_mop":      "has_robot_mop",
    "dishwasher":     "has_dishwasher",
    "washer":         "has_washer",
    "dryer":          "has_dryer",
    "window_cleaner": "has_window_cleaner",
    "steam_cleaner":  "has_steam_cleaner",
    "robot_mower":    "has_robot_mower",
    "irrigation":     "has_irrigation",
}

HOUSEHOLD_FLAG_TO_ATTR = {
    "children": "has_children",
    "cats":     "has_cats",
    "dogs":     "has_dogs",
}

ENERGY_ORDER = {"low": 0, "medium": 1, "high": 2}


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class ScoredTask:
    task: TaskTemplate
    score: float
    is_forced: bool = False         # unpopular overdue escalation
    panic_prompt: Optional[str] = None  # R8: non-None when calendar alert_level=panic


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_suggestions(
    session: DailySession,
    db: Session,
    excluded_task_ids: Optional[list[int]] = None,
    max_results: int = 3,
) -> list[ScoredTask]:
    """
    Score all eligible tasks for the given session and return top `max_results`.

    excluded_task_ids: task IDs already shown in this session (for reroll).
    """
    excluded_task_ids = excluded_task_ids or []
    resident = db.get(Resident, session.resident_id)
    household = db.get(Household, resident.household_id)

    all_tasks = db.query(TaskTemplate).filter(TaskTemplate.is_active == True).all()  # noqa: E712

    # --- Pre-compute context needed for scoring ---
    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    preferences = _load_preferences(session.resident_id, db)
    all_resident_ids = _household_resident_ids(household.id, db)
    all_preferences = _load_all_preferences(all_resident_ids, db)
    recent_completions = _recent_completions(all_resident_ids, db)

    # R8: Load calendar alert context
    household_context = (
        db.query(HouseholdContext)
        .filter(HouseholdContext.household_id == household.id)
        .first()
    )
    calendar_alert = household_context.current_alert_level if household_context else None
    calendar_panic = bool(household_context.panic_prompt_active) if household_context else False
    # Map task_template_id → last completion datetime (across all residents)
    last_done_map: dict[int, datetime] = {}
    for assignment in recent_completions:
        tid = assignment.task_template_id
        if tid not in last_done_map or assignment.completed_at > last_done_map[tid]:
            last_done_map[tid] = assignment.completed_at

    # Resident-specific last-done map (for imbalance detection)
    my_completions = [a for a in recent_completions if a.resident_id == session.resident_id]
    my_last_done: dict[int, datetime] = {}
    for a in my_completions:
        tid = a.task_template_id
        if tid not in my_last_done or a.completed_at > my_last_done[tid]:
            my_last_done[tid] = a.completed_at

    # Recent skips/rejections (last 7 days) for this resident
    rejection_map = _rejection_map(session.resident_id, db, now)

    # Robot tasks completed within suppression window (for manual suppression)
    robot_run_task_ids = _recently_run_robot_tasks(db, now)

    month = now.month
    season = _season(month)

    # --- Score each task ---
    scored: list[ScoredTask] = []
    forced: list[ScoredTask] = []

    for task in all_tasks:
        if task.id in excluded_task_ids:
            continue

        # --- Visibility filters ---
        if not _household_flag_ok(task, household):
            continue
        if not _device_flag_ok(task, household):
            continue

        # Energy filter: task energy must be ≤ resident's current energy
        if ENERGY_ORDER.get(task.energy_level, 1) > ENERGY_ORDER.get(session.energy_level, 1):
            continue

        # Time filter: task must fit in available time
        if task.default_duration_minutes > session.available_minutes:
            continue

        # Compute effective frequency (reduced when robot present)
        effective_freq = _effective_frequency(task, household)

        # Suppress manual variant if robot ran within suppression window
        if _is_manual_suppressed(task, household, robot_run_task_ids):
            continue

        # Frequency window: skip if done recently (unless overdue)
        last_done = last_done_map.get(task.id)
        days_since_done = (now - last_done).total_seconds() / 86400 if last_done else 9999

        if last_done and days_since_done < effective_freq:
            # Within frequency window — only include if overdue escalation applies
            if not _is_force_candidate(task, days_since_done, effective_freq, all_preferences):
                continue

        # --- Calculate score ---
        score = _score_task(
            task=task,
            session=session,
            household=household,
            days_since_done=days_since_done,
            effective_freq=effective_freq,
            season=season,
            rejection_map=rejection_map,
            now=now,
            preferences=preferences,
            all_preferences=all_preferences,
            all_resident_ids=all_resident_ids,
            my_last_done=my_last_done,
            last_done_map=last_done_map,
        )

        # R8: Apply calendar alert scoring boosts
        score += _calendar_boost(task, calendar_alert)

        is_forced = _is_force_candidate(task, days_since_done, effective_freq, all_preferences)

        # R8: urgent alert → force-include at least 1 visible-area task
        if (
            calendar_alert is not None
            and hasattr(calendar_alert, "value")
            and calendar_alert.value == "urgent"
            and task.room_type in CALENDAR_TIER1_ROOMS
            and not is_forced
        ):
            is_forced = True  # surfaces at least one visible-area task

        st = ScoredTask(task=task, score=score, is_forced=is_forced)

        if is_forced:
            forced.append(st)
        else:
            scored.append(st)

    # Sort non-forced by score descending
    scored.sort(key=lambda s: s.score, reverse=True)

    # Build result: forced tasks first (up to 1), fill rest from scored
    result: list[ScoredTask] = []
    if forced:
        # Pick the most overdue forced task (highest score among forced)
        forced.sort(key=lambda s: s.score, reverse=True)
        result.append(forced[0])

    remaining_slots = max_results - len(result)
    result.extend(scored[:remaining_slots])

    # R8: Attach panic prompt to first result if panic alert is active
    if calendar_panic and result and household_context:
        event_info = ""
        if household_context.event_title:
            event_info = f" ({household_context.event_title})"
        result[0].panic_prompt = (
            f"Guests arriving today{event_info} — want to activate Panic Mode? "
            "Go to the Panic Mode tab for a quick cleaning plan."
        )

    return result


# ---------------------------------------------------------------------------
# Scoring sub-functions
# ---------------------------------------------------------------------------

def _score_task(
    task: TaskTemplate,
    session: DailySession,
    household: Household,
    days_since_done: float,
    effective_freq: float,
    season: str,
    rejection_map: dict,
    now: datetime,
    preferences: dict,
    all_preferences: dict,
    all_resident_ids: list[int],
    my_last_done: dict,
    last_done_map: dict,
) -> float:
    score = 0.0

    # 1. Overdue factor
    overdue = min((days_since_done / effective_freq) * OVERDUE_FACTOR_WEIGHT, OVERDUE_FACTOR_CAP)
    score += overdue

    # 2. Seasonality
    score += _seasonality(task, season)

    # 3. Rejection malus
    if task.id in rejection_map:
        rejection_info = rejection_map[task.id]
        days_ago = rejection_info["days_ago"]
        # malus decays by 1 per day
        raw_malus = REJECTION_MALUS_PER_DAY - (days_ago * REJECTION_RECOVERY_PER_DAY)
        score -= max(raw_malus, 0)

    # 4. Imbalance bonus: task done mostly by others
    score += _imbalance_bonus(task.id, session.resident_id, all_resident_ids, my_last_done, last_done_map)

    # 5. Random factor (variety)
    score += random.uniform(0.0, RANDOM_FACTOR_MAX)

    # 6. Unpopular bonus: all residents dislike this category
    if _all_dislike(task.category, all_preferences, all_resident_ids):
        score += UNPOPULAR_BONUS

    # 7. Robot scoring (energy-aware)
    score += _robot_score(task, session, household)

    return score


def _effective_frequency(task: TaskTemplate, household: Household) -> float:
    """
    Apply robot_frequency_multiplier to reduce manual task frequency
    when the corresponding robot device is present.
    e.g. vacuum every 3 days, multiplier=0.4 → every 3/0.4 = 7.5 days
    """
    freq = float(task.default_frequency_days)
    if (
        task.robot_frequency_multiplier
        and not task.is_robot_variant
        and task.device_flag is None
    ):
        # Check if any robot device relevant to this task is present
        # We identify robot-paired tasks by having robot_frequency_multiplier set
        if household.has_robot_vacuum or household.has_robot_mop:
            freq = freq / task.robot_frequency_multiplier
    return freq


def _robot_score(task: TaskTemplate, session: DailySession, household: Household) -> float:
    """Apply robot preference bonuses/maluses at energy=low."""
    if session.energy_level != "low":
        return 0.0

    # Robot variant bonus
    if task.is_robot_variant and task.device_flag:
        attr = DEVICE_FLAG_TO_HOUSEHOLD_ATTR.get(task.device_flag)
        if attr and getattr(household, attr, False):
            return ROBOT_LOW_ENERGY_BONUS

    # Manual task malus when robot is present and energy is low
    if (
        not task.is_robot_variant
        and task.robot_frequency_multiplier is not None
    ):
        # Check if corresponding robot device exists
        if household.has_robot_vacuum or household.has_robot_mop:
            return -ROBOT_MANUAL_LOW_ENERGY_MALUS

    return 0.0


def _is_manual_suppressed(
    task: TaskTemplate,
    household: Household,
    robot_run_task_ids: set[int],
) -> bool:
    """
    Suppress manual floor task if corresponding robot ran within ROBOT_RECENT_RUN_HOURS.
    robot_run_task_ids: set of task_template_ids where robot variant was completed recently.

    v1.0 note: Suppression is matched by room_type — any manual task with
    robot_frequency_multiplier in a room where a robot ran is suppressed.
    This works correctly for the catalog structure (vacuum/mop tasks per room),
    but could theoretically suppress unrelated tasks sharing a room_type.
    Refine to category-level matching in a future round if needed.
    """
    if task.is_robot_variant:
        return False
    if task.robot_frequency_multiplier is None:
        return False
    # This is a manual task paired with a robot variant
    # Check if the robot variant for this "floor zone" was completed recently
    # We detect pairing by room_type (both manual and robot share the same room_type)
    return task.id in robot_run_task_ids


def _is_force_candidate(
    task: TaskTemplate,
    days_since_done: float,
    effective_freq: float,
    all_preferences: dict,
) -> bool:
    """Return True if task should be force-included (overdue 2x + all dislike)."""
    if days_since_done < effective_freq * UNPOPULAR_OVERDUE_MULTIPLIER:
        return False
    # Check if all residents dislike this category
    return _all_dislike_raw(task.category, all_preferences)


def _seasonality(task: TaskTemplate, season: str) -> float:
    if task.category == "garden" and season in ("spring", "summer"):
        return SEASONALITY_BONUS
    if task.category == "cleaning" and season in ("autumn", "winter"):
        return SEASONALITY_BONUS
    return 0.0


def _imbalance_bonus(
    task_id: int,
    resident_id: int,
    all_resident_ids: list[int],
    my_last_done: dict,
    last_done_map: dict,
) -> float:
    """
    Award bonus if this task was always done by others (imbalance detection).
    Simple heuristic: task appears in last_done_map but not in my_last_done.
    """
    if task_id in last_done_map and task_id not in my_last_done:
        return IMBALANCE_BONUS
    return 0.0


def _all_dislike(category: str, all_preferences: dict, all_resident_ids: list[int]) -> bool:
    """Return True if every resident has explicitly disliked this category."""
    return _all_dislike_raw(category, all_preferences)


def _all_dislike_raw(category: str, all_preferences: dict) -> bool:
    if not all_preferences:
        return False
    for resident_id, prefs in all_preferences.items():
        pref = prefs.get(category)
        if pref != "dislike":
            return False
    return True


# ---------------------------------------------------------------------------
# Context loaders
# ---------------------------------------------------------------------------

def _load_preferences(resident_id: int, db: Session) -> dict:
    """Returns { category: preference_value } for a resident."""
    prefs = (
        db.query(ResidentPreference)
        .filter(ResidentPreference.resident_id == resident_id)
        .all()
    )
    return {p.task_category: p.preference.value for p in prefs}


def _load_all_preferences(resident_ids: list[int], db: Session) -> dict:
    """Returns { resident_id: { category: preference } } for all residents."""
    result: dict = {}
    for rid in resident_ids:
        result[rid] = _load_preferences(rid, db)
    return result


def _household_resident_ids(household_id: int, db: Session) -> list[int]:
    residents = db.query(Resident).filter(Resident.household_id == household_id).all()
    return [r.id for r in residents]


def _recent_completions(resident_ids: list[int], db: Session) -> list[TaskAssignment]:
    """All completed assignments for the household (for history-based scoring)."""
    return (
        db.query(TaskAssignment)
        .filter(
            TaskAssignment.resident_id.in_(resident_ids),
            TaskAssignment.status == "completed",
            TaskAssignment.completed_at.isnot(None),
        )
        .order_by(TaskAssignment.completed_at.desc())
        .limit(500)
        .all()
    )


def _rejection_map(resident_id: int, db: Session, now: datetime) -> dict:
    """
    Returns { task_template_id: { days_ago: float } } for skipped tasks in last 7 days.
    """
    cutoff = now - timedelta(days=7)
    skipped = (
        db.query(TaskAssignment)
        .filter(
            TaskAssignment.resident_id == resident_id,
            TaskAssignment.status == "skipped",
            TaskAssignment.suggested_at >= cutoff,
        )
        .all()
    )
    result: dict = {}
    for a in skipped:
        days_ago = (now - a.suggested_at).total_seconds() / 86400
        tid = a.task_template_id
        # Keep most recent rejection
        if tid not in result or days_ago < result[tid]["days_ago"]:
            result[tid] = {"days_ago": days_ago}
    return result


def _recently_run_robot_tasks(db: Session, now: datetime) -> set[int]:
    """
    Returns set of task_template_ids for robot tasks completed within ROBOT_RECENT_RUN_HOURS.
    Used to suppress paired manual tasks.
    """
    cutoff = now - timedelta(hours=ROBOT_RECENT_RUN_HOURS)
    recent = (
        db.query(TaskAssignment)
        .join(TaskTemplate, TaskAssignment.task_template_id == TaskTemplate.id)
        .filter(
            TaskAssignment.status == "completed",
            TaskAssignment.completed_at >= cutoff,
            TaskTemplate.is_robot_variant == True,  # noqa: E712
        )
        .all()
    )
    # Collect room_types of recently run robot tasks
    robot_room_types: set[str] = set()
    for a in recent:
        robot_room_types.add(a.task_template.room_type)

    # Now find manual floor tasks in those same room types that have a multiplier
    if not robot_room_types:
        return set()

    manual_tasks = (
        db.query(TaskTemplate)
        .filter(
            TaskTemplate.is_robot_variant == False,  # noqa: E712
            TaskTemplate.robot_frequency_multiplier.isnot(None),
            TaskTemplate.room_type.in_(robot_room_types),
        )
        .all()
    )
    return {t.id for t in manual_tasks}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _season(month: int) -> str:
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _household_flag_ok(task: TaskTemplate, household: Household) -> bool:
    if task.household_flag is None:
        return True
    attr = HOUSEHOLD_FLAG_TO_ATTR.get(task.household_flag)
    return bool(attr and getattr(household, attr, False))


def _device_flag_ok(task: TaskTemplate, household: Household) -> bool:
    if task.device_flag is None:
        return True
    attr = DEVICE_FLAG_TO_HOUSEHOLD_ATTR.get(task.device_flag)
    return bool(attr and getattr(household, attr, False))


# ---------------------------------------------------------------------------
# R8: Calendar alert boost helper
# ---------------------------------------------------------------------------

def _calendar_boost(task: TaskTemplate, alert_level: Optional[object]) -> float:
    """
    Apply a scoring boost based on the active calendar alert level.
    Tier-1 rooms (hallway, bathroom, kitchen, living) get higher boosts.
    No boost for non-visible rooms on early/medium; full boost on urgent.
    Returns the boost value to add to the task score.
    """
    if alert_level is None:
        return 0.0

    alert_str = alert_level.value if hasattr(alert_level, "value") else str(alert_level)
    is_visible = task.room_type in CALENDAR_TIER1_ROOMS

    if alert_str == "early":
        # Boost all shared/visible room tasks
        return float(CALENDAR_BOOST_EARLY) if is_visible else 0.0
    elif alert_str == "medium":
        return float(CALENDAR_BOOST_MEDIUM) if is_visible else 0.0
    elif alert_str == "urgent":
        return float(CALENDAR_BOOST_URGENT) if is_visible else 0.0
    # panic → no score boost; prompt handled at result level
    return 0.0

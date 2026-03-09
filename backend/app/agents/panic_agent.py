"""
panic_agent.py — Rule-based Panic Mode plan generator.

Generates a prioritized, time-boxed cleaning plan for unexpected guest arrival.
No AI — purely deterministic prioritization based on room visibility tiers.

Boundaries:
  - Ignores energy level and resident preferences
  - Panic tasks earn normal points via the Gamification Agent (no special handling)
  - Daily task engine continues to run in parallel (no lock)

Public API:
    generate_panic_plan(panic_session, db) -> PanicPlan
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.panic_session import PanicSession
from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident

# ---------------------------------------------------------------------------
# Room priority tiers — configurable constants
# ---------------------------------------------------------------------------

# Tier 1: shared + visible — guests will almost certainly see these
TIER_1_ROOMS = ["hallway", "bathroom", "kitchen", "living"]

# Tier 2: less visible but common areas
TIER_2_ROOMS = ["other"]  # covers dining, staircase, etc. mapped to "other"

# Tier 3: private rooms — only if time budget allows
TIER_3_ROOMS = ["bedroom", "childrens_room", "garden"]

ROOM_TIER: dict[str, int] = {}
for _r in TIER_1_ROOMS:
    ROOM_TIER[_r] = 1
for _r in TIER_2_ROOMS:
    ROOM_TIER[_r] = 2
for _r in TIER_3_ROOMS:
    ROOM_TIER[_r] = 3

# Visual impact ranking within tier (lower = higher impact = appears first)
# Categories that have the most visible effect are prioritised
VISUAL_IMPACT_ORDER: dict[str, int] = {
    "cleaning":     1,   # wipe surfaces, sanitise
    "tidying":      2,   # declutter visible areas
    "decluttering": 3,
    "laundry":      4,
    "maintenance":  5,
    "garden":       6,
    "other":        7,
}

# Maximum allowed time buffer over the requested duration (10%)
TIME_BUFFER_FACTOR = 1.10

# How many hours after a task was completed counts as "done recently" (suppress)
RECENT_COMPLETION_HOURS = 24


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class PanicTaskItem:
    assignment_id: int
    task_id: int
    task_name: str
    room_type: str
    category: str
    duration_minutes: int
    priority_tier: int
    assigned_resident_id: int
    assigned_resident_name: str
    instruction: str              # human-readable template string


@dataclass
class ResidentPlan:
    resident_id: int
    resident_name: str
    tasks: list[PanicTaskItem] = field(default_factory=list)
    total_minutes: int = 0


@dataclass
class PanicPlan:
    panic_session_id: int
    available_minutes: int
    total_planned_minutes: int
    order_note: str
    residents: list[ResidentPlan] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_panic_plan(panic_session: PanicSession, db: Session) -> PanicPlan:
    """
    Build a prioritized, time-boxed plan for the given panic session.
    Creates TaskAssignment records for each planned task.
    Returns a PanicPlan with per-resident task lists.
    """
    available_resident_ids = panic_session.get_resident_ids()
    max_minutes = panic_session.available_minutes
    budget_with_buffer = max_minutes * TIME_BUFFER_FACTOR
    now = datetime.now(timezone.utc)

    # Load residents
    residents = [db.get(Resident, rid) for rid in available_resident_ids]
    residents = [r for r in residents if r is not None]
    if not residents:
        return PanicPlan(
            panic_session_id=panic_session.id,
            available_minutes=max_minutes,
            total_planned_minutes=0,
            order_note="No available residents found.",
        )

    # Determine household from activating resident
    activating_resident = db.get(Resident, panic_session.activated_by_resident_id)
    household_id = activating_resident.household_id

    # Fetch all active tasks, filter, and sort by priority
    all_tasks = db.query(TaskTemplate).filter(TaskTemplate.is_active == True).all()  # noqa: E712

    # Filter: not completed in last 24 hours (household-wide)
    recent_cutoff = now - timedelta(hours=RECENT_COMPLETION_HOURS)
    recently_done_ids = _recently_completed_task_ids(db, household_id, recent_cutoff)

    eligible = [t for t in all_tasks if t.id not in recently_done_ids]

    # Sort: tier → visual impact → duration (shorter first within same priority)
    eligible.sort(key=lambda t: (
        ROOM_TIER.get(t.room_type, 2),
        VISUAL_IMPACT_ORDER.get(t.category, 7),
        t.default_duration_minutes,
    ))

    # Fill time budget with round-robin resident assignment
    resident_plans: dict[int, ResidentPlan] = {
        r.id: ResidentPlan(resident_id=r.id, resident_name=r.display_name)
        for r in residents
    }

    total_minutes = 0
    resident_cycle = list(residents)
    cycle_index = 0

    assignments_to_create: list[tuple[TaskTemplate, int]] = []  # (task, resident_id)

    for task in eligible:
        if total_minutes >= budget_with_buffer:
            break

        duration = task.default_duration_minutes
        if total_minutes + duration > budget_with_buffer:
            # Would exceed budget — skip unless we have nothing yet
            if total_minutes == 0:
                pass  # must include at least one task
            else:
                continue

        # Assign to next resident in round-robin
        assigned_resident = resident_cycle[cycle_index % len(resident_cycle)]
        cycle_index += 1
        total_minutes += duration
        assignments_to_create.append((task, assigned_resident.id))

    # Create TaskAssignment records in DB
    created_items: list[PanicTaskItem] = []
    for task, resident_id in assignments_to_create:
        resident = db.get(Resident, resident_id)
        assignment = TaskAssignment(
            session_id=None,
            panic_session_id=panic_session.id,
            resident_id=resident_id,
            task_template_id=task.id,
            status="suggested",
            score=None,
            suggested_at=now,
            is_forced=False,
        )
        db.add(assignment)
        db.flush()  # get assignment.id

        tier = ROOM_TIER.get(task.room_type, 2)
        instruction = _build_instruction(task)

        item = PanicTaskItem(
            assignment_id=assignment.id,
            task_id=task.id,
            task_name=task.name,
            room_type=task.room_type,
            category=task.category,
            duration_minutes=task.default_duration_minutes,
            priority_tier=tier,
            assigned_resident_id=resident_id,
            assigned_resident_name=resident.display_name,
            instruction=instruction,
        )
        created_items.append(item)
        resident_plans[resident_id].tasks.append(item)
        resident_plans[resident_id].total_minutes += task.default_duration_minutes

    db.commit()

    order_note = _build_order_note(created_items)

    return PanicPlan(
        panic_session_id=panic_session.id,
        available_minutes=max_minutes,
        total_planned_minutes=total_minutes,
        order_note=order_note,
        residents=list(resident_plans.values()),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _recently_completed_task_ids(
    db: Session, household_id: int, since: datetime
) -> set[int]:
    """
    Return task_template_ids completed by any household resident since `since`.
    Used to suppress tasks already done within the last 24 hours.
    """
    # Get all resident IDs in household
    residents = (
        db.query(Resident)
        .filter(Resident.household_id == household_id)
        .all()
    )
    resident_ids = [r.id for r in residents]
    if not resident_ids:
        return set()

    recent = (
        db.query(TaskAssignment.task_template_id)
        .filter(
            TaskAssignment.resident_id.in_(resident_ids),
            TaskAssignment.status == "completed",
            TaskAssignment.completed_at >= since,
        )
        .distinct()
        .all()
    )
    return {row[0] for row in recent}


def _build_instruction(task: TaskTemplate) -> str:
    """
    Generate a human-readable instruction string for a task.
    Uses simple template strings — no AI.
    """
    room = task.room_type.replace("_", " ").title()
    category = task.category

    templates: dict[str, str] = {
        "cleaning":     f"Clean and wipe all surfaces in the {room}.",
        "tidying":      f"Tidy up and declutter the {room} — put items in their place.",
        "decluttering": f"Quickly remove any visible clutter from the {room}.",
        "laundry":      f"Handle laundry tasks: collect, sort, or fold items in the {room}.",
        "maintenance":  f"Check and address any maintenance issues visible in the {room}.",
        "garden":       f"Make the garden / outdoor area presentable — sweep and tidy.",
        "other":        f"Complete the task '{task.name}' in the {room}.",
    }
    return templates.get(category, f"Complete '{task.name}' in the {room}.")


def _build_order_note(items: list[PanicTaskItem]) -> str:
    """
    Build a human-readable order recommendation note.
    Highlights tier-1 rooms that guests will likely see first.
    """
    tier1_rooms = sorted(
        {item.room_type for item in items if item.priority_tier == 1},
        key=lambda r: TIER_1_ROOMS.index(r) if r in TIER_1_ROOMS else 99,
    )

    if not tier1_rooms:
        return "Work through tasks in the order listed — all areas are covered."

    room_labels = [r.replace("_", " ").title() for r in tier1_rooms]
    if len(room_labels) == 1:
        first_rooms = room_labels[0]
    elif len(room_labels) == 2:
        first_rooms = " and ".join(room_labels)
    else:
        first_rooms = ", ".join(room_labels[:-1]) + f", and {room_labels[-1]}"

    return (
        f"Start with {first_rooms} — these are the areas guests will notice first. "
        "Work through the list in order; lower-priority rooms can be skipped if time runs out."
    )

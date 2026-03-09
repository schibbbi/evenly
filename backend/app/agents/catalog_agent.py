"""
catalog_agent.py — Task catalog generation (AI-powered or static fallback).

Primary path: calls Claude API (claude-sonnet) once at setup to generate a
comprehensive household task catalog.

Fallback path: if CLAUDE_API_KEY is not set, seeds the built-in default catalog
from default_catalog.py instead. This allows the app to work fully offline and
without an API key on first docker-compose up.

Usage (via API):
    POST /catalog/generate   →  triggers generate_catalog(db, household_id)

Direct seeding (called from seed.py):
    seed_default_catalog(db)  →  inserts DEFAULT_TASKS, idempotent

Environment:
    CLAUDE_API_KEY — Anthropic API key (optional; falls back to static catalog)
"""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.task_template import TaskTemplate
from app.agents.default_catalog import DEFAULT_TASKS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

CATALOG_PROMPT = """
You are a household management expert. Generate a comprehensive task catalog for a modern household.

Return a JSON array of task objects. Each task must have exactly these fields:
- name: string (concise, action-oriented, e.g. "Wipe kitchen cabinet fronts")
- description: string (1-2 sentences explaining what to do and why)
- room_type: one of: kitchen, bathroom, bedroom, living, hallway, childrens_room, garden, other
- category: one of: cleaning, tidying, laundry, garden, decluttering, maintenance, other
- default_duration_minutes: integer (5, 10, 15, 20, 30, 45, 60, 90, 120)
- default_frequency_days: integer (1=daily, 2, 3, 7=weekly, 14, 30=monthly, 60, 90=quarterly, 180, 365=yearly)
- energy_level: one of: low, medium, high
- household_flag: one of: "children", "cats", "dogs", or null (null = always shown)
- device_flag: one of: "robot_vacuum", "robot_mop", "dishwasher", "washer", "dryer", "window_cleaner", "steam_cleaner", "robot_mower", "irrigation", or null
- is_robot_variant: boolean (true only for robot-operated task variants)
- robot_frequency_multiplier: float or null (e.g. 0.4 means 60% less often when device present; null for non-paired tasks)

Requirements:
1. GRANULARITY: Not "clean kitchen" but specific tasks like "Descale kettle", "Clean oven interior", "Wipe hob", "Clean sink strainer", "Wipe splashback"
2. ROOM COVERAGE: Minimum 12 base tasks per room type (kitchen, bathroom, bedroom, living, hallway, other)
3. GARDEN: Minimum 8 garden tasks, with device variants where applicable
4. ROBOT PAIRS: For every manual floor task (vacuuming, mopping), create a PAIRED robot variant:
   - Manual: device_flag=null, is_robot_variant=false, robot_frequency_multiplier=0.4 (e.g. "Vacuum living room manually")
   - Robot variant: device_flag="robot_vacuum" or "robot_mop", is_robot_variant=true, robot_frequency_multiplier=null (e.g. "Run robot vacuum in living room")
   - Apply this pattern for: kitchen, bathroom, bedroom, living room, hallway floors
5. DISHWASHER: Create both "Hand wash dishes" (device_flag=null) and "Empty dishwasher" (device_flag="dishwasher")
6. WASHER/DRYER: Tasks like "Do a laundry load" (device_flag="washer"), "Transfer laundry to dryer" (device_flag="dryer")
7. WINDOW CLEANER: Tasks like "Clean windows with electric cleaner" (device_flag="window_cleaner")
8. STEAM CLEANER: Tasks like "Steam clean bathroom tiles" (device_flag="steam_cleaner")
9. ROBOT MOWER: "Run robot mower" (device_flag="robot_mower", is_robot_variant=true)
10. IRRIGATION: "Check irrigation system" (device_flag="irrigation")
11. FLAGGED TASKS (household_flag set, is_active=false by default):
    - children: min 6 tasks (e.g. "Sanitize baby changing mat", "Wash children's bedding", "Clean highchair", "Sort toy storage", "Disinfect teething toys", "Clean play mat")
    - cats: min 6 tasks (e.g. "Clean litter box", "Wash food bowls", "Vacuum cat hair from furniture", "Clean scratch post", "Wash cat bed", "Check fur for parasites")
    - dogs: min 6 tasks (e.g. "Wash dog bed", "Clean food/water bowls", "Vacuum dog hair from floors", "Wipe paw prints from floor", "Clean dog toys", "Check dog coat for parasites")
12. TOTAL: 120+ tasks minimum

Do not include any markdown, explanation, or wrapper. Return ONLY the raw JSON array starting with [ and ending with ].
"""

# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def _insert_tasks(db: Session, tasks_data: list) -> int:
    """Insert a list of task dicts into TaskTemplate. Returns count inserted."""
    inserted = 0
    now = datetime.now(timezone.utc)
    for item in tasks_data:
        # Flagged tasks (household_flag or device_flag) start inactive.
        # They are activated when the user confirms the household configuration.
        has_flag = item.get("household_flag") is not None or item.get("device_flag") is not None
        is_active_default = not has_flag

        task = TaskTemplate(
            name=item["name"],
            description=item.get("description", ""),
            room_type=item["room_type"],
            category=item["category"],
            default_duration_minutes=int(item.get("default_duration_minutes", 15)),
            default_frequency_days=int(item.get("default_frequency_days", 7)),
            energy_level=item.get("energy_level", "medium"),
            household_flag=item.get("household_flag"),
            device_flag=item.get("device_flag"),
            is_robot_variant=bool(item.get("is_robot_variant", False)),
            robot_frequency_multiplier=item.get("robot_frequency_multiplier"),
            is_active=is_active_default,
            is_custom=False,
            created_at=now,
        )
        db.add(task)
        inserted += 1
    return inserted


def seed_default_catalog(db: Session) -> dict:
    """
    Insert the built-in DEFAULT_TASKS catalog into the DB.

    Idempotent — skips silently if non-custom tasks already exist.
    Called from seed.py on first startup (no API key required).
    """
    existing_count = (
        db.query(TaskTemplate)
        .filter(TaskTemplate.is_custom == False)  # noqa: E712
        .count()
    )
    if existing_count > 0:
        logger.info("Catalog already exists (%d tasks). Skipping default seed.", existing_count)
        return _build_summary(db, skipped=True)

    inserted = _insert_tasks(db, DEFAULT_TASKS)
    db.commit()
    logger.info("Default catalog seeded: %d tasks inserted.", inserted)
    print(
        f"\n✓ Default task catalog seeded: {inserted} tasks.\n"
        "  Activate device/flag tasks in household settings.\n"
        "  Add custom tasks via: POST /catalog\n"
    )
    return _build_summary(db, skipped=False)


def generate_catalog(db: Session, household_id: int) -> dict:
    """
    Generate the task catalog via Claude API (or fall back to the static default).

    Returns a summary dict:
    {
        "total": int,
        "by_room": { room_type: count },
        "by_flag": { flag: count },
        "by_device_flag": { device_flag: count },
        "skipped": bool  # True if catalog already existed
    }
    """
    # Idempotency check — skip if any non-custom tasks exist
    # v1.0: single household assumed — catalog is shared/global across the instance
    existing_count = (
        db.query(TaskTemplate)
        .filter(TaskTemplate.is_custom == False)  # noqa: E712
        .count()
    )
    if existing_count > 0:
        logger.info("Catalog already exists (%d tasks). Skipping generation.", existing_count)
        return _build_summary(db, skipped=True)

    # Load API key — if absent, fall back to static default catalog
    api_key = os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        logger.info("CLAUDE_API_KEY not set — seeding built-in default catalog instead.")
        return seed_default_catalog(db)

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — seeding default catalog instead.")
        return seed_default_catalog(db)

    client = anthropic.Anthropic(api_key=api_key)

    logger.info("Calling Claude API to generate task catalog...")
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=8192,
        messages=[{"role": "user", "content": CATALOG_PROMPT}],
    )

    raw = message.content[0].text.strip()

    # Parse JSON — Claude returns raw array
    try:
        tasks_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Claude response as JSON: %s", exc)
        logger.debug("Raw response (first 500 chars): %s", raw[:500])
        logger.warning("Falling back to built-in default catalog.")
        return seed_default_catalog(db)

    if not isinstance(tasks_data, list):
        logger.warning("Unexpected Claude response type — falling back to default catalog.")
        return seed_default_catalog(db)

    inserted = _insert_tasks(db, tasks_data)
    db.commit()
    logger.info(
        "Catalog generated via Claude API: %d tasks inserted.",
        inserted,
    )
    print(
        f"\n✓ Catalog generated: {inserted} tasks inserted into the database.\n"
        "  Review the full catalog at: GET /catalog/export\n"
        "  Add missing tasks via:       POST /catalog\n"
        "  Activate device tasks in household settings after confirming devices.\n"
    )
    return _build_summary(db, skipped=False)


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def _build_summary(db: Session, skipped: bool = False) -> dict:
    tasks = db.query(TaskTemplate).all()

    by_room: dict = {}
    by_flag: dict = {}
    by_device_flag: dict = {}

    for t in tasks:
        by_room[t.room_type] = by_room.get(t.room_type, 0) + 1
        if t.household_flag:
            by_flag[t.household_flag] = by_flag.get(t.household_flag, 0) + 1
        if t.device_flag:
            by_device_flag[t.device_flag] = by_device_flag.get(t.device_flag, 0) + 1

    return {
        "total": len(tasks),
        "by_room": by_room,
        "by_household_flag": by_flag,
        "by_device_flag": by_device_flag,
        "skipped": skipped,
    }

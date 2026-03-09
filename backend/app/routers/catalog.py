"""
catalog router — Task catalog management endpoints.

Endpoints:
    POST /catalog/generate          — trigger one-time AI catalog generation (admin)
    GET  /catalog                   — list tasks, with household-flag filtering
    GET  /catalog/export            — full grouped catalog for human review (admin/edit)
    PUT  /catalog/{id}              — edit any task field (admin/edit)
    POST /catalog                   — create a custom task manually (admin/edit)
    DELETE /catalog/{id}            — delete custom task / deactivate pre-generated task (admin/edit)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_active_resident, require_role
from app.agents.catalog_agent import generate_catalog
from app.models.task_template import TaskTemplate
from app.models.household import Household
from app.models.resident import Resident
from app.models.enums import (
    EnergyLevelEnum,
    CategoryEnum,
    HouseholdFlagEnum,
    DeviceFlagEnum,
    RoomTypeEnum,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])

# ---------------------------------------------------------------------------
# Household flag → Household field mapping
# ---------------------------------------------------------------------------

HOUSEHOLD_FLAG_MAP = {
    "children": "has_children",
    "cats": "has_cats",
    "dogs": "has_dogs",
}

DEVICE_FLAG_MAP = {
    "robot_vacuum": "has_robot_vacuum",
    "robot_mop": "has_robot_mop",
    "dishwasher": "has_dishwasher",
    "washer": "has_washer",
    "dryer": "has_dryer",
    "window_cleaner": "has_window_cleaner",
    "steam_cleaner": "has_steam_cleaner",
    "robot_mower": "has_robot_mower",
    "irrigation": "has_irrigation",
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TaskTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    room_type: str
    category: str
    default_duration_minutes: int
    default_frequency_days: int
    energy_level: str
    household_flag: Optional[str]
    device_flag: Optional[str]
    is_robot_variant: bool
    robot_frequency_multiplier: Optional[float]
    is_active: bool
    is_custom: bool
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, t: TaskTemplate) -> "TaskTemplateResponse":
        return cls(
            id=t.id,
            name=t.name,
            description=t.description,
            room_type=t.room_type,
            category=t.category,
            default_duration_minutes=t.default_duration_minutes,
            default_frequency_days=t.default_frequency_days,
            energy_level=t.energy_level,
            household_flag=t.household_flag,
            device_flag=t.device_flag,
            is_robot_variant=t.is_robot_variant,
            robot_frequency_multiplier=t.robot_frequency_multiplier,
            is_active=t.is_active,
            is_custom=t.is_custom,
            created_at=t.created_at.isoformat(),
        )


class TaskTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    room_type: RoomTypeEnum
    category: CategoryEnum
    default_duration_minutes: int = Field(default=15, ge=1, le=480)
    default_frequency_days: int = Field(default=7, ge=1, le=365)
    energy_level: EnergyLevelEnum = EnergyLevelEnum.medium
    household_flag: Optional[HouseholdFlagEnum] = None
    device_flag: Optional[DeviceFlagEnum] = None
    is_robot_variant: bool = False
    robot_frequency_multiplier: Optional[float] = Field(default=None, ge=0.01, le=1.0)
    is_active: bool = True


class TaskTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    room_type: Optional[RoomTypeEnum] = None
    category: Optional[CategoryEnum] = None
    default_duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    default_frequency_days: Optional[int] = Field(None, ge=1, le=365)
    energy_level: Optional[EnergyLevelEnum] = None
    household_flag: Optional[HouseholdFlagEnum] = None
    device_flag: Optional[DeviceFlagEnum] = None
    is_robot_variant: Optional[bool] = None
    robot_frequency_multiplier: Optional[float] = Field(None, ge=0.01, le=1.0)
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_task_or_404(task_id: int, db: Session) -> TaskTemplate:
    task = db.get(TaskTemplate, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _get_household_or_404(household_id: int, db: Session) -> Household:
    h = db.get(Household, household_id)
    if not h:
        raise HTTPException(status_code=404, detail="Household not found")
    return h


def _flag_visible_for_household(task: TaskTemplate, household: Household) -> bool:
    """
    Return True if the task should be visible given the household's flags.
    - household_flag: check composition flags
    - device_flag: check appliance flags
    Both must pass.
    """
    if task.household_flag is not None:
        attr = HOUSEHOLD_FLAG_MAP.get(task.household_flag)
        if attr and not getattr(household, attr, False):
            return False

    if task.device_flag is not None:
        attr = DEVICE_FLAG_MAP.get(task.device_flag)
        if attr and not getattr(household, attr, False):
            return False

    return True


# ---------------------------------------------------------------------------
# POST /catalog/generate
# ---------------------------------------------------------------------------

@router.post("/generate", status_code=200)
def trigger_generate(
    household_id: int = Query(..., description="Household to generate catalog for"),
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Trigger one-time AI catalog generation via Claude API.
    Idempotent: returns summary without re-generating if catalog already exists.
    """
    _get_household_or_404(household_id, db)
    summary = generate_catalog(db, household_id)
    return summary


# ---------------------------------------------------------------------------
# GET /catalog
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TaskTemplateResponse])
def list_catalog(
    household_id: int = Query(..., description="Filter visibility by household flags"),
    room_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    household_flag: Optional[str] = Query(None),
    include_flagged: bool = Query(
        False,
        description="If true, return all tasks regardless of household flags (for settings screen)"
    ),
    db: Session = Depends(get_db),
):
    """
    List catalog tasks. Automatically hides tasks whose household_flag or device_flag
    is not satisfied by the household config — unless include_flagged=true.
    Public endpoint (no auth required — used by suggestion engine and UI).
    """
    household = _get_household_or_404(household_id, db)

    query = db.query(TaskTemplate)

    if room_type is not None:
        query = query.filter(TaskTemplate.room_type == room_type)
    if category is not None:
        query = query.filter(TaskTemplate.category == category)
    if is_active is not None:
        query = query.filter(TaskTemplate.is_active == is_active)
    if household_flag is not None:
        query = query.filter(TaskTemplate.household_flag == household_flag)

    tasks = query.all()

    if not include_flagged:
        tasks = [t for t in tasks if _flag_visible_for_household(t, household)]

    return [TaskTemplateResponse.from_orm_model(t) for t in tasks]


# ---------------------------------------------------------------------------
# GET /catalog/export
# ---------------------------------------------------------------------------

@router.get("/export")
def export_catalog(
    _editor: Resident = Depends(require_role("edit")),
    db: Session = Depends(get_db),
):
    """
    Export the full catalog as structured JSON grouped by room → category → household_flag.
    Used for human review after generation.
    """
    tasks = db.query(TaskTemplate).order_by(
        TaskTemplate.room_type,
        TaskTemplate.category,
        TaskTemplate.household_flag,
        TaskTemplate.name,
    ).all()

    # Build nested structure: room_type → category → flag → tasks
    export: dict = {}
    for t in tasks:
        room = t.room_type
        cat = t.category
        flag = t.household_flag or "_base"

        if room not in export:
            export[room] = {}
        if cat not in export[room]:
            export[room][cat] = {}
        if flag not in export[room][cat]:
            export[room][cat][flag] = []

        export[room][cat][flag].append({
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "duration_minutes": t.default_duration_minutes,
            "frequency_days": t.default_frequency_days,
            "energy_level": t.energy_level,
            "household_flag": t.household_flag,
            "device_flag": t.device_flag,
            "is_robot_variant": t.is_robot_variant,
            "robot_frequency_multiplier": t.robot_frequency_multiplier,
            "is_active": t.is_active,
            "is_custom": t.is_custom,
        })

    total = len(tasks)
    return {
        "total_tasks": total,
        "catalog": export,
        "review_note": (
            "Review all tasks below. Activate device-specific tasks in household settings. "
            "Add missing tasks via POST /catalog."
        ),
    }


# ---------------------------------------------------------------------------
# POST /catalog
# ---------------------------------------------------------------------------

@router.post("", response_model=TaskTemplateResponse, status_code=201)
def create_custom_task(
    payload: TaskTemplateCreate,
    _editor: Resident = Depends(require_role("edit")),
    db: Session = Depends(get_db),
):
    """Create a custom task manually. Marked as is_custom=True."""
    task = TaskTemplate(
        name=payload.name,
        description=payload.description,
        room_type=payload.room_type.value,
        category=payload.category.value,
        default_duration_minutes=payload.default_duration_minutes,
        default_frequency_days=payload.default_frequency_days,
        energy_level=payload.energy_level.value,
        household_flag=payload.household_flag.value if payload.household_flag else None,
        device_flag=payload.device_flag.value if payload.device_flag else None,
        is_robot_variant=payload.is_robot_variant,
        robot_frequency_multiplier=payload.robot_frequency_multiplier,
        is_active=payload.is_active,
        is_custom=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return TaskTemplateResponse.from_orm_model(task)


# ---------------------------------------------------------------------------
# PUT /catalog/{id}
# ---------------------------------------------------------------------------

@router.put("/{task_id}", response_model=TaskTemplateResponse)
def update_task(
    task_id: int,
    payload: TaskTemplateUpdate,
    _editor: Resident = Depends(require_role("edit")),
    db: Session = Depends(get_db),
):
    """Edit any field of a task (duration, frequency, energy level, name, active status)."""
    task = _get_task_or_404(task_id, db)

    if payload.name is not None:
        task.name = payload.name
    if payload.description is not None:
        task.description = payload.description
    if payload.room_type is not None:
        task.room_type = payload.room_type.value
    if payload.category is not None:
        task.category = payload.category.value
    if payload.default_duration_minutes is not None:
        task.default_duration_minutes = payload.default_duration_minutes
    if payload.default_frequency_days is not None:
        task.default_frequency_days = payload.default_frequency_days
    if payload.energy_level is not None:
        task.energy_level = payload.energy_level.value
    if "household_flag" in payload.model_fields_set:
        task.household_flag = payload.household_flag.value if payload.household_flag else None
    if "device_flag" in payload.model_fields_set:
        task.device_flag = payload.device_flag.value if payload.device_flag else None
    if payload.is_robot_variant is not None:
        task.is_robot_variant = payload.is_robot_variant
    if "robot_frequency_multiplier" in payload.model_fields_set:
        task.robot_frequency_multiplier = payload.robot_frequency_multiplier
    if payload.is_active is not None:
        task.is_active = payload.is_active

    db.commit()
    db.refresh(task)
    return TaskTemplateResponse.from_orm_model(task)


# ---------------------------------------------------------------------------
# DELETE /catalog/{id}
# ---------------------------------------------------------------------------

@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Delete a custom task (is_custom=True) permanently.
    Pre-generated tasks (is_custom=False) are only deactivated, not deleted.
    """
    task = _get_task_or_404(task_id, db)

    if task.is_custom:
        db.delete(task)
    else:
        # Deactivate only — preserves history references in R5+
        task.is_active = False

    db.commit()
    return None

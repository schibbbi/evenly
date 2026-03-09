"""
panic router — Panic Mode activation and management.

Endpoints:
    POST /panic                   — activate panic mode, returns prioritized plan
    GET  /panic/{id}              — get panic session details + progress
    POST /panic/{id}/complete     — mark entire session as done (completes all remaining tasks)

Individual task completion is handled by the existing assignments router:
    POST /assignments/{id}/complete — works identically for panic assignments
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.agents.panic_agent import (
    generate_panic_plan,
    PanicPlan,
    PanicTaskItem,
    ResidentPlan,
    ROOM_TIER,
    _build_instruction,
)
from app.agents.history_agent import record_completion
from app.agents.gamification_agent import award_task_points
from app.models.panic_session import PanicSession
from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident

router = APIRouter(prefix="/panic", tags=["panic"])

# Valid duration options (minutes)
VALID_DURATIONS = {120, 180, 240}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PanicActivateRequest(BaseModel):
    available_minutes: int = Field(
        ...,
        description="Total minutes available. Must be 120, 180, or 240.",
    )
    available_resident_ids: list[int] = Field(
        ...,
        min_length=1,
        description="IDs of residents who are available to help. At least one required.",
    )


class PanicTaskResponse(BaseModel):
    assignment_id: int
    task_id: int
    task_name: str
    room_type: str
    category: str
    duration_minutes: int
    priority_tier: int
    assigned_resident_id: int
    assigned_resident_name: str
    instruction: str
    status: str = "suggested"


class ResidentPlanResponse(BaseModel):
    resident_id: int
    resident_name: str
    tasks: list[PanicTaskResponse]
    total_minutes: int


class PanicPlanResponse(BaseModel):
    panic_session_id: int
    status: str
    available_minutes: int
    total_planned_minutes: int
    order_note: str
    residents: list[ResidentPlanResponse]


class PanicProgressResponse(BaseModel):
    panic_session_id: int
    status: str
    available_minutes: int
    created_at: str
    completed_at: Optional[str]
    total_tasks: int
    completed_tasks: int
    remaining_tasks: int
    residents: list[ResidentPlanResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_panic_session_or_404(panic_session_id: int, db: Session) -> PanicSession:
    ps = db.get(PanicSession, panic_session_id)
    if not ps:
        raise HTTPException(status_code=404, detail="Panic session not found")
    return ps


def _plan_to_response(plan: PanicPlan, status: str, db: Session) -> PanicPlanResponse:
    residents_out = []
    for rplan in plan.residents:
        tasks_out = []
        for item in rplan.tasks:
            # Fetch current status from DB
            assignment = db.get(TaskAssignment, item.assignment_id)
            tasks_out.append(PanicTaskResponse(
                assignment_id=item.assignment_id,
                task_id=item.task_id,
                task_name=item.task_name,
                room_type=item.room_type,
                category=item.category,
                duration_minutes=item.duration_minutes,
                priority_tier=item.priority_tier,
                assigned_resident_id=item.assigned_resident_id,
                assigned_resident_name=item.assigned_resident_name,
                instruction=item.instruction,
                status=assignment.status if assignment else "unknown",
            ))
        residents_out.append(ResidentPlanResponse(
            resident_id=rplan.resident_id,
            resident_name=rplan.resident_name,
            tasks=tasks_out,
            total_minutes=rplan.total_minutes,
        ))

    return PanicPlanResponse(
        panic_session_id=plan.panic_session_id,
        status=status,
        available_minutes=plan.available_minutes,
        total_planned_minutes=plan.total_planned_minutes,
        order_note=plan.order_note,
        residents=residents_out,
    )


def _build_progress_response(panic_session: PanicSession, db: Session) -> PanicProgressResponse:
    """Build a progress response from a stored PanicSession."""
    assignments = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.panic_session_id == panic_session.id)
        .all()
    )

    total = len(assignments)
    completed = sum(1 for a in assignments if a.status == "completed")
    remaining = total - completed

    resident_ids = panic_session.get_resident_ids()
    resident_map: dict[int, list[PanicTaskResponse]] = {rid: [] for rid in resident_ids}

    for a in assignments:
        task = db.get(TaskTemplate, a.task_template_id)
        if task and a.resident_id in resident_map:
            resident_map[a.resident_id].append(PanicTaskResponse(
                assignment_id=a.id,
                task_id=task.id,
                task_name=task.name,
                room_type=task.room_type,
                category=task.category,
                duration_minutes=task.default_duration_minutes,
                priority_tier=ROOM_TIER.get(task.room_type, 2),
                assigned_resident_id=a.resident_id,
                assigned_resident_name=_get_display_name(a.resident_id, db),
                instruction=_build_instruction(task),
                status=a.status,
            ))

    residents_out = []
    for rid in resident_ids:
        r = db.get(Resident, rid)
        if r:
            tasks = resident_map.get(rid, [])
            residents_out.append(ResidentPlanResponse(
                resident_id=rid,
                resident_name=r.display_name,
                tasks=tasks,
                total_minutes=sum(t.duration_minutes for t in tasks),
            ))

    return PanicProgressResponse(
        panic_session_id=panic_session.id,
        status=panic_session.status,
        available_minutes=panic_session.available_minutes,
        created_at=panic_session.created_at.isoformat(),
        completed_at=panic_session.completed_at.isoformat() if panic_session.completed_at else None,
        total_tasks=total,
        completed_tasks=completed,
        remaining_tasks=remaining,
        residents=residents_out,
    )


def _get_display_name(resident_id: int, db: Session) -> str:
    r = db.get(Resident, resident_id)
    return r.display_name if r else f"Resident {resident_id}"


# ---------------------------------------------------------------------------
# POST /panic — activate Panic Mode
# ---------------------------------------------------------------------------

@router.post("", response_model=PanicPlanResponse, status_code=201)
def activate_panic(
    payload: PanicActivateRequest,
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Activate Panic Mode. Any resident can trigger this.
    Returns a prioritized, time-boxed plan distributed across the selected residents.

    available_minutes must be 120, 180, or 240.
    available_resident_ids must contain at least one resident in the same household.
    """
    # Validate duration
    if payload.available_minutes not in VALID_DURATIONS:
        raise HTTPException(
            status_code=422,
            detail=f"available_minutes must be one of {sorted(VALID_DURATIONS)}. "
                   f"Got {payload.available_minutes}.",
        )

    # Validate residents belong to caller's household
    for rid in payload.available_resident_ids:
        r = db.get(Resident, rid)
        if not r:
            raise HTTPException(
                status_code=404,
                detail=f"Resident {rid} not found.",
            )
        if r.household_id != caller.household_id:
            raise HTTPException(
                status_code=400,
                detail=f"Resident {rid} does not belong to the same household.",
            )

    now = datetime.now(timezone.utc)

    # Create PanicSession record
    panic_session = PanicSession(
        activated_by_resident_id=caller.id,
        available_minutes=payload.available_minutes,
        available_resident_ids=json.dumps(payload.available_resident_ids),
        status="active",
        created_at=now,
    )
    db.add(panic_session)
    db.commit()
    db.refresh(panic_session)

    # Generate the plan (creates TaskAssignment records)
    plan = generate_panic_plan(panic_session, db)

    return _plan_to_response(plan, "active", db)


# ---------------------------------------------------------------------------
# GET /panic/{id} — get current panic session and progress
# ---------------------------------------------------------------------------

@router.get("/{panic_session_id}", response_model=PanicProgressResponse)
def get_panic_session(
    panic_session_id: int,
    _caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Return the current state of a panic session, including task completion progress.
    Individual tasks can be completed via POST /assignments/{id}/complete.
    """
    panic_session = _get_panic_session_or_404(panic_session_id, db)
    return _build_progress_response(panic_session, db)


# ---------------------------------------------------------------------------
# POST /panic/{id}/complete — mark entire panic session as done
# ---------------------------------------------------------------------------

@router.post("/{panic_session_id}/complete", response_model=PanicProgressResponse)
def complete_panic_session(
    panic_session_id: int,
    _caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Mark the entire panic session as completed.
    Any tasks not yet individually completed are bulk-marked as completed.
    History and gamification are triggered for each uncompleted task.
    """
    panic_session = _get_panic_session_or_404(panic_session_id, db)

    if panic_session.status == "completed":
        raise HTTPException(status_code=409, detail="Panic session is already completed.")

    now = datetime.now(timezone.utc)

    # Find all non-completed assignments in this panic session
    pending_assignments = (
        db.query(TaskAssignment)
        .filter(
            TaskAssignment.panic_session_id == panic_session_id,
            TaskAssignment.status.notin_(["completed", "skipped"]),
        )
        .all()
    )

    for assignment in pending_assignments:
        assignment.status = "completed"
        assignment.completed_at = now
        if not assignment.accepted_at:
            assignment.accepted_at = now
        db.commit()
        db.refresh(assignment)

        # Trigger history and gamification for each
        try:
            record_completion(assignment, db)
        except Exception:
            pass  # Best-effort — don't fail the whole session for one task

        try:
            award_task_points(assignment, db)
        except Exception:
            pass  # Best-effort

    # Mark session complete
    panic_session.status = "completed"
    panic_session.completed_at = now
    db.commit()

    return _build_progress_response(panic_session, db)

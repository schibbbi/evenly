"""
assignments router — Task assignment lifecycle endpoints.

Endpoints:
    POST /assignments/{id}/accept    — accept a suggested task
    POST /assignments/{id}/complete  — mark task as done + trigger history + gamification agents
    POST /assignments/{id}/skip      — skip a task + trigger history agent
    POST /assignments/{id}/delegate  — delegate task to another resident (R6)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.agents.history_agent import record_completion, record_skip
from app.agents.gamification_agent import (
    award_task_points,
    complete_delegated_task,
    delegate_task,
)
from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident
from app.models.delegation_record import DelegationRecord

router = APIRouter(prefix="/assignments", tags=["assignments"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AssignmentResponse(BaseModel):
    id: int
    session_id: int
    resident_id: int
    task_template_id: int
    status: str
    score: Optional[float]
    suggested_at: str
    accepted_at: Optional[str]
    completed_at: Optional[str]
    is_forced: bool
    points_awarded: Optional[int]
    # R5 additions
    rejection_prompt: Optional[str] = None   # non-None when resident should be prompted
    # R6 additions
    streak_after: Optional[int] = None
    vouchers_earned: Optional[list[str]] = None
    team_multiplier_applied: Optional[bool] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(
        cls,
        a: TaskAssignment,
        rejection_prompt: Optional[str] = None,
        streak_after: Optional[int] = None,
        vouchers_earned: Optional[list[str]] = None,
        team_multiplier_applied: Optional[bool] = None,
    ) -> "AssignmentResponse":
        return cls(
            id=a.id,
            session_id=a.session_id,
            resident_id=a.resident_id,
            task_template_id=a.task_template_id,
            status=a.status,
            score=a.score,
            suggested_at=a.suggested_at.isoformat(),
            accepted_at=a.accepted_at.isoformat() if a.accepted_at else None,
            completed_at=a.completed_at.isoformat() if a.completed_at else None,
            is_forced=a.is_forced,
            points_awarded=a.points_awarded,
            rejection_prompt=rejection_prompt,
            streak_after=streak_after,
            vouchers_earned=vouchers_earned,
            team_multiplier_applied=team_multiplier_applied,
        )


class DelegateRequest(BaseModel):
    to_resident_id: int


class DelegationResponse(BaseModel):
    delegation_id: int
    from_resident_id: int
    to_resident_id: int
    assignment_id: int
    receiver_assignment_id: Optional[int]
    deadline_at: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_assignment_or_404(assignment_id: int, db: Session) -> TaskAssignment:
    a = db.get(TaskAssignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return a


def _assert_status(assignment: TaskAssignment, allowed: list[str]) -> None:
    if assignment.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Assignment status '{assignment.status}' does not allow this action. "
                   f"Expected one of: {allowed}",
        )


# ---------------------------------------------------------------------------
# POST /assignments/{id}/accept
# ---------------------------------------------------------------------------

@router.post("/{assignment_id}/accept", response_model=AssignmentResponse)
def accept_assignment(
    assignment_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Accept a suggested task — moves to in_progress."""
    assignment = _get_assignment_or_404(assignment_id, db)
    _assert_status(assignment, ["suggested", "delegation_received"])

    assignment.status = "in_progress"
    assignment.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assignment)
    return AssignmentResponse.from_orm_model(assignment)


# ---------------------------------------------------------------------------
# POST /assignments/{id}/complete
# ---------------------------------------------------------------------------

@router.post("/{assignment_id}/complete", response_model=AssignmentResponse)
def complete_assignment(
    assignment_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Mark a task as completed.
    - Sets completed_at timestamp
    - Triggers history agent (HistoryEntry + FeedEntry + feedback loop)
    - Triggers gamification agent (points, streak, safes, vouchers)

    For delegation_received tasks: checks DelegationRecord for deadline.
    """
    assignment = _get_assignment_or_404(assignment_id, db)
    _assert_status(assignment, ["suggested", "accepted", "in_progress", "delegation_received"])

    assignment.status = "completed"
    assignment.completed_at = datetime.now(timezone.utc)
    # accepted_at: fill if not set (resident completed without explicitly accepting)
    if not assignment.accepted_at:
        assignment.accepted_at = assignment.completed_at
    db.commit()
    db.refresh(assignment)

    # Trigger history agent
    history_result = record_completion(assignment, db)

    # Check if this is a delegated task
    delegation = (
        db.query(DelegationRecord)
        .filter(DelegationRecord.receiver_assignment_id == assignment.id)
        .first()
    )

    if delegation:
        # Delegated task completion — handles deadline check internally
        game_result = complete_delegated_task(delegation, assignment, db)
    else:
        # Regular task completion — award full points
        game_result = award_task_points(assignment, db)

    db.refresh(assignment)

    return AssignmentResponse.from_orm_model(
        assignment,
        rejection_prompt=history_result.rejection_prompt,
        streak_after=game_result.streak_after,
        vouchers_earned=game_result.vouchers_earned,
        team_multiplier_applied=game_result.team_multiplier_applied,
    )


# ---------------------------------------------------------------------------
# POST /assignments/{id}/skip
# ---------------------------------------------------------------------------

@router.post("/{assignment_id}/skip", response_model=AssignmentResponse)
def skip_assignment(
    assignment_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Skip a task. Logged as skipped — counts as a rejection for scoring.
    Forced tasks (overdue unpopular, delegation_received) can still be skipped,
    but they will reappear sooner (rejection malus doesn't outlast overdue factor).
    """
    assignment = _get_assignment_or_404(assignment_id, db)
    _assert_status(assignment, ["suggested", "accepted", "in_progress", "delegation_received"])

    assignment.status = "skipped"
    db.commit()
    db.refresh(assignment)

    # Trigger history agent (creates HistoryEntry, updates rejection profile)
    result = record_skip(assignment, db)

    return AssignmentResponse.from_orm_model(assignment, rejection_prompt=result.rejection_prompt)


# ---------------------------------------------------------------------------
# POST /assignments/{id}/delegate
# ---------------------------------------------------------------------------

@router.post("/{assignment_id}/delegate", response_model=DelegationResponse)
def delegate_assignment(
    assignment_id: int,
    payload: DelegateRequest,
    resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Delegate a task to another resident.
    - Validates: receiver must not dislike the task category (400)
    - Deducts delegation cost from sender
    - Creates DelegationRecord with 3-day deadline
    - Creates new assignment for receiver with status=delegation_received
    """
    assignment = _get_assignment_or_404(assignment_id, db)
    _assert_status(assignment, ["suggested", "accepted", "in_progress"])

    # Caller must own the assignment
    if assignment.resident_id != resident.id:
        raise HTTPException(
            status_code=403,
            detail="You can only delegate your own assignments",
        )

    # Prevent self-delegation
    if payload.to_resident_id == resident.id:
        raise HTTPException(status_code=400, detail="Cannot delegate a task to yourself")

    # Verify receiver exists
    receiver = db.get(Resident, payload.to_resident_id)
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver resident not found")

    # Verify both residents belong to the same household
    if receiver.household_id != resident.household_id:
        raise HTTPException(
            status_code=400,
            detail="Can only delegate tasks to residents of the same household",
        )

    # delegate_task raises HTTPException(400) if receiver dislikes category
    delegation = delegate_task(assignment, payload.to_resident_id, db)

    return DelegationResponse(
        delegation_id=delegation.id,
        from_resident_id=delegation.from_resident_id,
        to_resident_id=delegation.to_resident_id,
        assignment_id=delegation.assignment_id,
        receiver_assignment_id=delegation.receiver_assignment_id,
        deadline_at=delegation.deadline_at.isoformat(),
    )

"""
sessions router — Daily task session management.

Endpoints:
    POST /sessions                       — start a session, returns suggestions
    GET  /sessions/{id}/suggestions      — (re-)fetch suggestions for a session
    POST /sessions/{id}/reroll           — reroll suggestions (free 1st, malus 2nd+)
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.agents.suggestion_agent import get_suggestions, ScoredTask
from app.agents.gamification_agent import apply_reroll_malus  # R6
from app.models.daily_session import DailySession
from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident
from app.models.resident_game_profile import ResidentGameProfile  # R6
from app.models.enums import EnergyLevelEnum

router = APIRouter(prefix="/sessions", tags=["sessions"])

MAX_SUGGESTIONS = 3


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    resident_id: int
    energy_level: EnergyLevelEnum
    available_minutes: int = Field(..., ge=5, le=480)


class TaskSuggestionResponse(BaseModel):
    assignment_id: int
    task_id: int
    name: str
    description: Optional[str]
    room_type: str
    category: str
    duration_minutes: int
    energy_level: str
    score: float
    is_forced: bool
    panic_prompt: Optional[str] = None  # R8: non-None when calendar alert_level=panic


class SessionResponse(BaseModel):
    session_id: int
    resident_id: int
    date: str
    energy_level: str
    available_minutes: int
    reroll_count: int
    reroll_malus: bool
    reroll_malus_points_deducted: Optional[int] = None  # R6: points deducted on 2nd+ reroll
    suggestions: list[TaskSuggestionResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_suggestion_response(
    a: TaskAssignment,
    task: TaskTemplate,
    score: float,
    is_forced: bool,
    panic_prompt: Optional[str] = None,
) -> TaskSuggestionResponse:
    return TaskSuggestionResponse(
        assignment_id=a.id,
        task_id=task.id,
        name=task.name,
        description=task.description,
        room_type=task.room_type,
        category=task.category,
        duration_minutes=task.default_duration_minutes,
        energy_level=task.energy_level,
        score=round(score, 2),
        is_forced=is_forced,
        panic_prompt=panic_prompt,
    )


def _get_session_or_404(session_id: int, db: Session) -> DailySession:
    s = db.get(DailySession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


def _create_assignments(
    session: DailySession,
    scored_tasks: list[ScoredTask],
    db: Session,
) -> list[TaskAssignment]:
    now = datetime.now(timezone.utc)
    assignments = []
    for st in scored_tasks:
        a = TaskAssignment(
            session_id=session.id,
            resident_id=session.resident_id,
            task_template_id=st.task.id,
            status="suggested",
            score=st.score,
            suggested_at=now,
            is_forced=st.is_forced,
        )
        db.add(a)
        assignments.append((a, st))
    db.commit()
    for a, _ in assignments:
        db.refresh(a)
    return assignments


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------

@router.post("", response_model=SessionResponse, status_code=201)
def create_session(
    payload: SessionCreate,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Start a daily suggestion session. Returns 2–3 task suggestions."""
    resident = db.get(Resident, payload.resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()

    # Multiple sessions per day per resident are allowed (e.g. morning + evening).
    # R6 streak logic must use the FIRST session per day when counting streaks (GROUP BY date).
    daily_session = DailySession(
        resident_id=payload.resident_id,
        date=today_str,
        energy_level=payload.energy_level.value,
        available_minutes=payload.available_minutes,
        created_at=now,
    )
    db.add(daily_session)
    db.commit()
    db.refresh(daily_session)

    # R6: Check delegation lock — if locked, return only pending delegation_received tasks
    game_profile = (
        db.query(ResidentGameProfile)
        .filter(ResidentGameProfile.resident_id == payload.resident_id)
        .first()
    )
    if game_profile and game_profile.delegation_locked:
        # Only show the pending delegated assignment — no normal suggestions
        pending_delegation = (
            db.query(TaskAssignment)
            .filter(
                TaskAssignment.resident_id == payload.resident_id,
                TaskAssignment.status == "delegation_received",
            )
            .first()
        )
        if pending_delegation:
            task = db.get(TaskTemplate, pending_delegation.task_template_id)
            suggestions = [
                _build_suggestion_response(
                    pending_delegation, task,
                    pending_delegation.score or 0.0,
                    True,  # is_forced — cannot be rerolled away
                )
            ]
        else:
            # Lock active but no pending assignment found — clear lock
            game_profile.delegation_locked = False
            db.commit()
            scored_tasks = get_suggestions(daily_session, db, max_results=MAX_SUGGESTIONS)
            pairs = _create_assignments(daily_session, scored_tasks, db)
            suggestions = [
                _build_suggestion_response(a, st.task, st.score, st.is_forced, st.panic_prompt)
                for a, st in zip([p[0] for p in pairs], scored_tasks)
            ]
    else:
        scored_tasks = get_suggestions(daily_session, db, max_results=MAX_SUGGESTIONS)
        pairs = _create_assignments(daily_session, scored_tasks, db)
        suggestions = [
            _build_suggestion_response(a, st.task, st.score, st.is_forced, st.panic_prompt)
            for a, st in zip([p[0] for p in pairs], scored_tasks)
        ]

    return SessionResponse(
        session_id=daily_session.id,
        resident_id=daily_session.resident_id,
        date=daily_session.date,
        energy_level=daily_session.energy_level,
        available_minutes=daily_session.available_minutes,
        reroll_count=daily_session.reroll_count,
        reroll_malus=daily_session.reroll_malus,
        suggestions=suggestions,
    )


# ---------------------------------------------------------------------------
# GET /sessions/{id}/suggestions
# ---------------------------------------------------------------------------

@router.get("/{session_id}/suggestions", response_model=list[TaskSuggestionResponse])
def get_session_suggestions(
    session_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Retrieve the current suggestions for a session."""
    session = _get_session_or_404(session_id, db)
    assignments = (
        db.query(TaskAssignment)
        .filter(
            TaskAssignment.session_id == session_id,
            TaskAssignment.status == "suggested",
        )
        .all()
    )
    result = []
    for a in assignments:
        task = db.get(TaskTemplate, a.task_template_id)
        result.append(_build_suggestion_response(a, task, a.score or 0.0, a.is_forced))
    return result


# ---------------------------------------------------------------------------
# POST /sessions/{id}/reroll
# ---------------------------------------------------------------------------

@router.post("/{session_id}/reroll", response_model=SessionResponse)
def reroll_session(
    session_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Reroll suggestions for a session.
    - 1st reroll: free, new suggestions (excludes previously shown tasks)
    - 2nd+ reroll: new suggestions, sets reroll_malus=True (Gamification Agent deducts points in R6)
    Forced tasks (overdue unpopular) cannot be removed by reroll.
    """
    session = _get_session_or_404(session_id, db)

    # Collect all task IDs ever shown in this session
    all_shown = (
        db.query(TaskAssignment.task_template_id)
        .filter(TaskAssignment.session_id == session_id)
        .all()
    )
    excluded_ids = [row[0] for row in all_shown]

    # Mark currently suggested assignments as skipped (effectively replaced)
    current_suggestions = (
        db.query(TaskAssignment)
        .filter(
            TaskAssignment.session_id == session_id,
            TaskAssignment.status == "suggested",
        )
        .all()
    )
    # Keep forced tasks — they survive reroll
    forced_assignments = [a for a in current_suggestions if a.is_forced]
    for a in current_suggestions:
        if not a.is_forced:
            a.status = "skipped"

    # Increment reroll count and flag malus on 2nd+ reroll
    session.reroll_count += 1
    malus_was_already_active = session.reroll_malus
    if session.reroll_count >= 2:
        session.reroll_malus = True

    db.commit()

    # R6: Deduct points on the FIRST time malus triggers (reroll_count == 2)
    # Subsequent rerolls (3rd, 4th, …) do NOT deduct again.
    points_deducted = None
    if session.reroll_count == 2 and not malus_was_already_active:
        points_deducted = apply_reroll_malus(session, db)

    # New suggestions — exclude all previously shown, preserve forced
    forced_task_ids = {a.task_template_id for a in forced_assignments}
    new_max = MAX_SUGGESTIONS - len(forced_assignments)

    new_scored = get_suggestions(
        session, db,
        excluded_task_ids=excluded_ids,
        max_results=new_max,
    )
    # Filter out any tasks that are forced (already in session)
    new_scored = [s for s in new_scored if s.task.id not in forced_task_ids]

    new_pairs = _create_assignments(session, new_scored, db)

    # Build response
    now_suggestions = []
    for a in forced_assignments:
        task = db.get(TaskTemplate, a.task_template_id)
        now_suggestions.append(_build_suggestion_response(a, task, a.score or 0.0, True))
    for a, st in zip([p[0] for p in new_pairs], new_scored):
        now_suggestions.append(_build_suggestion_response(a, st.task, st.score, st.is_forced))

    return SessionResponse(
        session_id=session.id,
        resident_id=session.resident_id,
        date=session.date,
        energy_level=session.energy_level,
        available_minutes=session.available_minutes,
        reroll_count=session.reroll_count,
        reroll_malus=session.reroll_malus,
        reroll_malus_points_deducted=points_deducted,
        suggestions=now_suggestions,
    )

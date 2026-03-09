"""
gamification_agent.py — Points, streaks, streak-safes, vouchers, delegation.

All logic is white-hat: rewarding positive behaviour, never punishing rest.
All point values are defined as named constants — easy to tune.

Public API:
    award_task_points(assignment, db)          -> GamificationResult
    apply_reroll_malus(session, db)            -> int  (points deducted)
    delegate_task(assignment, to_resident_id, db) -> DelegationRecord
    complete_delegated_task(delegation, assignment, db) -> GamificationResult
    redeem_voucher(voucher_id, resident_id, db)   -> Voucher
    run_daily_streak_check(db)                 -> None  (called by scheduler)
    run_delegation_expiry_check(db)            -> None  (called by scheduler)
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.task_assignment import TaskAssignment
from app.models.task_template import TaskTemplate
from app.models.resident import Resident
from app.models.resident_preference import ResidentPreference
from app.models.daily_session import DailySession
from app.models.resident_game_profile import ResidentGameProfile
from app.models.household_game_profile import HouseholdGameProfile
from app.models.point_transaction import PointTransaction
from app.models.voucher import Voucher
from app.models.delegation_record import DelegationRecord
from app.models.household_feed_entry import HouseholdFeedEntry
from app.models.enums import PointReasonEnum, VoucherTypeEnum

# ---------------------------------------------------------------------------
# Constants — all configurable here
# ---------------------------------------------------------------------------

POINTS_BASE = 10                  # base points per completed task
POINTS_UNPOPULAR_MULTIPLIER = 1.5 # applied when task is unpopular (all residents dislike)
POINTS_TEAM_MULTIPLIER = 1.3      # applied to BOTH residents when all complete ≥1 task same day
POINTS_REROLL_MALUS = -3          # deducted on 2nd+ reroll in a session
POINTS_DELEGATION_COST = -5       # deducted from sender on delegation

VOUCHER_THRESHOLD = 100           # earn 1 voucher per full 100-point increment
DELEGATION_DEADLINE_DAYS = 3      # days until delegation expires

# Streak-safe caps per day (no cap on total held)
SAFES_FOR_2_TASKS = 1
SAFES_FOR_3_TASKS = 2
SAFES_FOR_4_TASKS = 3             # maximum safes earned per day


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class GamificationResult:
    points_awarded: int = 0
    was_unpopular: bool = False
    team_multiplier_applied: bool = False
    streak_before: int = 0
    streak_after: int = 0
    safes_earned: int = 0
    vouchers_earned: list[str] = field(default_factory=list)  # labels of new vouchers
    transactions: list[int] = field(default_factory=list)     # PointTransaction IDs


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def award_task_points(assignment: TaskAssignment, db: Session) -> GamificationResult:
    """
    Called after POST /assignments/{id}/complete (non-delegated tasks).
    1. Awards base points (+unpopular bonus if applicable)
    2. Checks team multiplier
    3. Updates streak + safes
    4. Issues vouchers if threshold crossed
    """
    task = db.get(TaskTemplate, assignment.task_template_id)
    resident = db.get(Resident, assignment.resident_id)
    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()

    profile = _get_or_create_game_profile(resident.id, db)
    result = GamificationResult(
        streak_before=profile.current_streak,
    )

    # --- 1. Base points --------------------------------------------------
    base = POINTS_BASE
    result.points_awarded += base
    tx_id = _log_transaction(
        resident.id, profile, base,
        PointReasonEnum.task_completed,
        reference_id=assignment.id,
        db=db,
    )
    result.transactions.append(tx_id)

    # --- 2. Unpopular bonus ----------------------------------------------
    unpopular = _is_task_unpopular(task, resident.household_id, db)
    result.was_unpopular = unpopular
    if unpopular:
        bonus = int(base * POINTS_UNPOPULAR_MULTIPLIER) - base  # delta only
        result.points_awarded += bonus
        tx_id = _log_transaction(
            resident.id, profile, bonus,
            PointReasonEnum.unpopular_bonus,
            reference_id=assignment.id,
            db=db,
        )
        result.transactions.append(tx_id)

    # --- 3. Commit personal points so total_points is current before team check
    profile.total_points += result.points_awarded
    db.flush()

    # --- 4. Team multiplier check ----------------------------------------
    team_bonus = _check_and_apply_team_multiplier(
        resident, today_str, result.points_awarded, profile, db
    )
    if team_bonus > 0:
        result.team_multiplier_applied = True
        result.points_awarded += team_bonus
        # team bonus already written to profile inside helper

    # --- 5. Update streak ------------------------------------------------
    safes_earned = _update_streak(profile, today_str, db)
    result.safes_earned = safes_earned

    # --- 6. Voucher thresholds -------------------------------------------
    new_vouchers = _issue_vouchers(resident, profile, db)
    result.vouchers_earned = new_vouchers

    # --- 7. Persist assignment points ------------------------------------
    assignment.points_awarded = result.points_awarded

    db.commit()

    result.streak_after = profile.current_streak
    return result


def apply_reroll_malus(session: DailySession, db: Session) -> int:
    """
    Called when reroll_count reaches 2 (2nd reroll) in a session.
    Deducts POINTS_REROLL_MALUS from the resident and logs the transaction.
    Returns the absolute value of points deducted.
    """
    resident = db.get(Resident, session.resident_id)
    profile = _get_or_create_game_profile(resident.id, db)

    deduction = POINTS_REROLL_MALUS  # negative
    profile.total_points = max(0, profile.total_points + deduction)

    _log_transaction(
        resident.id, profile, deduction,
        PointReasonEnum.reroll_malus,
        reference_id=session.id,
        db=db,
    )
    db.commit()
    return abs(deduction)


def delegate_task(
    assignment: TaskAssignment,
    to_resident_id: int,
    db: Session,
) -> DelegationRecord:
    """
    Delegate a task from one resident to another.
    - Validates receiver does not dislike the task category (400 if so)
    - Deducts POINTS_DELEGATION_COST from sender
    - Sets sender assignment to 'delegated'
    - Creates new assignment for receiver with status 'delegation_received'
    - Creates DelegationRecord with deadline 3 days from now

    Raises ValueError if receiver dislikes the task category.
    """
    from fastapi import HTTPException

    task = db.get(TaskTemplate, assignment.task_template_id)
    sender = db.get(Resident, assignment.resident_id)
    receiver = db.get(Resident, to_resident_id)
    now = datetime.now(timezone.utc)

    # Validate: receiver must not dislike this category
    pref = (
        db.query(ResidentPreference)
        .filter(
            ResidentPreference.resident_id == to_resident_id,
            ResidentPreference.task_category == task.category,
        )
        .first()
    )
    if pref and pref.preference == "dislike":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delegate: {receiver.display_name} dislikes "
                f"the '{task.category}' category."
            ),
        )

    # Deduct delegation cost from sender
    sender_profile = _get_or_create_game_profile(sender.id, db)
    sender_profile.total_points = max(0, sender_profile.total_points + POINTS_DELEGATION_COST)
    _log_transaction(
        sender.id, sender_profile, POINTS_DELEGATION_COST,
        PointReasonEnum.delegation_cost,
        reference_id=assignment.id,
        db=db,
    )

    # Mark sender's assignment as delegated
    assignment.status = "delegated"

    # Create receiver assignment (no session — standalone)
    # Use the sender's session_id so context is preserved
    receiver_assignment = TaskAssignment(
        session_id=assignment.session_id,
        resident_id=to_resident_id,
        task_template_id=assignment.task_template_id,
        status="delegation_received",
        score=assignment.score,
        suggested_at=now,
        is_forced=True,  # delegation_received tasks cannot be rerolled away
    )
    db.add(receiver_assignment)
    db.flush()  # get receiver_assignment.id

    # Create DelegationRecord
    delegation = DelegationRecord(
        from_resident_id=sender.id,
        to_resident_id=to_resident_id,
        assignment_id=assignment.id,
        receiver_assignment_id=receiver_assignment.id,
        delegated_at=now,
        deadline_at=now + timedelta(days=DELEGATION_DEADLINE_DAYS),
    )
    db.add(delegation)

    # Feed entry
    feed = HouseholdFeedEntry(
        resident_id=sender.id,
        text=f"{sender.display_name} delegated '{task.name}' to {receiver.display_name}",
        action_type="delegated",
        task_name=task.name,
        timestamp=now,
    )
    db.add(feed)

    db.commit()
    db.refresh(delegation)
    return delegation


def complete_delegated_task(
    delegation: DelegationRecord,
    assignment: TaskAssignment,
    db: Session,
) -> GamificationResult:
    """
    Called when a receiver completes a delegation_received assignment.
    If deadline already passed (no_points_on_completion=True): no points.
    Otherwise: award normal points to receiver.
    """
    now = datetime.now(timezone.utc)

    if delegation.no_points_on_completion:
        # Deadline already expired — no points, just mark complete
        assignment.status = "completed"
        assignment.completed_at = now
        delegation.completed_at = now
        db.commit()
        return GamificationResult()

    # Award points normally
    result = award_task_points(assignment, db)
    delegation.completed_at = now
    db.commit()
    return result


def redeem_voucher(voucher_id: int, resident_id: int, db: Session) -> Voucher:
    """
    Redeem a voucher. Currently supports:
    - free_day: grants +1 streak-safe to the resident immediately
    - custom: marked as redeemed (display only)

    Raises ValueError if voucher not found, not owned by resident, or already redeemed.
    """
    from fastapi import HTTPException

    voucher = db.get(Voucher, voucher_id)
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
    if voucher.resident_id != resident_id:
        raise HTTPException(status_code=403, detail="This voucher belongs to another resident")
    if voucher.is_redeemed:
        raise HTTPException(status_code=409, detail="Voucher has already been redeemed")

    now = datetime.now(timezone.utc)
    voucher.is_redeemed = True
    voucher.redeemed_at = now

    if voucher.type == VoucherTypeEnum.free_day:
        profile = _get_or_create_game_profile(resident_id, db)
        profile.streak_safes_available += 1

        _log_transaction(
            resident_id, profile, 0,
            PointReasonEnum.voucher_redeemed,
            reference_id=voucher.id,
            db=db,
        )

    db.commit()
    db.refresh(voucher)
    return voucher


# ---------------------------------------------------------------------------
# Daily scheduler jobs
# ---------------------------------------------------------------------------

def run_daily_streak_check(db: Session) -> None:
    """
    Run at 00:01 daily for every resident.
    For each resident:
      - If last_activity_date == yesterday: streak continues (already handled on complete)
      - If last_activity_date == today: nothing to do
      - If last_activity_date < yesterday (or None): missed day
          → use streak-safe if available, else reset streak to 0
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    today_str = today.isoformat()

    profiles = db.query(ResidentGameProfile).all()
    for profile in profiles:
        if profile.last_activity_date is None:
            # Never done anything — nothing to reset
            continue
        if profile.last_activity_date == today_str:
            # Already active today — no action needed
            continue
        if profile.last_activity_date == yesterday_str:
            # Was active yesterday — streak is live, daily job runs at midnight
            # so this is correct: no missed day
            continue

        # Missed at least one day
        if profile.streak_safes_available > 0:
            profile.streak_safes_available -= 1
            profile.streak_safes_used += 1
            # Streak continues — do NOT reset
        else:
            profile.current_streak = 0

    db.commit()


def run_delegation_expiry_check(db: Session) -> None:
    """
    Run daily. Finds DelegationRecords where:
      deadline_at < now AND completed_at IS NULL AND no_points_on_completion == False

    For each expired delegation:
      - Set no_points_on_completion = True
      - Set delegation_locked = True on receiver's ResidentGameProfile
    """
    now = datetime.now(timezone.utc)

    expired = (
        db.query(DelegationRecord)
        .filter(
            DelegationRecord.deadline_at < now,
            DelegationRecord.completed_at.is_(None),
            DelegationRecord.no_points_on_completion == False,  # noqa: E712
        )
        .all()
    )

    for delegation in expired:
        delegation.no_points_on_completion = True
        receiver_profile = _get_or_create_game_profile(delegation.to_resident_id, db)
        receiver_profile.delegation_locked = True

    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_game_profile(resident_id: int, db: Session) -> ResidentGameProfile:
    profile = (
        db.query(ResidentGameProfile)
        .filter(ResidentGameProfile.resident_id == resident_id)
        .first()
    )
    if not profile:
        now = datetime.now(timezone.utc)
        profile = ResidentGameProfile(
            resident_id=resident_id,
            created_at=now,
        )
        db.add(profile)
        db.flush()
    return profile


def _get_or_create_household_game_profile(
    household_id: int, db: Session
) -> HouseholdGameProfile:
    profile = (
        db.query(HouseholdGameProfile)
        .filter(HouseholdGameProfile.household_id == household_id)
        .first()
    )
    if not profile:
        now = datetime.now(timezone.utc)
        profile = HouseholdGameProfile(
            household_id=household_id,
            created_at=now,
        )
        db.add(profile)
        db.flush()
    return profile


def _log_transaction(
    resident_id: int,
    profile: ResidentGameProfile,
    amount: int,
    reason: PointReasonEnum,
    db: Session,
    reference_id: Optional[int] = None,
) -> int:
    tx = PointTransaction(
        resident_id=resident_id,
        game_profile_id=profile.id,
        amount=amount,
        reason=reason,
        reference_id=reference_id,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(tx)
    db.flush()
    return tx.id


def _is_task_unpopular(task: TaskTemplate, household_id: int, db: Session) -> bool:
    """
    A task is unpopular when ALL active residents in the household have 'dislike'
    preference for the task's category. If no residents have a preference set,
    the task is NOT considered unpopular.
    """
    residents = (
        db.query(Resident)
        .filter(Resident.household_id == household_id)
        .all()
    )
    if not residents:
        return False

    for resident in residents:
        pref = (
            db.query(ResidentPreference)
            .filter(
                ResidentPreference.resident_id == resident.id,
                ResidentPreference.task_category == task.category,
            )
            .first()
        )
        if not pref or pref.preference != "dislike":
            return False  # At least one resident doesn't dislike it

    return True  # All residents dislike it


def _check_and_apply_team_multiplier(
    completing_resident: Resident,
    today_str: str,
    personal_points: int,
    profile: ResidentGameProfile,
    db: Session,
) -> int:
    """
    Check if ALL active residents in the household completed at least 1 task today.
    If yes: apply POINTS_TEAM_MULTIPLIER to BOTH residents.

    Returns the additional bonus awarded to the completing resident (0 if not triggered).
    """
    household_id = completing_resident.household_id
    all_residents = (
        db.query(Resident)
        .filter(Resident.household_id == household_id)
        .all()
    )
    if len(all_residents) < 2:
        # Team multiplier requires at least 2 residents
        return 0

    # Check each resident completed ≥1 task today
    for r in all_residents:
        completed_today = (
            db.query(TaskAssignment)
            .join(DailySession, TaskAssignment.session_id == DailySession.id)
            .filter(
                TaskAssignment.resident_id == r.id,
                TaskAssignment.status == "completed",
                DailySession.date == today_str,
            )
            .first()
        )
        if not completed_today:
            return 0  # Not all residents completed yet

    # All residents done! Apply team multiplier.
    # We don't want to double-apply — track with household profile last_team_activity_date
    household_profile = _get_or_create_household_game_profile(household_id, db)
    if household_profile.last_team_activity_date == today_str:
        # Already applied today — skip
        return 0

    household_profile.last_team_activity_date = today_str
    now = datetime.now(timezone.utc)

    total_team_bonus = 0
    for r in all_residents:
        r_profile = _get_or_create_game_profile(r.id, db)

        # Calculate this resident's earned points today (approximate via profile delta)
        # For simplicity: apply multiplier as (multiplier - 1.0) * personal_points for each
        # This awards the DELTA — the "extra" on top of what they already got.
        # For the completing resident we use personal_points; for others we estimate
        # from their profile history (last team day). We use a flat delta per resident.
        bonus = int(POINTS_BASE * (POINTS_TEAM_MULTIPLIER - 1.0))
        # Note: We award the team bonus based on POINTS_BASE, not the actual personal total,
        # to keep it simple and fair across sessions with different task counts.

        r_profile.total_points += bonus
        household_profile.team_points += bonus

        tx_id = _log_transaction(
            r.id, r_profile, bonus,
            PointReasonEnum.team_bonus,
            reference_id=None,
            db=db,
        )

        if r.id == completing_resident.id:
            total_team_bonus = bonus

    db.flush()
    return total_team_bonus


def _update_streak(profile: ResidentGameProfile, today_str: str, db: Session) -> int:
    """
    Update the resident's streak based on today's completion.
    Returns number of streak-safes earned today.
    """
    yesterday_str = (date.fromisoformat(today_str) - timedelta(days=1)).isoformat()

    last = profile.last_activity_date

    if last == today_str:
        # Second (or more) task today — streak already incremented,
        # just check for extra safes earned
        pass  # fall through to safe calculation below
    elif last == yesterday_str or last is None:
        # Consecutive day or first task ever
        profile.current_streak += 1
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak
    else:
        # Missed days — streak was reset by scheduler or this is first activity after a break.
        # If the scheduler already reset the streak, current_streak is 0; increment from 0.
        profile.current_streak += 1
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak

    profile.last_activity_date = today_str

    # Safes earned based on tasks completed today
    safes_earned = _calculate_safes_earned(profile.resident_id, today_str, db)
    profile.streak_safes_available += safes_earned
    db.flush()
    return safes_earned


def _calculate_safes_earned(resident_id: int, today_str: str, db: Session) -> int:
    """
    Count how many tasks completed TODAY to determine safe increments.
    Returns the INCREMENT of safes earned (not the running total).
    Note: we only want to award the DELTA per task completed.
    Thresholds:
      1 task:  +0 safes
      2 tasks: total +1 safe → delta on 2nd task = +1
      3 tasks: total +2 safes → delta on 3rd task = +1
      4+ tasks: total +3 safes → delta on 4th task = +1, no more after
    """
    completed_today = (
        db.query(TaskAssignment)
        .join(DailySession, TaskAssignment.session_id == DailySession.id)
        .filter(
            TaskAssignment.resident_id == resident_id,
            TaskAssignment.status == "completed",
            DailySession.date == today_str,
        )
        .count()
    )

    if completed_today == 2:
        return SAFES_FOR_2_TASKS      # delta: 1st task gave 0, 2nd gives +1
    elif completed_today == 3:
        return SAFES_FOR_3_TASKS - SAFES_FOR_2_TASKS  # delta: +1
    elif completed_today >= 4:
        if completed_today == 4:
            return SAFES_FOR_4_TASKS - SAFES_FOR_3_TASKS  # delta: +1 (total cap reached)
        # Beyond 4: no more safes per day
        return 0
    return 0  # 1st task gives no safes


def _issue_vouchers(
    resident: Resident, profile: ResidentGameProfile, db: Session
) -> list[str]:
    """
    Issue vouchers based on total_points crossing VOUCHER_THRESHOLD increments.
    Uses watermark to avoid issuing duplicates.
    Returns list of new voucher labels.
    """
    new_threshold_count = profile.total_points // VOUCHER_THRESHOLD
    already_issued = profile.voucher_threshold_watermark
    delta = new_threshold_count - already_issued

    if delta <= 0:
        return []

    now = datetime.now(timezone.utc)
    labels = []
    for _ in range(delta):
        voucher = Voucher(
            resident_id=resident.id,
            game_profile_id=profile.id,
            type=VoucherTypeEnum.free_day,
            label="Free Day Voucher",
            earned_at=now,
        )
        db.add(voucher)
        labels.append("Free Day Voucher")

    profile.voucher_threshold_watermark = new_threshold_count
    db.flush()
    return labels

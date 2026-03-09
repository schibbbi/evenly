"""
gamification router — Points, streaks, vouchers, and household game state.

Endpoints:
    GET  /residents/{id}/game-profile    — personal points, streak, safes, voucher count
    GET  /residents/{id}/transactions    — point transaction history
    GET  /household/game-profile         — team points, team streak
    GET  /vouchers                       — list authenticated resident's vouchers
    POST /vouchers/{id}/redeem           — redeem a voucher
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.agents.gamification_agent import redeem_voucher
from app.models.resident import Resident
from app.models.resident_game_profile import ResidentGameProfile
from app.models.household_game_profile import HouseholdGameProfile
from app.models.point_transaction import PointTransaction
from app.models.voucher import Voucher
from app.models.household import Household

router = APIRouter(tags=["gamification"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GameProfileResponse(BaseModel):
    resident_id: int
    total_points: int
    current_streak: int
    longest_streak: int
    streak_safes_available: int
    streak_safes_used: int
    last_activity_date: Optional[str]
    delegation_locked: bool
    voucher_count: int           # total (including redeemed)
    voucher_unredeemed_count: int

    model_config = {"from_attributes": True}


class PointTransactionResponse(BaseModel):
    id: int
    amount: int
    reason: str
    reference_id: Optional[int]
    timestamp: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, tx: PointTransaction) -> "PointTransactionResponse":
        return cls(
            id=tx.id,
            amount=tx.amount,
            reason=tx.reason.value if hasattr(tx.reason, "value") else str(tx.reason),
            reference_id=tx.reference_id,
            timestamp=tx.timestamp.isoformat(),
        )


class HouseholdGameProfileResponse(BaseModel):
    household_id: int
    team_points: int
    team_streak: int
    last_team_activity_date: Optional[str]

    model_config = {"from_attributes": True}


class VoucherResponse(BaseModel):
    id: int
    type: str
    label: str
    earned_at: str
    redeemed_at: Optional[str]
    is_redeemed: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, v: Voucher) -> "VoucherResponse":
        return cls(
            id=v.id,
            type=v.type.value if hasattr(v.type, "value") else str(v.type),
            label=v.label,
            earned_at=v.earned_at.isoformat(),
            redeemed_at=v.redeemed_at.isoformat() if v.redeemed_at else None,
            is_redeemed=v.is_redeemed,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_game_profile(resident_id: int, db: Session) -> ResidentGameProfile:
    """Lazy-create the game profile on first read."""
    from app.agents.gamification_agent import _get_or_create_game_profile as _create
    profile = _create(resident_id, db)
    db.commit()
    return profile


def _get_resident_or_404(resident_id: int, db: Session) -> Resident:
    r = db.get(Resident, resident_id)
    if not r:
        raise HTTPException(status_code=404, detail="Resident not found")
    return r


# ---------------------------------------------------------------------------
# GET /residents/{id}/game-profile
# ---------------------------------------------------------------------------

@router.get("/residents/{resident_id}/game-profile", response_model=GameProfileResponse)
def get_game_profile(
    resident_id: int,
    _caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Return the personal gamification state for a resident."""
    _get_resident_or_404(resident_id, db)
    profile = _get_or_create_game_profile(resident_id, db)

    vouchers = (
        db.query(Voucher)
        .filter(Voucher.resident_id == resident_id)
        .all()
    )
    voucher_count = len(vouchers)
    voucher_unredeemed_count = sum(1 for v in vouchers if not v.is_redeemed)

    return GameProfileResponse(
        resident_id=profile.resident_id,
        total_points=profile.total_points,
        current_streak=profile.current_streak,
        longest_streak=profile.longest_streak,
        streak_safes_available=profile.streak_safes_available,
        streak_safes_used=profile.streak_safes_used,
        last_activity_date=profile.last_activity_date,
        delegation_locked=profile.delegation_locked,
        voucher_count=voucher_count,
        voucher_unredeemed_count=voucher_unredeemed_count,
    )


# ---------------------------------------------------------------------------
# GET /residents/{id}/transactions
# ---------------------------------------------------------------------------

@router.get(
    "/residents/{resident_id}/transactions",
    response_model=list[PointTransactionResponse],
)
def get_transactions(
    resident_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Return point transaction history for a resident, newest first."""
    _get_resident_or_404(resident_id, db)

    transactions = (
        db.query(PointTransaction)
        .filter(PointTransaction.resident_id == resident_id)
        .order_by(PointTransaction.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [PointTransactionResponse.from_orm(tx) for tx in transactions]


# ---------------------------------------------------------------------------
# GET /household/game-profile
# ---------------------------------------------------------------------------

@router.get("/household/game-profile", response_model=HouseholdGameProfileResponse)
def get_household_game_profile(
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Return the household-level team gamification state."""
    from app.agents.gamification_agent import _get_or_create_household_game_profile as _create
    household_profile = _create(caller.household_id, db)
    db.commit()

    return HouseholdGameProfileResponse(
        household_id=household_profile.household_id,
        team_points=household_profile.team_points,
        team_streak=household_profile.team_streak,
        last_team_activity_date=household_profile.last_team_activity_date,
    )


# ---------------------------------------------------------------------------
# GET /vouchers
# ---------------------------------------------------------------------------

@router.get("/vouchers", response_model=list[VoucherResponse])
def list_vouchers(
    is_redeemed: Optional[bool] = Query(None, description="Filter by redemption status"),
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Return all vouchers belonging to the authenticated resident."""
    q = db.query(Voucher).filter(Voucher.resident_id == caller.id)
    if is_redeemed is not None:
        q = q.filter(Voucher.is_redeemed == is_redeemed)
    vouchers = q.order_by(Voucher.earned_at.desc()).all()
    return [VoucherResponse.from_orm(v) for v in vouchers]


# ---------------------------------------------------------------------------
# POST /vouchers/{id}/redeem
# ---------------------------------------------------------------------------

@router.post("/vouchers/{voucher_id}/redeem", response_model=VoucherResponse)
def redeem_voucher_endpoint(
    voucher_id: int,
    caller: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """
    Redeem a voucher.
    - free_day: grants +1 streak-safe immediately
    - custom: marked as redeemed (display only)

    Raises 404 if not found, 403 if not owner, 409 if already redeemed.
    """
    voucher = redeem_voucher(voucher_id, caller.id, db)
    return VoucherResponse.from_orm(voucher)

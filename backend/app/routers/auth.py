"""
auth router — PIN verification and PIN management endpoints.

Endpoints:
    POST /auth/verify-pin         — verify a PIN, returns { valid, role }
    POST /residents/{id}/change-pin — change own PIN (any role)
    POST /residents/{id}/reset-pin  — admin resets another resident's PIN
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import (
    get_active_resident,
    require_role,
    verify_pin,
    hash_pin,
)
from app.models.resident import Resident

router = APIRouter(tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class VerifyPinRequest(BaseModel):
    resident_id: int
    pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


class VerifyPinResponse(BaseModel):
    valid: bool
    role: str | None = None


class ChangePinRequest(BaseModel):
    current_pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")
    new_pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


class ResetPinRequest(BaseModel):
    new_pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_resident_or_404(resident_id: int, db: Session) -> Resident:
    resident = db.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    return resident


# ---------------------------------------------------------------------------
# POST /auth/verify-pin
# ---------------------------------------------------------------------------

@router.post("/auth/verify-pin", response_model=VerifyPinResponse)
def verify_pin_endpoint(
    payload: VerifyPinRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Verify a resident's PIN.
    - Returns { valid: true, role: "..." } on success.
    - Returns { valid: false } on wrong PIN.
    - Returns 429 after 3 failures within 10 minutes.
    """
    resident = _get_resident_or_404(payload.resident_id, db)
    ip = request.client.host if request.client else None

    is_valid = verify_pin(resident, payload.pin, db, ip_address=ip)

    if is_valid:
        return VerifyPinResponse(valid=True, role=resident.role.value)
    return VerifyPinResponse(valid=False)


# ---------------------------------------------------------------------------
# POST /residents/{id}/change-pin  — any role, own PIN only
# ---------------------------------------------------------------------------

@router.post("/residents/{resident_id}/change-pin", status_code=204)
def change_pin(
    resident_id: int,
    payload: ChangePinRequest,
    request: Request,
    active_resident: Resident = Depends(get_active_resident),
    db: Session = Depends(get_db),
):
    """
    Change own PIN. Any role can do this, but only for their own account.
    Current PIN must be provided and correct.
    """
    # Can only change own PIN
    if active_resident.id != resident_id:
        raise HTTPException(
            status_code=403,
            detail="You can only change your own PIN",
        )

    ip = request.client.host if request.client else None
    is_valid = verify_pin(active_resident, payload.current_pin, db, ip_address=ip)
    if not is_valid:
        raise HTTPException(status_code=403, detail="Current PIN is incorrect")

    active_resident.pin_hash = hash_pin(payload.new_pin)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# POST /residents/{id}/reset-pin  — admin only
# ---------------------------------------------------------------------------

@router.post("/residents/{resident_id}/reset-pin", status_code=204)
def reset_pin(
    resident_id: int,
    payload: ResetPinRequest,
    admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Admin resets another resident's PIN without requiring current PIN.
    Used for lockout recovery.
    """
    target = _get_resident_or_404(resident_id, db)
    target.pin_hash = hash_pin(payload.new_pin)
    db.commit()
    return None

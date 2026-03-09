"""
auth.py — Reusable FastAPI dependencies for role-based access control.

Usage:
    from app.auth import get_active_resident, require_role, require_pin_or_role

    @router.post("/rooms")
    def create_room(resident=Depends(require_role("admin")), db=Depends(get_db)):
        ...

Future upgrade path:
    Replace get_active_resident() with a JWT-based version.
    All role guards remain unchanged because they depend only on the Resident object.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.resident import Resident
from app.models.pin_attempt_log import PINAttemptLog

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLE_HIERARCHY = ["view", "edit", "admin"]


# ---------------------------------------------------------------------------
# PIN utilities (shared across routers — do not duplicate)
# ---------------------------------------------------------------------------

def hash_pin(pin: str) -> str:
    """Hash a 4-digit PIN with bcrypt. Use this everywhere — never store plain PINs."""
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()
PIN_THROTTLE_WINDOW_MINUTES = 10
PIN_THROTTLE_MAX_FAILURES = 3
PIN_THROTTLE_LOCKOUT_MINUTES = 5


# ---------------------------------------------------------------------------
# Core dependency: identify the active resident from request header
# ---------------------------------------------------------------------------

def get_active_resident(
    x_resident_id: Optional[int] = Header(default=None),
    db: Session = Depends(get_db),
) -> Resident:
    """
    Reads X-Resident-ID header and returns the corresponding Resident.
    Raises 401 if header is missing or resident not found.
    """
    if x_resident_id is None:
        raise HTTPException(status_code=401, detail="X-Resident-ID header required")
    resident = db.get(Resident, x_resident_id)
    if not resident:
        raise HTTPException(status_code=401, detail="Resident not found")
    return resident


# ---------------------------------------------------------------------------
# Role guard factory
# ---------------------------------------------------------------------------

def require_role(minimum_role: str):
    """
    Returns a FastAPI dependency that enforces a minimum role level.
    Role hierarchy: view < edit < admin

    Usage:
        @router.post("/rooms")
        def create_room(resident=Depends(require_role("admin")), ...):
    """
    def dependency(resident: Resident = Depends(get_active_resident)) -> Resident:
        resident_level = ROLE_HIERARCHY.index(resident.role.value)
        required_level = ROLE_HIERARCHY.index(minimum_role)
        if resident_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{minimum_role}' or higher required. "
                       f"Your role: '{resident.role.value}'",
            )
        return resident
    return dependency


# ---------------------------------------------------------------------------
# PIN verification helper (used by auth router and require_pin_or_role)
# ---------------------------------------------------------------------------

def _check_pin_throttle(resident_id: int, db: Session) -> None:
    """Raises 429 if too many failed PIN attempts in the throttle window."""
    window_start = datetime.now(timezone.utc) - timedelta(minutes=PIN_THROTTLE_WINDOW_MINUTES)
    failure_count = (
        db.query(PINAttemptLog)
        .filter(
            PINAttemptLog.resident_id == resident_id,
            PINAttemptLog.success == False,  # noqa: E712
            PINAttemptLog.attempted_at >= window_start,
        )
        .count()
    )
    if failure_count >= PIN_THROTTLE_MAX_FAILURES:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed PIN attempts. "
                   f"Try again in {PIN_THROTTLE_LOCKOUT_MINUTES} minutes.",
            headers={"Retry-After": str(PIN_THROTTLE_LOCKOUT_MINUTES * 60)},
        )


def verify_pin(resident: Resident, pin: str, db: Session, ip_address: Optional[str] = None) -> bool:
    """
    Verifies a PIN against the stored bcrypt hash.
    Logs the attempt and enforces throttling.
    Returns True if valid, False if invalid.
    Raises 429 if throttle limit exceeded.
    """
    _check_pin_throttle(resident.id, db)

    is_valid = bcrypt.checkpw(pin.encode(), resident.pin_hash.encode())

    log = PINAttemptLog(
        resident_id=resident.id,
        success=is_valid,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()

    return is_valid


# ---------------------------------------------------------------------------
# Combined: role OR PIN guard
# ---------------------------------------------------------------------------

def require_pin_or_role(minimum_role: str):
    """
    Returns a dependency that passes if EITHER:
    - Resident already has sufficient role, OR
    - Resident provides a valid PIN via X-Resident-PIN header

    Used for sensitive actions where a lower-role resident can elevate
    temporarily with their PIN (e.g. entering settings screen).
    """
    def dependency(
        request: Request,
        x_resident_pin: Optional[str] = Header(default=None),
        resident: Resident = Depends(get_active_resident),
        db: Session = Depends(get_db),
    ) -> Resident:
        resident_level = ROLE_HIERARCHY.index(resident.role.value)
        required_level = ROLE_HIERARCHY.index(minimum_role)

        # Already has sufficient role — no PIN needed
        if resident_level >= required_level:
            return resident

        # Try PIN elevation
        if x_resident_pin is None:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{minimum_role}' required, or provide X-Resident-PIN header",
            )

        ip = request.client.host if request.client else None
        if not verify_pin(resident, x_resident_pin, db, ip_address=ip):
            raise HTTPException(status_code=403, detail="Invalid PIN")

        return resident

    return dependency

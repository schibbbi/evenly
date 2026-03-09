from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_active_resident, require_role, hash_pin
from app.models.enums import RoleEnum, PreferenceEnum
from app.models.resident import Resident
from app.models.resident_preference import ResidentPreference
from app.models.household import Household

router = APIRouter(prefix="/residents", tags=["residents"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ResidentCreate(BaseModel):
    household_id: int
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    role: RoleEnum = RoleEnum.view
    pin: str = Field(..., min_length=4, max_length=4, pattern=r"^\d{4}$")


class ResidentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    display_name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    role: RoleEnum | None = None
    pin: str | None = Field(None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    setup_complete: bool | None = None


class ResidentResponse(BaseModel):
    id: int
    household_id: int
    name: str
    display_name: str
    color: str
    role: RoleEnum
    setup_complete: bool
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, r: Resident) -> "ResidentResponse":
        return cls(
            id=r.id,
            household_id=r.household_id,
            name=r.name,
            display_name=r.display_name,
            color=r.color,
            role=r.role,
            setup_complete=r.setup_complete,
            created_at=r.created_at.isoformat(),
        )


class PreferenceCreate(BaseModel):
    task_category: str = Field(..., min_length=1, max_length=50)
    preference: PreferenceEnum


class PreferenceResponse(BaseModel):
    id: int
    resident_id: int
    task_category: str
    preference: PreferenceEnum

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_resident_or_404(resident_id: int, db: Session) -> Resident:
    resident = db.get(Resident, resident_id)
    if not resident:
        raise HTTPException(status_code=404, detail="Resident not found")
    return resident


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/bootstrap", response_model=ResidentResponse, status_code=201)
def bootstrap_first_resident(
    payload: ResidentCreate,
    db: Session = Depends(get_db),
):
    """Create the first admin resident during initial setup.
    No auth guard — only works if the household has zero existing residents.
    Returns 409 if residents already exist (prevents abuse).
    """
    household = db.get(Household, payload.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    existing_count = (
        db.query(Resident)
        .filter(Resident.household_id == payload.household_id)
        .count()
    )
    if existing_count > 0:
        raise HTTPException(
            status_code=409,
            detail="Residents already exist. Use the authenticated endpoint to add more.",
        )

    resident = Resident(
        household_id=payload.household_id,
        name=payload.name,
        display_name=payload.display_name,
        color=payload.color,
        role=RoleEnum.admin,  # always admin for bootstrap
        pin_hash=hash_pin(payload.pin),
    )
    db.add(resident)
    db.commit()
    db.refresh(resident)
    return ResidentResponse.from_orm_model(resident)


@router.post("", response_model=ResidentResponse, status_code=201)
def create_resident(
    payload: ResidentCreate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Create a new resident (requires admin role)."""
    household = db.get(Household, payload.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    existing_count = (
        db.query(Resident)
        .filter(Resident.household_id == payload.household_id)
        .count()
    )
    # First resident always becomes admin (failsafe — should not normally be reached via this endpoint)
    role = RoleEnum.admin if existing_count == 0 else payload.role

    resident = Resident(
        household_id=payload.household_id,
        name=payload.name,
        display_name=payload.display_name,
        color=payload.color,
        role=role,
        pin_hash=hash_pin(payload.pin),
    )
    db.add(resident)
    db.commit()
    db.refresh(resident)
    return ResidentResponse.from_orm_model(resident)


@router.get("", response_model=list[ResidentResponse])
def list_residents(household_id: int | None = None, db: Session = Depends(get_db)):
    """List all residents. Optionally filter by household_id."""
    query = db.query(Resident)
    if household_id is not None:
        query = query.filter(Resident.household_id == household_id)
    return [ResidentResponse.from_orm_model(r) for r in query.all()]


@router.put("/{resident_id}", response_model=ResidentResponse)
def update_resident(
    resident_id: int,
    payload: ResidentUpdate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update a resident's details."""
    resident = _get_resident_or_404(resident_id, db)
    if payload.name is not None:
        resident.name = payload.name
    if payload.display_name is not None:
        resident.display_name = payload.display_name
    if payload.color is not None:
        resident.color = payload.color
    if payload.role is not None:
        resident.role = payload.role
    if payload.pin is not None:
        resident.pin_hash = hash_pin(payload.pin)
    if payload.setup_complete is not None:
        resident.setup_complete = payload.setup_complete
    db.commit()
    db.refresh(resident)
    return ResidentResponse.from_orm_model(resident)


@router.post("/{resident_id}/preferences", response_model=PreferenceResponse, status_code=201)
def set_preference(
    resident_id: int,
    payload: PreferenceCreate,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Set or update a preference for a task category (upsert)."""
    _get_resident_or_404(resident_id, db)

    existing = (
        db.query(ResidentPreference)
        .filter(
            ResidentPreference.resident_id == resident_id,
            ResidentPreference.task_category == payload.task_category,
        )
        .first()
    )
    if existing:
        existing.preference = payload.preference
        db.commit()
        db.refresh(existing)
        return existing

    pref = ResidentPreference(
        resident_id=resident_id,
        task_category=payload.task_category,
        preference=payload.preference,
    )
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref


@router.get("/{resident_id}/preferences", response_model=list[PreferenceResponse])
def get_preferences(
    resident_id: int,
    _resident: Resident = Depends(require_role("view")),
    db: Session = Depends(get_db),
):
    """Get all preferences for a resident."""
    _get_resident_or_404(resident_id, db)
    return (
        db.query(ResidentPreference)
        .filter(ResidentPreference.resident_id == resident_id)
        .all()
    )

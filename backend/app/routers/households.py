from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.models.household import Household
from app.models.resident import Resident

router = APIRouter(prefix="/households", tags=["households"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class HouseholdCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # Composition flags
    has_children: bool = False
    has_cats: bool = False
    has_dogs: bool = False
    has_garden: bool = False
    # Appliance / device capability flags
    has_robot_vacuum: bool = False
    has_robot_mop: bool = False
    has_dishwasher: bool = False
    has_washer: bool = False
    has_dryer: bool = False
    has_window_cleaner: bool = False
    has_steam_cleaner: bool = False
    has_robot_mower: bool = False
    has_irrigation: bool = False


class HouseholdUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    # Composition flags
    has_children: bool | None = None
    has_cats: bool | None = None
    has_dogs: bool | None = None
    has_garden: bool | None = None
    # Appliance / device capability flags
    has_robot_vacuum: bool | None = None
    has_robot_mop: bool | None = None
    has_dishwasher: bool | None = None
    has_washer: bool | None = None
    has_dryer: bool | None = None
    has_window_cleaner: bool | None = None
    has_steam_cleaner: bool | None = None
    has_robot_mower: bool | None = None
    has_irrigation: bool | None = None


class HouseholdResponse(BaseModel):
    id: int
    name: str
    # Composition flags
    has_children: bool
    has_cats: bool
    has_dogs: bool
    has_garden: bool
    # Appliance flags
    has_robot_vacuum: bool
    has_robot_mop: bool
    has_dishwasher: bool
    has_washer: bool
    has_dryer: bool
    has_window_cleaner: bool
    has_steam_cleaner: bool
    has_robot_mower: bool
    has_irrigation: bool
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, h: Household) -> "HouseholdResponse":
        return cls(
            id=h.id,
            name=h.name,
            has_children=h.has_children,
            has_cats=h.has_cats,
            has_dogs=h.has_dogs,
            has_garden=h.has_garden,
            has_robot_vacuum=h.has_robot_vacuum,
            has_robot_mop=h.has_robot_mop,
            has_dishwasher=h.has_dishwasher,
            has_washer=h.has_washer,
            has_dryer=h.has_dryer,
            has_window_cleaner=h.has_window_cleaner,
            has_steam_cleaner=h.has_steam_cleaner,
            has_robot_mower=h.has_robot_mower,
            has_irrigation=h.has_irrigation,
            created_at=h.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLAG_FIELDS = [
    "has_children", "has_cats", "has_dogs", "has_garden",
    "has_robot_vacuum", "has_robot_mop", "has_dishwasher",
    "has_washer", "has_dryer", "has_window_cleaner",
    "has_steam_cleaner", "has_robot_mower", "has_irrigation",
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=HouseholdResponse, status_code=201)
def create_household(payload: HouseholdCreate, db: Session = Depends(get_db)):
    """Create a new household (typically called once at setup via wizard).
    No auth guard — intentionally public during first-run setup (no residents exist yet).
    """
    household = Household(**payload.model_dump())
    db.add(household)
    db.commit()
    db.refresh(household)
    return HouseholdResponse.from_orm_model(household)


@router.get("", response_model=list[HouseholdResponse])
def list_households(db: Session = Depends(get_db)):
    """List all households."""
    return [HouseholdResponse.from_orm_model(h) for h in db.query(Household).all()]


@router.get("/{household_id}", response_model=HouseholdResponse)
def get_household(household_id: int, db: Session = Depends(get_db)):
    """Get a single household by ID."""
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    return HouseholdResponse.from_orm_model(household)


@router.put("/{household_id}", response_model=HouseholdResponse)
def update_household(
    household_id: int,
    payload: HouseholdUpdate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update household — name or any composition/device flag."""
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(household, field, value)
    db.commit()
    db.refresh(household)
    return HouseholdResponse.from_orm_model(household)

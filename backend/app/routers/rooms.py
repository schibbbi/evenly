from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.models.enums import RoomTypeEnum
from app.models.room import Room
from app.models.household import Household
from app.models.resident import Resident

router = APIRouter(prefix="/rooms", tags=["rooms"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RoomCreate(BaseModel):
    household_id: int
    name: str = Field(..., min_length=1, max_length=100)
    type: RoomTypeEnum


class RoomUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: RoomTypeEnum | None = None
    active: bool | None = None


class RoomResponse(BaseModel):
    id: int
    household_id: int
    name: str
    type: RoomTypeEnum
    active: bool
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, r: Room) -> "RoomResponse":
        return cls(
            id=r.id,
            household_id=r.household_id,
            name=r.name,
            type=r.type,
            active=r.active,
            created_at=r.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_room_or_404(room_id: int, db: Session) -> Room:
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=RoomResponse, status_code=201)
def create_room(
    payload: RoomCreate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Create a new room in a household."""
    household = db.get(Household, payload.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    room = Room(
        household_id=payload.household_id,
        name=payload.name,
        type=payload.type,
        active=True,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return RoomResponse.from_orm_model(room)


@router.get("", response_model=list[RoomResponse])
def list_rooms(
    household_id: int | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    """List rooms. Optionally filter by household and/or active status."""
    query = db.query(Room)
    if household_id is not None:
        query = query.filter(Room.household_id == household_id)
    if active_only:
        query = query.filter(Room.active == True)  # noqa: E712
    return [RoomResponse.from_orm_model(r) for r in query.all()]


@router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    payload: RoomUpdate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update a room — including deactivating it via active=false."""
    room = _get_room_or_404(room_id, db)
    if payload.name is not None:
        room.name = payload.name
    if payload.type is not None:
        room.type = payload.type
    if payload.active is not None:
        room.active = payload.active
    db.commit()
    db.refresh(room)
    return RoomResponse.from_orm_model(room)

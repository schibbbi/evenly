from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_role
from app.models.enums import DeviceTypeEnum
from app.models.device import Device
from app.models.household import Household
from app.models.room import Room
from app.models.resident import Resident

router = APIRouter(prefix="/devices", tags=["devices"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DeviceCreate(BaseModel):
    household_id: int
    room_id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    type: DeviceTypeEnum
    notes: str | None = None


class DeviceUpdate(BaseModel):
    room_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    type: DeviceTypeEnum | None = None
    notes: str | None = None


class DeviceResponse(BaseModel):
    id: int
    household_id: int
    room_id: int | None
    name: str
    type: DeviceTypeEnum
    notes: str | None
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, d: Device) -> "DeviceResponse":
        return cls(
            id=d.id,
            household_id=d.household_id,
            room_id=d.room_id,
            name=d.name,
            type=d.type,
            notes=d.notes,
            created_at=d.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_device_or_404(device_id: int, db: Session) -> Device:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=DeviceResponse, status_code=201)
def create_device(
    payload: DeviceCreate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Create a new device in a household."""
    household = db.get(Household, payload.household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")

    if payload.room_id is not None:
        room = db.get(Room, payload.room_id)
        if not room or room.household_id != payload.household_id:
            raise HTTPException(status_code=404, detail="Room not found in this household")

    device = Device(
        household_id=payload.household_id,
        room_id=payload.room_id,
        name=payload.name,
        type=payload.type,
        notes=payload.notes,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return DeviceResponse.from_orm_model(device)


@router.get("", response_model=list[DeviceResponse])
def list_devices(
    household_id: int | None = None,
    room_id: int | None = None,
    db: Session = Depends(get_db),
):
    """List devices. Optionally filter by household or room."""
    query = db.query(Device)
    if household_id is not None:
        query = query.filter(Device.household_id == household_id)
    if room_id is not None:
        query = query.filter(Device.room_id == room_id)
    return [DeviceResponse.from_orm_model(d) for d in query.all()]


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    _admin: Resident = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update a device."""
    device = _get_device_or_404(device_id, db)
    if payload.name is not None:
        device.name = payload.name
    if payload.type is not None:
        device.type = payload.type
    if payload.notes is not None:
        device.notes = payload.notes
    if "room_id" in payload.model_fields_set:
        device.room_id = payload.room_id
    db.commit()
    db.refresh(device)
    return DeviceResponse.from_orm_model(device)

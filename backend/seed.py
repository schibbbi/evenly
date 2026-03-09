"""
Seed script — creates a sample household with 2 residents, rooms, devices,
preferences, and the default task catalog.

Run inside the container: python seed.py
Or locally (with DB accessible): DATABASE_URL=sqlite:///./data/evenly.db python seed.py

The catalog seed is always attempted (idempotent) regardless of whether the
household seed was skipped. This allows re-running the script safely.
"""
import os
import sys
import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(__file__))

from app.database import Base
from app.models import Household, Resident, Room, Device, ResidentPreference  # noqa: F401
from app.models.task_template import TaskTemplate  # noqa: F401 — ensures table is created
from app.models.enums import RoleEnum, RoomTypeEnum, DeviceTypeEnum, PreferenceEnum
from app.agents.catalog_agent import seed_default_catalog

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/evenly.db")


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def seed():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)  # ensure all tables exist

    with Session(engine) as db:

        # ── Household (skip if already seeded) ────────────────────────────
        if db.query(Household).count() > 0:
            print("Household already exists — skipping household seed.")
        else:
            # ---- Household ----
            household = Household(
                name="Our Home",
                # Composition flags
                has_children=True,        # toddler in household
                has_cats=True,            # two cats
                has_dogs=False,
                has_garden=True,
                # Appliance / device capability flags
                has_robot_vacuum=True,    # Roborock Saros 10R
                has_robot_mop=True,       # Roborock also mops
                has_dishwasher=True,
                has_washer=True,
                has_dryer=True,
                has_window_cleaner=True,  # Kärcher WV2
                has_steam_cleaner=False,
                has_robot_mower=False,
                has_irrigation=False,
            )
            db.add(household)
            db.flush()

            # ---- Residents ----
            admin = Resident(
                household_id=household.id,
                name="Michael",
                display_name="Michael",
                color="#6366f1",
                role=RoleEnum.admin,
                pin_hash=hash_pin("1234"),
            )
            partner = Resident(
                household_id=household.id,
                name="Partner",
                display_name="Partner",
                color="#ec4899",
                role=RoleEnum.edit,
                pin_hash=hash_pin("5678"),
            )
            db.add_all([admin, partner])
            db.flush()

            # ---- Rooms ----
            rooms_data = [
                ("Kitchen",          RoomTypeEnum.kitchen),
                ("Living Room",      RoomTypeEnum.living),
                ("Bathroom",         RoomTypeEnum.bathroom),
                ("Bedroom",          RoomTypeEnum.bedroom),
                ("Hallway",          RoomTypeEnum.hallway),
                ("Children's Room",  RoomTypeEnum.childrens_room),
                ("Garden",           RoomTypeEnum.garden),
            ]
            rooms = []
            for name, rtype in rooms_data:
                room = Room(household_id=household.id, name=name, type=rtype, active=True)
                db.add(room)
                rooms.append(room)
            db.flush()

            room_map = {r.name: r for r in rooms}

            # ---- Devices ----
            devices_data = [
                ("Roborock Saros 10R", DeviceTypeEnum.vacuum,          "Living Room", "Robot vacuum & mop"),
                ("Washing Machine",    DeviceTypeEnum.washer,           None,          None),
                ("Dryer",              DeviceTypeEnum.dryer,            None,          None),
                ("Dishwasher",         DeviceTypeEnum.dishwasher,       "Kitchen",     None),
                ("Kärcher WV2",        DeviceTypeEnum.window_cleaner,   None,          "Cordless window cleaner"),
            ]
            for name, dtype, room_name, notes in devices_data:
                room_id = room_map[room_name].id if room_name and room_name in room_map else None
                device = Device(
                    household_id=household.id,
                    room_id=room_id,
                    name=name,
                    type=dtype,
                    notes=notes,
                )
                db.add(device)

            # ---- Preferences ----
            preferences_data = [
                (admin.id,   "garden",       PreferenceEnum.like),
                (admin.id,   "laundry",      PreferenceEnum.neutral),
                (admin.id,   "cleaning",     PreferenceEnum.neutral),
                (partner.id, "cleaning",     PreferenceEnum.like),
                (partner.id, "garden",       PreferenceEnum.neutral),
                (admin.id,   "decluttering", PreferenceEnum.dislike),
                (partner.id, "decluttering", PreferenceEnum.dislike),
            ]
            for resident_id, category, pref in preferences_data:
                db.add(ResidentPreference(
                    resident_id=resident_id,
                    task_category=category,
                    preference=pref,
                ))

            db.commit()
            print(f"✓ Seeded household '{household.name}'")
            print(f"  Residents: {admin.display_name} (admin, PIN: 1234), "
                  f"{partner.display_name} (edit, PIN: 5678)")
            print(f"  Rooms: {', '.join(r.name for r in rooms)}")
            print(f"  Devices: Roborock, Washing Machine, Dryer, Dishwasher, Kärcher WV2")
            print(f"  Preferences: {len(preferences_data)} entries")

        # ── Task catalog (always runs, idempotent) ─────────────────────────
        seed_default_catalog(db)


if __name__ == "__main__":
    seed()

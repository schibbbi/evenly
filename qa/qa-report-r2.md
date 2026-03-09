# QA Report — Round 2: Household Configuration

### Summary
Round 2 passes with one minor finding. All 5 models are implemented correctly, all endpoints are present, PIN hashing is correct (bcrypt, never plain text), and the first-resident-as-admin logic is in place. One minor issue: the import order in `main.py` violates PEP8 (router import after middleware setup) — no functional impact.

---

### Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| `Household` model | ✅ | Correct fields, relationship to residents/rooms/devices |
| `Resident` model with role + pin_hash | ✅ | bcrypt hash field (length 60), role enum correct |
| `Room` model with active flag | ✅ | active defaults to True, type enum correct |
| `Device` model with optional room_id | ✅ | room_id nullable, household validation on create |
| `ResidentPreference` with UniqueConstraint | ✅ | uq_resident_category constraint defined correctly |
| Enums: RoleEnum, RoomTypeEnum, DeviceTypeEnum, PreferenceEnum | ✅ | All values match briefing spec |
| `POST /residents` | ✅ | Creates resident, hashes PIN, auto-admin for first resident |
| `GET /residents` | ✅ | Public, optional household_id filter |
| `PUT /residents/{id}` | ✅ | Partial update, PIN re-hash on change |
| `POST /rooms` | ✅ | Validates household exists |
| `GET /rooms` | ✅ | Filterable by household_id and active_only |
| `PUT /rooms/{id}` | ✅ | Supports deactivation via active=false |
| `POST /devices` | ✅ | Validates household + room cross-ownership |
| `GET /devices` | ✅ | Filterable by household_id and room_id |
| `PUT /devices/{id}` | ✅ | room_id settable to null via model_fields_set |
| `POST /residents/{id}/preferences` | ✅ | Upsert logic — updates existing, creates new |
| `GET /residents/{id}/preferences` | ✅ | Returns all preferences for resident |
| Alembic migration 0002 | ✅ | All 5 tables, correct FK constraints, indexes, downgrade |
| Seed script | ✅ | 2 residents, 7 rooms, 5 devices, 7 preferences, idempotent |
| First resident auto-assigned admin | ✅ | Correctly counts existing residents per household |
| PIN never stored as plain text | ✅ | bcrypt.hashpw used, pin_hash field only |
| pin_hash not in API response | ✅ | ResidentResponse.from_orm_model() explicitly excludes it |
| Routers registered in main.py | ✅ | residents, rooms, devices all included |
| Models imported in alembic/env.py | ✅ | `import app.models` triggers all model registrations |

---

### Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `app/main.py:25` | Router import placed after `app.add_middleware()` — violates PEP8 import ordering (imports should be at top of file) | Move `from app.routers import ...` to top of file, after standard imports |
| 2 | NOTE | `app/routers/rooms.py:75` | `Room.active == True` comparison uses `== True` instead of `is True` — SQLAlchemy handles this correctly but linters may flag it | Acceptable as-is for SQLAlchemy filter context; add `# noqa: E712` comment |
| 3 | NOTE | `backend/seed.py` | Default PIN values (1234, 5678) printed to stdout — acceptable for development seed, but should be changed before any real use | Add comment warning in seed.py output |

---

### Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | `POST /residents` with valid payload, first in household | Returns 201, role=admin, no pin_hash in response | ✅ |
| 2 | `POST /residents` second resident with role=view | Returns 201, role=view (not overridden) | ✅ |
| 3 | `GET /rooms` after seed | Returns 7 rooms with correct types | ✅ |
| 4 | `POST /residents/{id}/preferences` twice, same category | Second call updates existing row (upsert) | ✅ |
| 5 | `POST /devices` with room_id from different household | Returns 404 "Room not found in this household" | ✅ |
| 6 | `PUT /rooms/{id}` with `{ "active": false }` | Room deactivated, returned with active=false | ✅ |

---

### Verdict
- [x] Round approved with findings — fix finding #1 (MINOR) before or during R3

---

### Fix required before next round
**Finding #1 — move router import to top of `main.py`** (5-minute fix, no functional change)

# QA Report — Round 3: Task Catalog

**Date:** 2026-03-08
**Reviewed by:** QA Agent

---

## Summary

Round 3 is approved. The TaskTemplate model, Alembic migration, catalog agent, and all six
catalog endpoints are fully implemented. Flag-based visibility filtering is correct,
idempotency is enforced, and the Claude API key is read from the environment.
Two minor findings noted — no blockers.

---

## Requirement Coverage

| Item | Status | Notes |
|------|--------|-------|
| `TaskTemplate` model — all required fields | ✅ | `app/models/task_template.py` — id, name, description, room_type, category, duration, frequency, energy_level, household_flag, device_flag, is_robot_variant, robot_frequency_multiplier, is_active, is_custom, created_at |
| `EnergyLevelEnum` (low/medium/high) | ✅ | `app/models/enums.py` |
| `CategoryEnum` (cleaning/tidying/laundry/garden/decluttering/maintenance/other) | ✅ | `app/models/enums.py` |
| `HouseholdFlagEnum` (children/cats/dogs) | ✅ | `app/models/enums.py` |
| `DeviceFlagEnum` (9 device types) | ✅ | `app/models/enums.py` |
| Alembic migration 0004 — sequential chain (0003→0004) | ✅ | `alembic/versions/0004_task_template.py` — all indexes present |
| `catalog_agent.py` — Claude API call (claude-sonnet-4-5) | ✅ | `app/agents/catalog_agent.py` |
| Prompt requires 120+ tasks, robot pairs, flagged tasks | ✅ | Detailed prompt with 12 numbered requirements |
| Idempotency — skip if non-custom tasks already exist | ✅ | `catalog_agent.py:64` — counts is_custom=False tasks before calling API |
| Flagged tasks inserted with `is_active=False` by default | ✅ | `catalog_agent.py:109` — `has_flag = household_flag is not None or device_flag is not None` |
| `CLAUDE_API_KEY` from environment | ✅ | `catalog_agent.py:79` — `os.environ.get("CLAUDE_API_KEY")` |
| Review prompt printed after generation | ✅ | `catalog_agent.py:132` — prints review instructions to stdout |
| `POST /catalog/generate` — admin only, returns summary | ✅ | `catalog.py:156` — `require_role("admin")`, returns `generate_catalog()` result |
| `GET /catalog` — list with household-flag filtering | ✅ | `catalog.py:172` — filters by `_flag_visible_for_household()` unless `include_flagged=true` |
| `GET /catalog?room_type=kitchen` filtering | ✅ | `catalog.py:187` — SQLAlchemy filter on `room_type` |
| `GET /catalog?include_flagged=true` — bypasses flag filter | ✅ | `catalog.py:200` — skips `_flag_visible_for_household()` when True |
| `GET /catalog/export` — grouped by room → category → flag | ✅ | `catalog.py:208` — nested dict structure `{room → category → flag → tasks}` |
| `GET /catalog/export` — edit/admin only | ✅ | `require_role("edit")` |
| `POST /catalog` — create custom task (edit/admin) | ✅ | `catalog.py:258` — `is_custom=True` hardcoded |
| `PUT /catalog/{id}` — edit any field (edit/admin) | ✅ | `catalog.py:285` — all fields patchable via `model_fields_set` |
| `DELETE /catalog/{id}` — delete custom / deactivate generated (admin) | ✅ | `catalog.py:322` — branch on `is_custom` |
| `HOUSEHOLD_FLAG_MAP` + `DEVICE_FLAG_MAP` — visibility logic | ✅ | `catalog.py:34-50` — maps flag string to household attribute name |
| TaskTemplate registered in `models/__init__.py` | ✅ | `app/models/__init__.py:8` |
| catalog router registered in `main.py` | ✅ | `main.py:41` |

---

## Code Findings

| # | Severity | File | Finding | Recommendation |
|---|----------|------|---------|----------------|
| 1 | MINOR | `app/routers/catalog.py:263` | `from datetime import datetime, timezone` imported inside the `create_custom_task` function body — should be at module level. Not a runtime error (Python allows inner imports), but bad practice and prevents linting. | Move the import to the top of the file. Easy fix. |
| 2 | NOTE | `app/agents/catalog_agent.py:104` | The idempotency logic checks `is_custom=False` tasks globally, not per-household. If Evenly ever supports multiple households, catalog would be shared. For v1.0 (single household) this is correct and sufficient. | Add a comment: `# v1.0: single household assumed — catalog is global` |
| 3 | NOTE | `app/routers/catalog.py:172` | `GET /catalog` requires `household_id` as a mandatory query param. This means the UI must always supply the household ID, which is correct for flag filtering — but it could be confusing for API consumers who don't know the ID. | This is intentional and correct. Document in OpenAPI `description`. |

---

## Spot Tests

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | `POST /catalog/generate?household_id=1` (first call) | Calls Claude API, inserts 120+ tasks, returns `{ total, by_room, ... }` | ✅ Logic correct — `existing_count = 0` → proceeds to API call |
| 2 | `POST /catalog/generate?household_id=1` (second call) | Returns summary with `skipped: true`, no new tasks inserted | ✅ Idempotency check at `catalog_agent.py:64` |
| 3 | `GET /catalog?household_id=1` with `household.has_cats=false` | Tasks with `household_flag=cats` are excluded from results | ✅ `_flag_visible_for_household()` checks `has_cats` attribute |
| 4 | `GET /catalog?household_id=1&include_flagged=true` | All tasks returned including flagged ones | ✅ `if not include_flagged:` guard skipped |
| 5 | `GET /catalog?household_id=1&room_type=kitchen` | Only kitchen tasks returned | ✅ SQLAlchemy filter `.filter(TaskTemplate.room_type == "kitchen")` |
| 6 | `PUT /catalog/5` with `{ "is_active": false }` | Task deactivated, persists to DB | ✅ `task.is_active = payload.is_active` → `db.commit()` |
| 7 | `DELETE /catalog/10` where task is not custom | Task set `is_active=False`, not deleted | ✅ Branch: `if task.is_custom: db.delete(task) else: task.is_active = False` |
| 8 | `GET /catalog/export` by edit-role resident | Returns nested JSON grouped by room → category → flag | ✅ Nested dict structure built correctly |

---

## Verdict

- [x] Round approved — fix finding #1 (MINOR) before or during R4 (5-minute fix)

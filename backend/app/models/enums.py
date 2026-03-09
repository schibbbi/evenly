import enum


class RoleEnum(str, enum.Enum):
    admin = "admin"
    edit = "edit"
    view = "view"


class RoomTypeEnum(str, enum.Enum):
    kitchen = "kitchen"
    bathroom = "bathroom"
    bedroom = "bedroom"
    living = "living"
    hallway = "hallway"
    childrens_room = "childrens_room"
    garden = "garden"
    other = "other"


class DeviceTypeEnum(str, enum.Enum):
    vacuum = "vacuum"
    washer = "washer"
    dryer = "dryer"
    dishwasher = "dishwasher"
    window_cleaner = "window_cleaner"
    other = "other"


class PreferenceEnum(str, enum.Enum):
    like = "like"
    neutral = "neutral"
    dislike = "dislike"


class EnergyLevelEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AssignmentStatusEnum(str, enum.Enum):
    suggested = "suggested"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"
    delegated = "delegated"
    delegation_received = "delegation_received"  # R6: received as delegate


class PanicSessionStatusEnum(str, enum.Enum):  # R7
    active = "active"
    completed = "completed"


class VoucherTypeEnum(str, enum.Enum):  # R6
    free_day = "free_day"        # skip one day without streak penalty (grants +1 streak-safe)
    custom = "custom"            # household-defined reward


class PointReasonEnum(str, enum.Enum):  # R6
    task_completed = "task_completed"
    unpopular_bonus = "unpopular_bonus"
    team_bonus = "team_bonus"
    delegation_cost = "delegation_cost"
    reroll_malus = "reroll_malus"
    voucher_redeemed = "voucher_redeemed"


class CategoryEnum(str, enum.Enum):
    cleaning = "cleaning"
    tidying = "tidying"
    laundry = "laundry"
    garden = "garden"
    decluttering = "decluttering"
    maintenance = "maintenance"
    other = "other"


class HouseholdFlagEnum(str, enum.Enum):
    children = "children"
    cats = "cats"
    dogs = "dogs"


class DeviceFlagEnum(str, enum.Enum):
    robot_vacuum = "robot_vacuum"
    robot_mop = "robot_mop"
    dishwasher = "dishwasher"
    washer = "washer"
    dryer = "dryer"
    window_cleaner = "window_cleaner"
    steam_cleaner = "steam_cleaner"
    robot_mower = "robot_mower"
    irrigation = "irrigation"


class GuestProbabilityEnum(str, enum.Enum):  # R8
    low = "low"
    medium = "medium"
    high = "high"


class AlertLevelEnum(str, enum.Enum):  # R8
    early = "early"    # 7+ days until event
    medium = "medium"  # 3–6 days
    urgent = "urgent"  # 1–2 days
    panic = "panic"    # same day

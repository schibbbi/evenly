# Import all models here so Alembic autodiscovers them via Base.metadata
from app.models.household import Household
from app.models.resident import Resident
from app.models.room import Room
from app.models.device import Device
from app.models.resident_preference import ResidentPreference
from app.models.pin_attempt_log import PINAttemptLog  # R2b
from app.models.task_template import TaskTemplate     # R3
from app.models.daily_session import DailySession              # R4
from app.models.task_assignment import TaskAssignment          # R4
from app.models.history_entry import HistoryEntry              # R5
from app.models.resident_scoring_profile import ResidentScoringProfile  # R5
from app.models.household_feed_entry import HouseholdFeedEntry          # R5
from app.models.resident_game_profile import ResidentGameProfile        # R6
from app.models.household_game_profile import HouseholdGameProfile      # R6
from app.models.point_transaction import PointTransaction               # R6
from app.models.voucher import Voucher                                  # R6
from app.models.delegation_record import DelegationRecord               # R6
from app.models.panic_session import PanicSession                       # R7
from app.models.calendar_config import CalendarConfig                   # R8
from app.models.calendar_event import CalendarEvent                     # R8
from app.models.household_context import HouseholdContext               # R8

__all__ = [
    "Household", "Resident", "Room", "Device", "ResidentPreference",
    "PINAttemptLog",
    "TaskTemplate",
    "DailySession", "TaskAssignment",
    "HistoryEntry", "ResidentScoringProfile", "HouseholdFeedEntry",
    "ResidentGameProfile", "HouseholdGameProfile", "PointTransaction",
    "Voucher", "DelegationRecord",
    "PanicSession",
    "CalendarConfig", "CalendarEvent", "HouseholdContext",
]

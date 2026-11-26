"""Constants shared by every module of the Perdis Duty Roster integration."""

from __future__ import annotations

from typing import Final

try:  # StrEnum is in the standard library from Python 3.11; older cores ship a backport.
    from enum import StrEnum
except ImportError:  # pragma: no cover - only on Home Assistant cores before 2024
    from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "perdis_roster"
MANUFACTURER: Final = "INIT Mobility Software Solutions (unofficial)"

# Platforms are set up in this order; the calendar comes last because it only reads.
PLATFORMS: Final = ("sensor", "binary_sensor", "calendar")


class PortalType(StrEnum):
    """The two front ends a transit operator can publish for MOBILE-PERDIS."""

    WEBCOMM = "webcomm"  # classic ASP.NET WebForms portal in the browser
    APPCOMM = "appcomm"  # JSON service behind the AppComm smartphone app


# --- Config entry data -----------------------------------------------------------------------
CONF_PORTAL_TYPE: Final = "portal_type"
CONF_BASE_URL: Final = "base_url"
CONF_OPERATOR: Final = "operator"
CONF_VERIFY_SSL: Final = "verify_ssl"
OPERATOR_CUSTOM: Final = "custom"

# --- Options ---------------------------------------------------------------------------------
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_WAKE_UP_LEAD: Final = "wake_up_lead_minutes"
CONF_COMMUTE: Final = "commute_minutes"
CONF_MINIMUM_REST: Final = "minimum_rest_hours"
CONF_LOOKAHEAD_DAYS: Final = "lookahead_days"
CONF_LOOKBACK_DAYS: Final = "lookback_days"
CONF_DETAIL_DAYS: Final = "detail_days"
CONF_NOTIFY_CHANGES: Final = "notify_changes"
CONF_CALENDAR_LEG_EVENTS: Final = "calendar_leg_events"  # one calendar event per shift leg
CONF_PERSON: Final = "person"  # the employee the roster belongs to (a person entity)
CONF_NOTIFY_TARGET: Final = "notify_target"  # legacy: a single service to call, e.g. notify.*
CONF_NOTIFY_ACTION: Final = "notify_action"  # a full action/sequence run on every roster change

# Advanced options: everything the automatic page discovery can get wrong on a strange portal.
SECTION_ADVANCED: Final = "advanced"
CONF_ROSTER_PAGE: Final = "roster_page"
CONF_BALANCES_PAGE: Final = "balances_page"
CONF_WEEKEND_POINTS_PAGE: Final = "weekend_points_page"
CONF_APPCOMM_LOGIN_PATH: Final = "appcomm_login_path"
CONF_APPCOMM_ROSTER_PATH: Final = "appcomm_roster_path"
CONF_APPCOMM_BALANCES_PATH: Final = "appcomm_balances_path"
CONF_APPCOMM_WEEKEND_POINTS_PATH: Final = "appcomm_weekend_points_path"

DEFAULT_SCAN_INTERVAL: Final = 30  # minutes; rosters rarely change more often than that
DEFAULT_WAKE_UP_LEAD: Final = 90  # minutes before the shift starts
DEFAULT_COMMUTE: Final = 30  # minutes from home to the reporting point
DEFAULT_MINIMUM_REST: Final = 11  # hours, the daily rest of EU regulation 561/2006
DEFAULT_LOOKAHEAD_DAYS: Final = 42
DEFAULT_LOOKBACK_DAYS: Final = 7
DEFAULT_DETAIL_DAYS: Final = 42  # how many days ahead to detail each shift; matches the lookahead
DEFAULT_NOTIFY_CHANGES: Final = True
DEFAULT_CALENDAR_LEG_EVENTS: Final = True  # a structured day: each leg of a shift as its own event

# AppComm does not publish its API. These paths are a reasonable starting point and can be
# changed in the options as soon as the real ones of an operator are known.
DEFAULT_APPCOMM_LOGIN_PATH: Final = "api/auth/login"
DEFAULT_APPCOMM_ROSTER_PATH: Final = "api/roster"
DEFAULT_APPCOMM_BALANCES_PATH: Final = "api/accounts"
DEFAULT_APPCOMM_WEEKEND_POINTS_PATH: Final = "api/weekend-points"

# --- Events, services, triggers --------------------------------------------------------------
EVENT_PERDIS: Final = f"{DOMAIN}_event"  # one event type, the kind is in data["type"]

SERVICE_REFRESH: Final = "refresh"
SERVICE_GET_DUTIES: Final = "get_duties"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_START_DATE: Final = "start_date"
ATTR_END_DATE: Final = "end_date"


class TimelineEvent(StrEnum):
    """Moments the integration announces on the event bus and as device triggers."""

    WAKE_UP = "wake_up"
    LEAVE_HOME = "leave_home"
    SHIFT_STARTED = "shift_started"
    SHIFT_ENDED = "shift_ended"
    FREE_WEEKEND_STARTED = "free_weekend_started"
    SCHEDULE_CHANGED = "schedule_changed"


# --- Frontend --------------------------------------------------------------------------------
FRONTEND_URL_BASE: Final = f"/{DOMAIN}_static"
FRONTEND_SCRIPT: Final = "perdis-cards.js"

# How many changes the storage keeps, and how long the change sensor shows them.
CHANGE_HISTORY_LIMIT: Final = 50
CHANGE_DISPLAY_DAYS: Final = 14


def default_time_zone():
    """Home Assistant's configured default time zone, across core versions.

    ``dt_util.get_default_time_zone()`` only exists from Home Assistant 2024.6; older cores expose
    the same value as the module attribute ``DEFAULT_TIME_ZONE``. Imported lazily so this module
    stays free of Home Assistant for the parser unit tests.
    """
    from homeassistant.util import dt as dt_util

    getter = getattr(dt_util, "get_default_time_zone", None)
    return getter() if getter else dt_util.DEFAULT_TIME_ZONE

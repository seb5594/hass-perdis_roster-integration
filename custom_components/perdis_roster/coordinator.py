"""The coordinator: refreshes the roster, keeps the cache, detects changes and announces moments.

One refresh per scan interval asks the portal. Everything time related (the countdown to the
next shift, "on duty", the wake-up time) is recalculated once a minute from the cached data
without any network traffic, and the moments of the timeline (wake up, shift start, ...) are
announced at the exact second through timers instead of polling.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import inspect
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_point_in_time, async_track_time_change
from homeassistant.helpers.script import Script
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PerdisAuthError, PerdisError, PortalClient
from .capabilities import detect as detect_capabilities
from .changes import changes_since, describe, detect_changes, keep_recent, texts
from .const import (
    CHANGE_DISPLAY_DAYS,
    CHANGE_HISTORY_LIMIT,
    CONF_COMMUTE,
    CONF_LOOKAHEAD_DAYS,
    CONF_LOOKBACK_DAYS,
    CONF_MINIMUM_REST,
    CONF_NOTIFY_ACTION,
    CONF_NOTIFY_CHANGES,
    CONF_NOTIFY_TARGET,
    CONF_PERSON,
    CONF_SCAN_INTERVAL,
    CONF_WAKE_UP_LEAD,
    DEFAULT_COMMUTE,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MINIMUM_REST,
    DEFAULT_NOTIFY_CHANGES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_UP_LEAD,
    DOMAIN,
    EVENT_PERDIS,
    TimelineEvent,
    default_time_zone,
)
from .insights import InsightSettings, RosterInsights
from .models import Duty, DutySwap, ScheduleChange, Snapshot
from .storage import PerdisStore, StoredState

_LOGGER = logging.getLogger(__name__)

TIMELINE_HORIZON = timedelta(hours=36)  # timers further ahead are set by a later refresh


@dataclass(slots=True)
class PerdisData:
    """What the entities read: the roster, its change history and the state of the portal."""

    snapshot: Snapshot | None
    changes: list[ScheduleChange] = field(default_factory=list)
    online: bool = True
    last_error: str | None = None
    last_success: datetime | None = None

    @property
    def recent_changes(self) -> list[ScheduleChange]:
        return changes_since(self.changes, dt_util.now() - timedelta(days=CHANGE_DISPLAY_DAYS))


# A typed config entry whose `runtime_data` is the coordinator. The subscripted form needs Home
# Assistant 2024.5 and Python 3.12, so it is only used for type checkers; at runtime the plain
# ConfigEntry is kept, which keeps the integration importable on much older cores.
if TYPE_CHECKING:
    PerdisConfigEntry = ConfigEntry["PerdisCoordinator"]
else:
    PerdisConfigEntry = ConfigEntry


class PerdisCoordinator(DataUpdateCoordinator[PerdisData]):
    """Refreshes one Perdis account."""

    config_entry: PerdisConfigEntry

    def __init__(self, hass: HomeAssistant, entry: PerdisConfigEntry, client: PortalClient) -> None:
        # Home Assistant 2024.8 added the `config_entry` argument of the coordinator; older cores set
        # `self.config_entry` from the setup context instead, so it is only passed where it is known.
        kwargs: dict[str, Any] = {
            "name": f"{DOMAIN} {entry.title}",
            "update_interval": timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        }
        if "config_entry" in inspect.signature(DataUpdateCoordinator.__init__).parameters:
            kwargs["config_entry"] = entry
        super().__init__(hass, _LOGGER, **kwargs)
        # Newer cores store the entry on the coordinator (from the kwarg or the setup context); older
        # ones do not, so keep our own reference where it is still missing.
        if getattr(self, "config_entry", None) is None:
            self.config_entry = entry
        self.client = client
        self.capabilities: frozenset[str] = frozenset()
        self._store = PerdisStore(hass, entry.entry_id)
        self._stored = StoredState()
        self._timers: list[CALLBACK_TYPE] = []
        self._timeline_outdated = True
        self._insights: RosterInsights | None = None
        self._insights_source: Snapshot | None = None

    # --- Settings and derived information ----------------------------------------------------

    def option(self, key: str, default: Any) -> Any:
        return self.config_entry.options.get(key, default)

    @property
    def settings(self) -> InsightSettings:
        return InsightSettings(
            wake_up_lead=timedelta(minutes=self.option(CONF_WAKE_UP_LEAD, DEFAULT_WAKE_UP_LEAD)),
            commute=timedelta(minutes=self.option(CONF_COMMUTE, DEFAULT_COMMUTE)),
            minimum_rest=timedelta(hours=self.option(CONF_MINIMUM_REST, DEFAULT_MINIMUM_REST)),
        )

    @property
    def insights(self) -> RosterInsights:
        """Derived facts for the current minute, built once and shared by all entities."""
        now = dt_util.now().replace(second=0, microsecond=0)
        snapshot = self.data.snapshot if self.data else None
        if self._insights is None or self._insights.now != now or self._insights_source is not snapshot:
            self._insights = RosterInsights(snapshot, now, self.settings)
            self._insights_source = snapshot
        return self._insights

    @property
    def _snapshot(self) -> Snapshot | None:
        return self.data.snapshot if self.data else None

    @property
    def swaps(self) -> list[DutySwap]:
        """The open shift swaps the portal listed on the last refresh."""
        return self._snapshot.swaps if self._snapshot else []

    @property
    def swap_window(self) -> tuple[date, date] | None:
        """The period the portal accepts new swap requests for, if it shows one."""
        return self._snapshot.swap_window if self._snapshot else None

    @property
    def device_id(self) -> str | None:
        """The id of this account's device, looked up through its config entry."""
        devices = dr.async_entries_for_config_entry(dr.async_get(self.hass), self.config_entry.entry_id)
        return devices[0].id if devices else None

    # --- Life cycle --------------------------------------------------------------------------

    async def async_config_entry_first_refresh(self) -> None:
        # The `_async_setup` hook is only run by the coordinator itself from Home Assistant 2024.8;
        # on older cores invoke it here, so the cache and the timers are ready before the first fetch.
        if not hasattr(DataUpdateCoordinator, "_async_setup"):
            await self._async_setup()
        await super().async_config_entry_first_refresh()

    async def _async_setup(self) -> None:
        """Load the cache before the first refresh, so a portal outage does not block the start."""
        self._stored = await self._store.async_load()
        self.capabilities = self._stored.capabilities
        self.config_entry.async_on_unload(async_track_time_change(self.hass, self._async_tick, second=0))
        self.config_entry.async_on_unload(self._cancel_timers)
        self.config_entry.async_on_unload(self.async_add_listener(self._schedule_timeline))

    @callback
    def _async_tick(self, _now: datetime) -> None:
        """Once a minute: let the entities recalculate their time related values."""
        if self.data is not None:
            self.async_update_listeners()

    # --- Refresh -----------------------------------------------------------------------------

    async def _async_update_data(self) -> PerdisData:
        now = dt_util.now()
        lookahead = self.option(CONF_LOOKAHEAD_DAYS, DEFAULT_LOOKAHEAD_DAYS)
        lookback = self.option(CONF_LOOKBACK_DAYS, DEFAULT_LOOKBACK_DAYS)
        # Hand the client the shifts it already broke down, so an unchanged one is reused instead of
        # fetched again: only genuinely new or changed days then cost a detail request each refresh.
        known = {duty.day: duty for duty in self._stored.snapshot.duties if duty.segments} \
            if self._stored.snapshot else None
        try:
            fetched = await self.client.async_fetch(now.date() - timedelta(days=lookback),
                                                    now.date() + timedelta(days=lookahead), now, known)
        except PerdisAuthError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except PerdisError as error:
            if self._stored.snapshot is None:
                raise UpdateFailed(str(error)) from error
            _LOGGER.warning("Perdis portal unavailable (%s); showing the cached roster", error)
            previous = self.data
            self._timeline_outdated = True  # moments of the cached roster still deserve their timers
            return PerdisData(self._stored.snapshot, self._stored.changes, online=False, last_error=str(error),
                              last_success=previous.last_success if previous else self._stored.snapshot.fetched_at)

        previous = self._stored.snapshot
        snapshot = self._merge_history(previous, fetched, lookback)
        new_changes = detect_changes(previous, snapshot, now.date())
        # Which sensors this portal can fill is decided from the pages it served and the values
        # it returned; it only ever grows, so a temporary empty account does not drop a sensor.
        self.capabilities |= detect_capabilities(self.client.reachable_pages, snapshot)
        self._stored = StoredState(
            snapshot,
            keep_recent([*new_changes, *self._stored.changes], CHANGE_HISTORY_LIMIT),
            capabilities=self.capabilities,
        )
        await self._store.async_save(self._stored)
        if new_changes:
            self._announce_changes(new_changes)
        self._timeline_outdated = True
        return PerdisData(snapshot, self._stored.changes, online=True, last_success=now)

    def _merge_history(self, previous: Snapshot | None, fetched: Snapshot, lookback: int) -> Snapshot:
        """Keep past days the portal no longer shows, and keep the roster when a page came back empty."""
        if previous is None:
            return fetched
        if not fetched.duties and previous.duties:
            _LOGGER.warning("The portal returned an empty roster; keeping the previous one. "
                            "If this persists, set the roster page in the integration options.")
            fetched.duties = previous.duties
            return fetched
        oldest_kept = fetched.fetched_at.date() - timedelta(days=lookback)
        first_fetched = fetched.duties[0].day if fetched.duties else fetched.fetched_at.date()
        history = [duty for duty in previous.duties if oldest_kept <= duty.day < first_fetched]
        fetched.duties = [*history, *fetched.duties]
        return fetched

    # --- Announcements -----------------------------------------------------------------------

    def _announce_changes(self, changes: list[ScheduleChange]) -> None:
        language = self.hass.config.language or "en"
        lines = [describe(change, language) for change in changes]
        # Compact, e.g. "VGF - 12345: Dienstplanänderung".
        title = f"{self.config_entry.title}: {texts(language)['change_title']}"
        message = "\n".join(f"- {line}" for line in lines)
        _LOGGER.info("Roster changes detected: %s", "; ".join(describe(change) for change in changes))
        # The event lets automations react with any custom action, and carries the person entity.
        self._fire(TimelineEvent.SCHEDULE_CHANGED, {
            "changes": [change.to_dict() for change in changes],
            "summary": lines,
            "person": self.option(CONF_PERSON, None),
        })
        if self.option(CONF_NOTIFY_CHANGES, DEFAULT_NOTIFY_CHANGES):
            persistent_notification.async_create(
                self.hass, message, title=title,
                notification_id=f"{DOMAIN}_{self.config_entry.entry_id}_changes",
            )
        self._call_notify_target(title, message, lines)

    def _call_notify_target(self, title: str, message: str, lines: list[str]) -> None:
        """Run the user-configured action on a roster change, or the legacy single service."""
        variables = {
            "title": title,
            "message": message,
            "changes": lines,
            "person": self.option(CONF_PERSON, None),
            "entry_id": self.config_entry.entry_id,
        }
        action = self.option(CONF_NOTIFY_ACTION, None)
        if action:
            self._run_notify_action(action, variables)
            return
        self._call_legacy_target(title, message, lines)

    def _run_notify_action(self, action: Any, variables: dict[str, Any]) -> None:
        """Run the action built in the UI (a service call or a whole sequence) with the change data.

        The action can use `{{ title }}`, `{{ message }}`, `{{ changes }}` and `{{ person }}`.
        """
        sequence = action if isinstance(action, list) else [action]
        try:
            sequence = cv.SCRIPT_SCHEMA(sequence)
        except vol.Invalid as error:
            _LOGGER.warning("Perdis notify action is not valid: %s", error)
            return
        script = Script(self.hass, sequence, f"{DOMAIN} {self.config_entry.title}", DOMAIN)
        self.hass.async_create_task(script.async_run(variables, Context()))

    def _call_legacy_target(self, title: str, message: str, lines: list[str]) -> None:
        """The older single-service option (e.g. notify.mobile_app_*), kept for existing setups."""
        target = self.option(CONF_NOTIFY_TARGET, None)
        if not target or "." not in target:
            return
        domain, service = target.split(".", 1)
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning("Perdis notify target %s is not a known service", target)
            return
        data: dict[str, Any] = {"title": title, "message": message}
        if domain != "notify":
            data.update(changes=lines, person=self.option(CONF_PERSON, None),
                        entry_id=self.config_entry.entry_id)
        self.hass.async_create_task(self.hass.services.async_call(domain, service, data, blocking=False))

    def _fire(self, event: TimelineEvent, data: dict[str, Any] | None = None) -> None:
        self.hass.bus.async_fire(EVENT_PERDIS, {
            "entry_id": self.config_entry.entry_id,
            "device_id": self.device_id,
            "type": event.value,
            **(data or {}),
        })

    @callback
    def _schedule_timeline(self) -> None:
        """Set one timer per upcoming moment, once after every successful refresh."""
        if not self._timeline_outdated:
            return
        self._timeline_outdated = False
        self._cancel_timers()
        insights = self.insights
        now, horizon = insights.now, insights.now + TIMELINE_HORIZON
        for when, event, duty in self._timeline(insights):
            if now < when <= horizon:
                self._timers.append(async_track_point_in_time(
                    self.hass, self._timer_callback(event, duty), when))

    def _timeline(self, insights: RosterInsights) -> list[tuple[datetime, TimelineEvent, Duty | None]]:
        moments: list[tuple[datetime, TimelineEvent, Duty | None]] = []
        settings = insights.settings
        for duty in insights.duties:
            if not (duty.is_working and duty.has_times):
                continue
            moments += [
                (duty.start - settings.wake_up_lead, TimelineEvent.WAKE_UP, duty),
                (duty.start - settings.commute, TimelineEvent.LEAVE_HOME, duty),
                (duty.start, TimelineEvent.SHIFT_STARTED, duty),
                (duty.end, TimelineEvent.SHIFT_ENDED, duty),
            ]
        zone = default_time_zone()
        for saturday in insights.free_weekends:
            moments.append((datetime.combine(saturday, datetime.min.time(), zone), TimelineEvent.FREE_WEEKEND_STARTED,
                            insights.duty_on(saturday)))
        return moments

    def _timer_callback(self, event: TimelineEvent, duty: Duty | None) -> Callable[[datetime], None]:
        @callback
        def fire(_now: datetime) -> None:
            self._fire(event, {"duty": duty.to_dict() if duty else None})
            self.async_update_listeners()  # "on duty" and friends change at this very second

        return fire

    @callback
    def _cancel_timers(self) -> None:
        while self._timers:
            self._timers.pop()()


# --- Where the platforms find the coordinator ------------------------------------------------
# ConfigEntry.runtime_data would do this on Home Assistant 2024.5 and newer; a plain hass.data store
# does the same on every older core, so the integration stays compatible for years back.

def store_coordinator(hass: HomeAssistant, entry: PerdisConfigEntry, coordinator: PerdisCoordinator) -> None:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator


def coordinator_of(hass: HomeAssistant, entry: PerdisConfigEntry) -> PerdisCoordinator:
    return hass.data[DOMAIN][entry.entry_id]


def discard_coordinator(hass: HomeAssistant, entry: PerdisConfigEntry) -> None:
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

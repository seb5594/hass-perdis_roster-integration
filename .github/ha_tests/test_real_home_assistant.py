"""The integration inside a genuine Home Assistant core, against a fake WebComm portal.

They need Home Assistant and pytest-homeassistant-custom-component. The shared
engine installs both for every release the Compatibility workflow lists; to run them
locally: python .engine/.scripts/ha_matrix.py run 2026.9.4
"""

from datetime import date, datetime
from pathlib import Path

import aiohttp
from conftest import PASSWORD, USERNAME
import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

DOMAIN = next((Path(__file__).resolve().parents[2] / "custom_components").iterdir()).name
# Two o'clock in the night before the first duty of the fixtures (Monday 23 November 2026, 05:12).
NIGHT_BEFORE = "2026-11-23T01:00:00+00:00"

try:  # The options form folds the page overrides into a collapsible section where the core has one.
    from homeassistant.data_entry_flow import section as _section  # noqa: F401

    ADVANCED_OPTIONS = {"advanced": {}}
except ImportError:  # older cores show the same overrides as flat, optional fields
    ADVANCED_OPTIONS = {}


@pytest.fixture(autouse=True)
async def berlin(hass, freezer):
    """The fixtures are a roster in Europe/Berlin around 23 November 2026."""
    freezer.move_to(NIGHT_BEFORE)
    # async_set_time_zone arrived in Home Assistant 2024.6; older cores set it synchronously.
    if hasattr(hass.config, "async_set_time_zone"):
        await hass.config.async_set_time_zone("Europe/Berlin")
    else:
        await hass.async_add_executor_job(hass.config.set_time_zone, "Europe/Berlin")


async def add_account(hass, portal, password=PASSWORD):
    """Walk through the setup dialog with the manual address of the fake portal."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "menu"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
    assert result["step_id"] == "manual"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"base_url": portal.url, "portal_type": "webcomm", "verify_ssl": True})
    assert result["step_id"] == "credentials"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": USERNAME, "password": password})


def state_of(hass, platform, key):
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{entry_of(hass).entry_id}_{key}")
    return hass.states.get(entity_id) if entity_id else None


def entry_of(hass):
    return hass.config_entries.async_entries(DOMAIN)[0]


async def _calendar_description(hass, start_day, end_day):
    """The first calendar event's description in a day range, however the core exposes events.

    The `calendar.get_events` service only arrived in Home Assistant 2024.1; on older cores the
    calendar entity is read directly, so the same test runs across the whole supported range.
    """
    entity_id = state_of(hass, "calendar", "duties").entity_id
    if hass.services.has_service("calendar", "get_events"):
        events = await hass.services.async_call(
            "calendar", "get_events",
            {"entity_id": entity_id, "start_date_time": f"{start_day}T00:00:00",
             "end_date_time": f"{end_day}T00:00:00"},
            blocking=True, return_response=True)
        return next(iter(events.values()))["events"][0]["description"]
    entity = hass.data["entity_components"]["calendar"].get_entity(entity_id)
    zone = dt_util.DEFAULT_TIME_ZONE
    found = await entity.async_get_events(
        hass, datetime.fromisoformat(f"{start_day}T00:00:00").replace(tzinfo=zone),
        datetime.fromisoformat(f"{end_day}T00:00:00").replace(tzinfo=zone))
    return found[0].description


async def test_setup_dialog_offers_the_known_operators(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "operator"})
    options = result["data_schema"].schema["operator"].config["options"]
    assert {"rheinbahn", "bogestra", "rnv"} <= {option["value"] for option in options}


def test_surname_is_read_from_any_header_order():
    from custom_components.perdis_roster.config_flow import employee_surname

    assert employee_surname("Max Mustermann (4711)") == "Mustermann"
    assert employee_surname("Mustermann,Max") == "Mustermann"
    assert employee_surname("12345 Mustermann,Max") == "Mustermann"
    assert employee_surname("4711") is None  # a bare number is not a name
    assert employee_surname(None) is None


async def test_wrong_password_is_reported_in_the_dialog(hass, fake_webcomm):
    result = await add_account(hass, fake_webcomm, password="wrong")
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_account_is_set_up_and_reads_the_roster(hass, fake_webcomm):
    result = await add_account(hass, fake_webcomm)
    assert result["type"] == "create_entry"
    # The entry is titled "<personnel number> - <surname>", read from login and the portal header.
    assert result["title"] == "4711 - Mustermann"
    assert result["data"]["base_url"] == fake_webcomm.url
    await hass.async_block_till_done()
    assert entry_of(hass).state is ConfigEntryState.LOADED

    assert state_of(hass, "sensor", "next_shift").state == "4711"
    assert state_of(hass, "sensor", "next_shift_category").state == "early"
    assert state_of(hass, "sensor", "today").state == "work"
    assert state_of(hass, "sensor", "next_day_off").state == "2026-11-26"
    assert state_of(hass, "sensor", "next_free_weekend").state == "2026-11-28"
    assert float(state_of(hass, "sensor", "overtime").state) == 14.5
    assert float(state_of(hass, "sensor", "vacation_remaining").state) == 12.5
    assert float(state_of(hass, "sensor", "weekend_points_difference").state) == -3.5
    assert state_of(hass, "binary_sensor", "on_duty").state == "off"
    roster = state_of(hass, "sensor", "roster")
    assert roster.attributes["perdis_role"] == "roster"
    # Both roster months were read: the December page sits behind the "next" button.
    assert roster.attributes["days"][-1]["date"] == "2026-12-06"
    assert state_of(hass, "calendar", "duties") is not None

    assert await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_get_duties_service_returns_the_days(hass, fake_webcomm):
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        DOMAIN, "get_duties", {"start_date": "2026-11-23", "end_date": "2026-11-26"}, blocking=True,
        return_response=True)
    duties = response["accounts"][0]["duties"]
    assert [duty["day"] for duty in duties] == ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26"]
    assert duties[2]["split"] is True
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_device_offers_the_timeline_triggers(hass, fake_webcomm):
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()
    from custom_components.perdis_roster.device_trigger import async_get_triggers

    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry_of(hass).entry_id)[0]
    types = {trigger["type"] for trigger in await async_get_triggers(hass, device.id)}
    assert {"wake_up", "leave_home", "shift_started", "shift_ended", "schedule_changed"} <= types
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_wake_up_is_announced_on_time(hass, fake_webcomm, freezer):
    events = []
    hass.bus.async_listen(f"{DOMAIN}_event", events.append)
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()
    wake_up = dt_util.parse_datetime("2026-11-23T03:42:00+01:00")
    freezer.move_to(wake_up)
    async_fire_time_changed(hass, wake_up)
    await hass.async_block_till_done()
    assert [event.data["type"] for event in events] == ["wake_up"]
    assert events[0].data["duty"]["code"] == "4711"
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_new_password_through_reauth(hass, fake_webcomm):
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()
    entry = entry_of(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=dict(entry.data))
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": PASSWORD})
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_client_signs_in_again_when_the_session_expires(hass, fake_webcomm):
    from custom_components.perdis_roster.api import PerdisAuthError, create_client
    from custom_components.perdis_roster.const import PortalType, default_time_zone

    zone = default_time_zone()
    now = dt_util.now()
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        client = create_client(PortalType.WEBCOMM, session, fake_webcomm.url, USERNAME, PASSWORD, zone)
        snapshot = await client.async_fetch(date(2026, 11, 16), date(2026, 12, 31), now)
        assert snapshot.balances.overtime_minutes == 870
        fake_webcomm.sessions.clear()  # the portal forgets every session
        snapshot = await client.async_fetch(date(2026, 11, 16), date(2026, 12, 31), now)
        assert len(snapshot.duties) == 12
        assert fake_webcomm.logins == 2
        assert client.discovered_pages["roster"].endswith("/WebComm/Dienstplan.aspx")

    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        wrong = create_client(PortalType.WEBCOMM, session, fake_webcomm.url, USERNAME, "nope", zone)
        with pytest.raises(PerdisAuthError, match="Anmeldung fehlgeschlagen"):
            await wrong.async_login()


async def test_options_are_saved_and_reload_the_account(hass, fake_webcomm):
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()
    entry = entry_of(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "wake_up_lead_minutes": 60, "commute_minutes": 20, "minimum_rest_hours": 11, "notify_changes": False,
        "scan_interval": 30, "lookahead_days": 42, "lookback_days": 7, **ADVANCED_OPTIONS,
    })
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert state_of(hass, "sensor", "wake_up").state == "2026-11-23T03:12:00+00:00"
    await hass.config_entries.async_unload(entry.entry_id)


async def add_account_for(hass, portal):
    """Walk through the manual setup for a given fake portal and return the flow result."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"base_url": portal.url, "portal_type": "webcomm", "verify_ssl": True})
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": USERNAME, "password": PASSWORD})


async def test_a_roster_only_portal_hides_the_account_sensors(hass, fake_webcomm_roster_only):
    await add_account_for(hass, fake_webcomm_roster_only)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry_of(hass).entry_id]
    assert "roster" in coordinator.capabilities
    assert "overtime" not in coordinator.capabilities
    assert "weekend_points" not in coordinator.capabilities

    # The roster sensors are there, the account sensors the portal cannot fill are not created.
    assert state_of(hass, "sensor", "next_shift").state == "4711"
    assert state_of(hass, "sensor", "overtime") is None
    assert state_of(hass, "sensor", "vacation_remaining") is None
    assert state_of(hass, "sensor", "weekend_points") is None
    assert state_of(hass, "binary_sensor", "on_duty") is not None
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_calendar_portal_gets_real_times_from_shift_detail(hass, fake_webcomm_calendar):
    await add_account_for(hass, fake_webcomm_calendar)
    await hass.async_block_till_done()
    # The month calendar lists duty 3095 on the 24th with no times; the detail page fills them in.
    nxt = state_of(hass, "sensor", "next_shift")
    assert nxt.state == "3095"
    assert nxt.attributes["start"] == "2026-11-24T10:22:00+01:00"
    assert nxt.attributes["end"] == "2026-11-24T18:03:00+01:00"
    assert nxt.attributes["start_location"] == "HB"
    assert "21" in nxt.attributes["lines"] and "16" in nxt.attributes["lines"]
    # The legs ride on the sensor too, so the shift-detail card can show them as a table.
    assert len(nxt.attributes["legs"]) >= 4
    assert nxt.attributes["legs"][0]["location"] == "HB"

    # The calendar event must carry the leg-by-leg breakdown, not only the start and end.
    description = await _calendar_description(hass, "2026-11-24", "2026-11-25")
    assert "10:32-14:32" in description  # the first driving leg
    assert "21" in description and "16" in description  # both lines
    assert description.count("\n") >= 5  # several legs, each on its own line
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_detail_legs_are_added_even_when_the_roster_already_has_times(hass, fake_webcomm):
    """A table roster shows the shift's times; its legs must still come from the detail page."""
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        DOMAIN, "get_duties", {"start_date": "2026-11-24", "end_date": "2026-11-24"}, blocking=True,
        return_response=True)
    duty = response["accounts"][0]["duties"][0]
    assert duty["start"] and duty["end"]  # the roster already carried the times
    assert len(duty["segments"]) >= 4  # the legs were added from the detail page regardless
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_a_navigation_based_portal_details_next_month_shifts(hass, fake_webcomm_navigated):
    """A portal that only serves a shift's legs while its month is open must still detail next month."""
    await add_account_for(hass, fake_webcomm_navigated)
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        DOMAIN, "get_duties", {"start_date": "2026-11-23", "end_date": "2026-12-06"}, blocking=True,
        return_response=True)
    by_day = {duty["day"]: duty for duty in response["accounts"][0]["duties"]}
    # A shift this month and one next month both get their legs, because the roster is re-opened on
    # the right month before each detail page is read.
    assert by_day["2026-11-23"]["segments"]
    assert by_day["2026-12-01"]["segments"]
    await hass.config_entries.async_unload(entry_of(hass).entry_id)


async def test_open_duty_swaps_are_listed(hass, fake_webcomm):
    await add_account(hass, fake_webcomm)
    await hass.async_block_till_done()

    # The open swap and the request window show up on a sensor, gated by the swap capability.
    swaps = state_of(hass, "sensor", "duty_swaps")
    assert swaps.state == "1"
    assert swaps.attributes["swaps"][0]["id"] == "90201"
    assert swaps.attributes["swaps"][0]["duty"] == "3095"
    assert swaps.attributes["request_from"] == "2026-11-25"
    assert swaps.attributes["request_to"] == "2026-12-09"

    await hass.config_entries.async_unload(entry_of(hass).entry_id)

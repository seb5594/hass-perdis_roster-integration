"""Setup dialog: pick the transit operator (or enter the address), sign in, done.

Steps of a new account:

1. `user`        - menu: choose from the known operators, or enter the address yourself
2. `operator`    - list of operators with a public Perdis portal (see operators.py)
   `manual`      - address of the portal, the kind of portal and the certificate check
3. `credentials` - user name and password; the dialog signs in once to check them

When the password changes later, Home Assistant asks for the new one (`reauth_confirm`).
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import (
    PerdisAuthError,
    PerdisConnectionError,
    PerdisPortalError,
    create_client,
    default_path,
    normalize_base_url,
)
from .const import (
    CONF_APPCOMM_BALANCES_PATH,
    CONF_APPCOMM_LOGIN_PATH,
    CONF_APPCOMM_ROSTER_PATH,
    CONF_APPCOMM_WEEKEND_POINTS_PATH,
    CONF_BALANCES_PAGE,
    CONF_BASE_URL,
    CONF_COMMUTE,
    CONF_LOOKAHEAD_DAYS,
    CONF_LOOKBACK_DAYS,
    CONF_MINIMUM_REST,
    CONF_NOTIFY_CHANGES,
    CONF_OPERATOR,
    CONF_PORTAL_TYPE,
    CONF_ROSTER_PAGE,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    CONF_WAKE_UP_LEAD,
    CONF_WEEKEND_POINTS_PAGE,
    DEFAULT_COMMUTE,
    DEFAULT_LOOKAHEAD_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MINIMUM_REST,
    DEFAULT_NOTIFY_CHANGES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WAKE_UP_LEAD,
    DOMAIN,
    OPERATOR_CUSTOM,
    SECTION_ADVANCED,
    PortalType,
)
from .operators import OPERATORS, OPERATORS_BY_KEY, find_operator_by_url

_LOGGER = logging.getLogger(__name__)


# A personnel number the portal header often appends in brackets, e.g. "Max Mustermann (4711)".
_TRAILING_ID = re.compile(r"\s*[(\[]\s*\d{2,}\s*[)\]]\s*$")


def clean_employee_name(raw: str | None) -> str | None:
    """The plain employee name from a portal header, without a trailing personnel number."""
    if not raw:
        return None
    name = _TRAILING_ID.sub("", raw).strip()
    return name or None


async def async_check_login(hass: HomeAssistant, data: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Sign in once with throw-away cookies.

    Returns ``(error_key, employee_name)``: the error key is set for the dialog when the login
    failed, and the employee name is the one the portal greets the user with, when it shows one.
    """
    session = async_create_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True), auto_cleanup=False,
                                         cookie_jar=aiohttp.CookieJar(unsafe=True))
    client = create_client(PortalType(data[CONF_PORTAL_TYPE]), session, data[CONF_BASE_URL], data[CONF_USERNAME],
                           data[CONF_PASSWORD], dt_util.get_default_time_zone())
    try:
        await client.async_login()
    except PerdisAuthError:
        return "invalid_auth", None
    except PerdisConnectionError:
        return "cannot_connect", None
    except PerdisPortalError:
        return "not_a_portal", None
    except Exception:
        _LOGGER.exception("Unexpected error while signing in to %s", data[CONF_BASE_URL])
        return "unknown", None
    finally:
        session.detach()  # the connector is shared with Home Assistant and must stay open
    return None, clean_employee_name(client.employee_name)


def _number(minimum: float, maximum: float, step: float = 1, unit: str | None = None) -> NumberSelector:
    return NumberSelector(NumberSelectorConfig(min=minimum, max=maximum, step=step, unit_of_measurement=unit,
                                               mode=NumberSelectorMode.BOX))


WEBCOMM_ADVANCED = (CONF_ROSTER_PAGE, CONF_BALANCES_PAGE, CONF_WEEKEND_POINTS_PAGE)
APPCOMM_ADVANCED = (CONF_APPCOMM_LOGIN_PATH, CONF_APPCOMM_ROSTER_PATH, CONF_APPCOMM_BALANCES_PATH,
                    CONF_APPCOMM_WEEKEND_POINTS_PATH)
PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password"))
USERNAME = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username"))


class PerdisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adds one Perdis account."""

    VERSION = 1

    def __init__(self) -> None:
        self._portal: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["operator", "manual"])

    async def async_step_operator(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            operator = OPERATORS_BY_KEY[user_input[CONF_OPERATOR]]
            self._portal = {
                CONF_OPERATOR: operator.key,
                CONF_PORTAL_TYPE: operator.portal_type.value,
                CONF_BASE_URL: normalize_base_url(operator.url, default_path(operator.portal_type)),
                CONF_VERIFY_SSL: True,
            }
            return await self.async_step_credentials()
        options = [SelectOptionDict(value=operator.key, label=operator.label) for operator in OPERATORS]
        schema = vol.Schema({vol.Required(CONF_OPERATOR): SelectSelector(SelectSelectorConfig(
            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True))})
        return self.async_show_form(step_id="operator", data_schema=schema)

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            portal_type = PortalType(user_input[CONF_PORTAL_TYPE])
            url = normalize_base_url(user_input[CONF_BASE_URL], default_path(portal_type))
            if not url.startswith(("http://", "https://")) or "." not in url.split("/")[2]:
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                operator = find_operator_by_url(url)
                self._portal = {
                    CONF_OPERATOR: operator.key if operator else OPERATOR_CUSTOM,
                    CONF_PORTAL_TYPE: portal_type.value,
                    CONF_BASE_URL: url,
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                return await self.async_step_credentials()
        schema = vol.Schema({
            vol.Required(CONF_BASE_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(CONF_PORTAL_TYPE, default=PortalType.WEBCOMM.value): SelectSelector(SelectSelectorConfig(
                options=[portal.value for portal in PortalType], translation_key=CONF_PORTAL_TYPE,
                mode=SelectSelectorMode.LIST)),
            vol.Required(CONF_VERIFY_SSL, default=True): BooleanSelector(),
        })
        return self.async_show_form(step_id="manual", data_schema=self.add_suggested_values_to_schema(
            schema, user_input or {}), errors=errors)

    async def async_step_credentials(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            data = {**self._portal, CONF_USERNAME: username, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            await self.async_set_unique_id(f"{data[CONF_BASE_URL].split('/')[2]}|{username.lower()}")
            self._abort_if_unique_id_configured()
            error, employee = await async_check_login(self.hass, data)
            if not error:
                # Title: "Verkehrsunternehmen - Mitarbeitername", or the personnel number as a fallback.
                suffix = employee or username
                return self.async_create_entry(title=f"{self._operator_name()} - {suffix}", data=data)
            errors["base"] = error
        schema = vol.Schema({vol.Required(CONF_USERNAME): USERNAME, vol.Required(CONF_PASSWORD): PASSWORD})
        entered = {CONF_USERNAME: (user_input or {}).get(CONF_USERNAME)}  # keep the name after an error
        return self.async_show_form(
            step_id="credentials",
            data_schema=self.add_suggested_values_to_schema(schema, entered),
            errors=errors,
            description_placeholders={"operator": self._operator_name(), "url": self._portal[CONF_BASE_URL]},
        )

    def _operator_name(self) -> str:
        operator = OPERATORS_BY_KEY.get(self._portal.get(CONF_OPERATOR, ""))
        return operator.name if operator else self._portal[CONF_BASE_URL].split("/")[2]

    # --- New password --------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            error, _employee = await async_check_login(self.hass, data)
            if not error:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD}),
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME], "url": entry.data[CONF_BASE_URL]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> PerdisOptionsFlow:
        return PerdisOptionsFlow()


class PerdisOptionsFlow(OptionsFlow):
    """Personal times and, folded away, the pages of unusual portals."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        portal_type = PortalType(self.config_entry.data[CONF_PORTAL_TYPE])
        schema = vol.Schema({
            vol.Required(CONF_WAKE_UP_LEAD, default=DEFAULT_WAKE_UP_LEAD): _number(0, 360, unit="min"),
            vol.Required(CONF_COMMUTE, default=DEFAULT_COMMUTE): _number(0, 240, unit="min"),
            vol.Required(CONF_MINIMUM_REST, default=DEFAULT_MINIMUM_REST): _number(0, 24, step=0.5, unit="h"),
            vol.Required(CONF_NOTIFY_CHANGES, default=DEFAULT_NOTIFY_CHANGES): BooleanSelector(),
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _number(10, 360, unit="min"),
            vol.Required(CONF_LOOKAHEAD_DAYS, default=DEFAULT_LOOKAHEAD_DAYS): _number(7, 120, unit="d"),
            vol.Required(CONF_LOOKBACK_DAYS, default=DEFAULT_LOOKBACK_DAYS): _number(0, 60, unit="d"),
            vol.Required(SECTION_ADVANCED): section(_advanced_schema(portal_type), {"collapsed": True}),
        })
        return self.async_show_form(
            step_id="init", data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.options)
        )


def _advanced_schema(portal_type: PortalType) -> vol.Schema:
    """Page overrides of WebComm, or the endpoints of AppComm."""
    keys = APPCOMM_ADVANCED if portal_type is PortalType.APPCOMM else WEBCOMM_ADVANCED
    return vol.Schema({vol.Optional(key): TextSelector() for key in keys})

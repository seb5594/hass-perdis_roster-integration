"""Setup dialog: pick the transit operator (or enter the address), sign in, done.

Steps of a new account:

1. `user`        - menu: choose from the known operators, or enter the address yourself
2. `operator`    - list of operators with a public PERDIS portal (see operators.py)
   `manual`      - address of the portal, the kind of portal and the certificate check
3. `credentials` - user name and password; the dialog signs in once to check them

When the password changes later, Home Assistant asks for the new one (`reauth_confirm`).
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any
import unicodedata

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow

try:  # ConfigFlowResult replaced FlowResult as the flow return type in Home Assistant 2024.4.
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # pragma: no cover - older cores still call it FlowResult
    from homeassistant.data_entry_flow import FlowResult as ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
try:  # Collapsible form sections arrived in Home Assistant 2024.3.
    from homeassistant.data_entry_flow import section
except ImportError:  # pragma: no cover - only on older cores, where options stay flat
    section = None
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    ActionSelector,
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
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
    CONF_CALENDAR_LEG_EVENTS,
    CONF_COMMUTE,
    CONF_DETAIL_DAYS,
    CONF_LOOKAHEAD_DAYS,
    CONF_LOOKBACK_DAYS,
    CONF_MINIMUM_REST,
    CONF_NOTIFY_ACTION,
    CONF_NOTIFY_CHANGES,
    CONF_NOTIFY_TARGET,
    CONF_OPERATOR,
    CONF_PERSON,
    CONF_PORTAL_TYPE,
    CONF_ROSTER_PAGE,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_SSL,
    CONF_WAKE_UP_LEAD,
    CONF_WEEKEND_POINTS_PAGE,
    DEFAULT_CALENDAR_LEG_EVENTS,
    DEFAULT_COMMUTE,
    DEFAULT_DETAIL_DAYS,
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
    default_time_zone,
)
from .operators import OPERATORS, OPERATORS_BY_KEY, find_operator_by_url

_LOGGER = logging.getLogger(__name__)


# A personnel number the portal header often appends in brackets, e.g. "Max Mustermann (4711)".
_TRAILING_ID = re.compile(r"\s*[(\[]\s*\d{2,}\s*[)\]]\s*$")
# A personnel number some headers put first instead, e.g. "12345 Mustermann,Max".
_LEADING_ID = re.compile(r"^\s*\d[\d.\-/]*\s+")


def clean_employee_name(raw: str | None) -> str | None:
    """The plain employee name from a portal header, without a trailing personnel number."""
    if not raw:
        return None
    name = _TRAILING_ID.sub("", raw).strip()
    return name or None


def employee_surname(raw: str | None) -> str | None:
    """The surname from a portal header, in whichever order the portal writes the name.

    Handles "Mustermann,Max", "Max Mustermann" and "12345 Mustermann,Max": an optional personnel
    number comes first, the surname is the part before a comma, otherwise the last word.
    """
    name = clean_employee_name(raw)
    if not name:
        return None
    name = _LEADING_ID.sub("", name).strip()
    surname = (name.split(",", 1)[0] if "," in name else (name.split()[-1] if name.split() else "")).strip()
    return surname if surname and not surname.isdigit() else None


async def async_check_login(hass: HomeAssistant, data: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Sign in once with throw-away cookies.

    Returns ``(error_key, employee_name)``: the error key is set for the dialog when the login
    failed, and the employee name is the one the portal greets the user with, when it shows one.
    """
    session = async_create_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True), auto_cleanup=False,
                                         cookie_jar=aiohttp.CookieJar(unsafe=True))
    client = create_client(PortalType(data[CONF_PORTAL_TYPE]), session, data[CONF_BASE_URL], data[CONF_USERNAME],
                           data[CONF_PASSWORD], default_time_zone())
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


def _suggested_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """The saved options as form values; a service saved by an older version becomes an action.

    The notification service used to be a text field. It is shown as the equivalent action, with the
    title and message filled in, so saving the form keeps it instead of silently dropping it.
    """
    values = dict(_unfold_advanced(options))
    legacy = values.pop(CONF_NOTIFY_TARGET, None)
    if legacy and not values.get(CONF_NOTIFY_ACTION):
        values[CONF_NOTIFY_ACTION] = [{"service": legacy, "data": {"title": "{{ title }}", "message": "{{ message }}"}}]
    return values


def _sort_key(label: str) -> str:
    """Alphabetical order that files "Ü" under U instead of after Z."""
    decomposed = unicodedata.normalize("NFKD", label)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def _units(hass: HomeAssistant) -> dict[str, str]:
    """The minute/hour/day unit labels for the form, in German words where the server is German."""
    if (hass.config.language or "en").split("-")[0] == "de":
        return {"min": "Min.", "h": "Std.", "d": "Tage"}
    return {"min": "min", "h": "h", "d": "d"}


WEBCOMM_ADVANCED = (CONF_ROSTER_PAGE, CONF_BALANCES_PAGE, CONF_WEEKEND_POINTS_PAGE)
APPCOMM_ADVANCED = (CONF_APPCOMM_LOGIN_PATH, CONF_APPCOMM_ROSTER_PATH, CONF_APPCOMM_BALANCES_PATH,
                    CONF_APPCOMM_WEEKEND_POINTS_PATH)
PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password"))
USERNAME = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, autocomplete="username"))


class PerdisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adds one PERDIS account."""

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
        # Pre-sorted by label instead of the selector's own `sort=True`, which only arrived in
        # Home Assistant 2023.9, so the dropdown stays alphabetical on older cores too.
        options = sorted((SelectOptionDict(value=operator.key, label=operator.label) for operator in OPERATORS),
                         key=lambda option: _sort_key(option["label"]))
        schema = vol.Schema({vol.Required(CONF_OPERATOR): SelectSelector(SelectSelectorConfig(
            options=options, mode=SelectSelectorMode.DROPDOWN))})
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
            schema, user_input or {}), errors=errors,
            description_placeholders={"example_url": "https://perdis.example.org/WebComm/"})

    async def async_step_credentials(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            data = {**self._portal, CONF_USERNAME: username, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            await self.async_set_unique_id(f"{data[CONF_BASE_URL].split('/')[2]}|{username.lower()}")
            self._abort_if_unique_id_configured()
            error, employee = await async_check_login(self.hass, data)
            if not error:
                return self.async_create_entry(title=self._entry_title(username, employee), data=data)
            errors["base"] = error
        schema = vol.Schema({vol.Required(CONF_USERNAME): USERNAME, vol.Required(CONF_PASSWORD): PASSWORD})
        entered = {CONF_USERNAME: (user_input or {}).get(CONF_USERNAME)}  # keep the name after an error
        return self.async_show_form(
            step_id="credentials",
            data_schema=self.add_suggested_values_to_schema(schema, entered),
            errors=errors,
            description_placeholders={
                "operator": self._operator_name(),
                "url": self._portal[CONF_BASE_URL],
                # The way the portal is reached, shown right next to PERDIS in the title.
                "portal": "AppComm" if self._portal.get(CONF_PORTAL_TYPE) == PortalType.APPCOMM else "WebComm",
            },
        )

    def _operator_name(self) -> str:
        operator = OPERATORS_BY_KEY.get(self._portal.get(CONF_OPERATOR, ""))
        return operator.name if operator else self._portal[CONF_BASE_URL].split("/")[2]

    def _entry_title(self, username: str, employee: str | None) -> str:
        """The account name: "<operator short> - <personnel number>" for a known operator,
        e.g. "VGF - 12345"; otherwise "<personnel number> - <surname>", or just the number."""
        operator = OPERATORS_BY_KEY.get(self._portal.get(CONF_OPERATOR, ""))
        if operator:
            return f"{operator.short} - {username}"
        surname = employee_surname(employee)
        return f"{username} - {surname}" if surname else username

    # --- New password --------------------------------------------------------------------

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # `_get_reauth_entry()` only exists from Home Assistant 2024.12; the reauth context carries
        # the entry id on every core, so look the entry up through it instead.
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            error, _employee = await async_check_login(self.hass, data)
            if not error:
                return self._reauth_done(entry, data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD}),
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME], "url": entry.data[CONF_BASE_URL]},
        )

    def _reauth_done(self, entry, data: dict[str, Any]) -> ConfigFlowResult:
        # `async_update_reload_and_abort` only exists from Home Assistant 2024.2; older cores update,
        # reload and abort by hand for the same result.
        if hasattr(self, "async_update_reload_and_abort"):
            return self.async_update_reload_and_abort(entry, data=data)
        self.hass.config_entries.async_update_entry(entry, data=data)
        self.hass.async_create_task(self.hass.config_entries.async_reload(entry.entry_id))
        return self.async_abort(reason="reauth_successful")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> PerdisOptionsFlow:
        return PerdisOptionsFlow(config_entry)


class PerdisOptionsFlow(OptionsFlow):
    """Personal times and, folded away, the pages of unusual portals."""

    def __init__(self, config_entry) -> None:
        # Keep our own reference instead of `self.config_entry`: that attribute is only filled in
        # automatically from Home Assistant 2024.4, and assigning to it is deprecated on newer cores.
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        portal_type = PortalType(self._entry.data[CONF_PORTAL_TYPE])
        if user_input is not None:
            return self.async_create_entry(title="", data=_fold_advanced(user_input, portal_type))
        unit = _units(self.hass)
        schema = vol.Schema({
            vol.Required(CONF_WAKE_UP_LEAD, default=DEFAULT_WAKE_UP_LEAD): _number(0, 360, unit=unit["min"]),
            vol.Required(CONF_COMMUTE, default=DEFAULT_COMMUTE): _number(0, 240, unit=unit["min"]),
            vol.Required(CONF_MINIMUM_REST, default=DEFAULT_MINIMUM_REST): _number(0, 24, step=0.5, unit=unit["h"]),
            vol.Required(CONF_NOTIFY_CHANGES, default=DEFAULT_NOTIFY_CHANGES): BooleanSelector(),
            vol.Required(CONF_CALENDAR_LEG_EVENTS, default=DEFAULT_CALENDAR_LEG_EVENTS): BooleanSelector(),
            vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _number(10, 360, unit=unit["min"]),
            vol.Required(CONF_LOOKAHEAD_DAYS, default=DEFAULT_LOOKAHEAD_DAYS): _number(7, 120, unit=unit["d"]),
            vol.Required(CONF_LOOKBACK_DAYS, default=DEFAULT_LOOKBACK_DAYS): _number(0, 60, unit=unit["d"]),
            vol.Required(CONF_DETAIL_DAYS, default=DEFAULT_DETAIL_DAYS): _number(0, 120, unit=unit["d"]),
            vol.Optional(CONF_PERSON): EntitySelector(EntitySelectorConfig(domain="person")),
            # The full Home Assistant action editor: pick a service and fill its parameters in the UI,
            # or build a whole sequence. It runs on every roster change with the title, message, the
            # structured changes and the person available as variables.
            vol.Optional(CONF_NOTIFY_ACTION): ActionSelector(),
            **_advanced_part(portal_type),
        })
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, _suggested_options(self._entry.options)),
            # The template snippets are placeholders, so the frontend does not read their braces as
            # translation syntax.
            description_placeholders={
                "title_template": "`{{ title }}`",
                "message_template": "`{{ message }}`",
                "more_variables": "`{{ changes }}`, `{{ person }}`, `{{ entry_id }}`",
            },
        )


def _advanced_keys(portal_type: PortalType) -> tuple[str, ...]:
    return APPCOMM_ADVANCED if portal_type is PortalType.APPCOMM else WEBCOMM_ADVANCED


def _advanced_fields(portal_type: PortalType) -> dict[Any, Any]:
    """The page/endpoint override fields of a portal, as plain optional text inputs."""
    return {vol.Optional(key): TextSelector() for key in _advanced_keys(portal_type)}


def _advanced_part(portal_type: PortalType) -> dict[Any, Any]:
    """The advanced inputs, folded into a collapsible section where the core supports one."""
    if section is not None:
        return {vol.Required(SECTION_ADVANCED): section(vol.Schema(_advanced_fields(portal_type)),
                                                        {"collapsed": True})}
    return _advanced_fields(portal_type)  # older cores: the same inputs, just not collapsed


def _fold_advanced(user_input: dict[str, Any], portal_type: PortalType) -> dict[str, Any]:
    """On a core without sections, gather the flat advanced inputs back under their section key."""
    if section is not None or SECTION_ADVANCED in user_input:
        return user_input
    keys = _advanced_keys(portal_type)
    folded = {key: value for key, value in user_input.items() if key not in keys}
    advanced = {key: user_input[key] for key in keys if key in user_input}
    if advanced:
        folded[SECTION_ADVANCED] = advanced
    return folded


def _unfold_advanced(options: Mapping[str, Any]) -> dict[str, Any]:
    """Suggested values: on a core without sections, surface the stored advanced values flat."""
    merged = dict(options)
    if section is None and isinstance(merged.get(SECTION_ADVANCED), dict):
        merged.update(merged.pop(SECTION_ADVANCED))
    return merged

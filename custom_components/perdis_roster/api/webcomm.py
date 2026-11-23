"""Client for the classic PERDIS WebComm portal (ASP.NET WebForms in the browser).

How a WebComm portal behaves, as seen on the public login pages of several operators:

* The application lives in a folder, usually `/WebComm/`. Opening it redirects to
  `default.aspx`, first with `AspxAutoDetectCookieSupport=1` and then with `TestingCookie=1`:
  ASP.NET checks that the client keeps cookies. The session cookie is `WebComm-SID`.
* The login is an ASP.NET login control (`...$lgnLogin$UserName`, `...$Password`,
  `...$LoginButton`) inside the one page form, guarded by `__VIEWSTATE` and `__EVENTVALIDATION`.
* After the login `default.aspx` shows the menu. Its entries differ per operator and language,
  so the client finds the roster and the account pages by the words in their links.

Nothing of this is documented by INIT; the client therefore reads pages like a browser would and
never relies on fixed element ids.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
import logging
from urllib.parse import urljoin

import aiohttp

from ..models import Snapshot
from ..parsing.html import Element, PostBack, links, login_form, parse_forms, parse_html
from ..parsing.values import normalize_label
from ..parsing.webcomm import WebCommPages, WebCommParser
from .base import (
    REQUEST_TIMEOUT,
    PerdisAuthError,
    PerdisConnectionError,
    PerdisPortalError,
    PortalClient,
)

_LOGGER = logging.getLogger(__name__)

MAX_ROSTER_PAGES = 4  # the current period plus up to three "next" pages (months or weeks)

# Words in menu links, per page kind, in German, English and Dutch.
PAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "roster": ("dienstplan", "monatsplan", "mein plan", "meine dienste", "diensteinteilung", "dienstübersicht",
               "einsatzplan", "fahrplan", "duty", "roster", "schedule", "rooster", "dienstrooster", "planung"),
    "balances": ("salden", "saldo", "konten", "konto", "zeitkonten", "stundenkonto", "balances", "accounts",
                 "tegoeden", "saldi"),
    "weekend_points": ("we-punkte", "we punkte", "wochenendpunkte", "wochenende", "punkte", "weekend points",
                       "weekendpunten"),
}
NEXT_PERIOD_SYMBOLS = (">", ">>", "»", "›", "→")
NEXT_PERIOD_WORDS = ("vor", "weiter", "nächste", "naechste", "next", "volgende", "später")
NEXT_PERIOD_TARGETS = ("next", "vor", "weiter", "nextmonth", "btnnext")
ERROR_ELEMENT_IDS = ("errorMessage", "FailureText", "lblError", "lblMessage", "meldung")
LOCKED_WORDS = ("gesperrt", "locked", "geblokkeerd", "blocked")


@dataclass(slots=True)
class _Page:
    url: str
    html: str
    document: Element

    @property
    def asks_for_password(self) -> bool:
        return login_form(self.document) is not None


class WebCommClient(PortalClient):
    """Signs in to WebComm, finds the pages of interest and reads them."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
        zone,
        page_overrides: dict[str, str] | None = None,
    ) -> None:
        super().__init__(session, base_url, username, password)
        self._parser = WebCommParser(zone)
        self._overrides = {kind: path for kind, path in (page_overrides or {}).items() if path}
        self._pages: dict[str, str] = {}
        self._menu_html = ""
        self._signed_in = False
        self._lock = asyncio.Lock()

    @property
    def discovered_pages(self) -> dict[str, str]:
        return dict(self._pages)

    # --- Sign-in -----------------------------------------------------------------------------

    async def async_login(self) -> None:
        start = await self._get(self.base_url)
        if not start.asks_for_password:  # still signed in from an earlier session
            self._remember_menu(start)
            return
        form = login_form(start.document)
        if not form or not form.username_field:
            raise PerdisPortalError("The portal shows no login form with a user name field")
        fields = dict(form.fields)
        fields[form.username_field] = self._username
        fields[form.password_field] = self._password
        if form.submit:
            fields[form.submit[0]] = form.submit[1]
        answer = await self._post(urljoin(start.url, form.action or start.url), fields)
        if answer.asks_for_password:
            message = _error_text(answer.document)
            if any(word in message.lower() for word in LOCKED_WORDS):
                raise PerdisAuthError(f"The portal locked the account: {message}")
            raise PerdisAuthError(message or "The portal did not accept the user name or password")
        self._remember_menu(answer)
        _LOGGER.debug("Signed in to %s, menu pages: %s", self.base_url, self._pages)

    def _remember_menu(self, page: _Page) -> None:
        self._signed_in = True
        self._menu_html = page.html
        self._pages = self._find_pages(page)

    def _find_pages(self, menu: _Page) -> dict[str, str]:
        """Kind -> absolute URL, from the overrides first and from the menu links otherwise."""
        found = {kind: urljoin(self.base_url, path) for kind, path in self._overrides.items()}
        for text, href in links(menu.document):
            label = normalize_label(text)
            for kind, keywords in PAGE_KEYWORDS.items():
                if kind not in found and any(keyword in label for keyword in keywords):
                    found[kind] = urljoin(menu.url, href)
                    break
        return found

    # --- Reading -----------------------------------------------------------------------------

    async def async_fetch(self, start: date, end: date, now: datetime) -> Snapshot:
        async with self._lock:  # one portal session, one request sequence at a time
            if not self._signed_in:
                await self.async_login()
            pages = WebCommPages(menu=self._menu_html)
            if "roster" not in self._pages:
                _LOGGER.warning("No roster page found in the WebComm menu of %s; set it in the options", self.base_url)
            else:
                pages.roster = await self._roster_pages(self._pages["roster"], end, now.date())
            for kind in ("balances", "weekend_points"):
                if kind in self._pages:
                    try:
                        setattr(pages, kind, (await self._get_signed_in(self._pages[kind])).html)
                    except PerdisConnectionError as error:  # optional pages must not fail the update
                        _LOGGER.debug("Optional page %s unavailable: %s", kind, error)
        return self._parser.parse(pages, now)

    async def _roster_pages(self, url: str, end: date, today: date) -> list[str]:
        """The roster page and, while it ends before `end`, the following periods."""
        page = await self._get_signed_in(url)
        collected = [page.html]
        for _ in range(MAX_ROSTER_PAGES - 1):
            last_day = max((duty.day for duty in self._parser.parse_roster(page.html, today)), default=None)
            control = _next_period_control(page.document)
            if last_day is None or last_day >= end or control is None:
                break
            page = await self._postback(page, control)
            if page.html in collected:
                break
            collected.append(page.html)
        return collected

    async def _get_signed_in(self, url: str) -> _Page:
        """GET a page; when the session has expired, sign in again once and repeat."""
        page = await self._get(url)
        if page.asks_for_password:
            _LOGGER.debug("WebComm session expired, signing in again")
            self._signed_in = False
            await self.async_login()
            page = await self._get(url)
            if page.asks_for_password:
                raise PerdisAuthError("The portal asks for the password again right after signing in")
        return page

    async def _postback(self, page: _Page, control: PostBack) -> _Page:
        """Submit the page form the way clicking `control` in the browser would."""
        form = next(iter(parse_forms(page.document)), None)
        if form is None:
            raise PerdisPortalError("The roster page has no form to change the period")
        fields = dict(form.fields)
        if control.is_button:
            fields[control.target] = control.value
            fields.setdefault("__EVENTTARGET", "")
            fields.setdefault("__EVENTARGUMENT", "")
        else:
            fields["__EVENTTARGET"] = control.target
            fields["__EVENTARGUMENT"] = control.argument
        return await self._post(urljoin(page.url, form.action or page.url), fields)

    # --- HTTP --------------------------------------------------------------------------------

    async def _get(self, url: str) -> _Page:
        return await self._request("GET", url)

    async def _post(self, url: str, fields: dict[str, str]) -> _Page:
        return await self._request("POST", url, data=fields)

    async def _request(self, method: str, url: str, **kwargs) -> _Page:
        try:
            async with self._session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs) as response:
                if response.status >= 500:
                    raise PerdisConnectionError(f"{method} {url} answered HTTP {response.status}")
                if response.status in (401, 403):
                    raise PerdisAuthError(f"{method} {url} answered HTTP {response.status}")
                response.raise_for_status()
                html = await response.text(errors="replace")
                return _Page(str(response.url), html, parse_html(html))
        except aiohttp.ClientResponseError as error:
            raise PerdisConnectionError(f"{method} {url} failed: HTTP {error.status}") from error
        except (aiohttp.ClientError, TimeoutError) as error:
            raise PerdisConnectionError(f"{method} {url} failed: {error!r}") from error


def _error_text(document: Element) -> str:
    """The message a login page shows after a failed attempt."""
    wanted = tuple(element_id.lower() for element_id in ERROR_ELEMENT_IDS)
    for element in document.find_all(where=lambda e: any(part in e.get("id").lower() for part in wanted)):
        if element.text():
            return element.text()
    return ""


def _next_period_control(document: Element) -> PostBack | None:
    """The button or link that shows the next month or week of the roster."""
    for form in parse_forms(document):
        for control in form.postbacks:
            words = normalize_label(control.text).split()
            if (control.text.strip() in NEXT_PERIOD_SYMBOLS
                    or any(word in words for word in NEXT_PERIOD_WORDS)
                    or control.target.lower().endswith(NEXT_PERIOD_TARGETS)):
                return control
    return None

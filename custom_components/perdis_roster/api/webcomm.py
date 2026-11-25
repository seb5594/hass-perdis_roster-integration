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
from datetime import date, datetime, timedelta
import logging
from urllib.parse import urljoin

import aiohttp

from ..models import Duty, DutyType, Snapshot
from ..parsing.dutyswap import parse_duty_swaps, parse_swap_window
from ..parsing.html import Element, PostBack, links, login_form, parse_forms, parse_html
from ..parsing.values import normalize_label
from ..parsing.shift_detail import ShiftDetail, parse_shift_detail
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
    "roster": (
        "dienstplan", "monatsplan", "mein plan", "meine dienste", "diensteinteilung",
        "dienstübersicht", "einsatzplan", "fahrplan", "duty", "roster", "schedule",
        "rooster", "dienstrooster", "planung",
    ),
    "balances": (
        "salden", "saldo", "konten", "konto", "zeitkonten", "stundenkonto", "summen",
        "balances", "accounts", "tegoeden", "saldi", "totals",
    ),
    "daily_values": (
        "tageswerte", "tageskonto", "tagesbilanz", "tagessalden", "tagesübersicht",
        "daily", "daily values", "dagwaarden", "dagoverzicht",
    ),
    "vacation": (
        "urlaub", "resturlaub", "urlaubskonto", "plansalden", "leave", "vacation", "verlof",
    ),
    "weekend_points": (
        "we-punkte", "we punkte", "wochenendpunkte", "wochenende", "punkte",
        "weekend points", "weekendpunten",
    ),
    "dutyswap": (
        "dienst tauschen", "diensttausch", "tauschen", "tausch", "swap", "duty swap",
        "shift swap", "dienstruil", "ruilen",
    ),
}
# Filenames WebComm uses regardless of the portal's menu language. They are tried when the menu
# did not reveal a page of that kind, so a portal whose menu labels we do not recognise still works.
CANONICAL_PAGES: dict[str, str] = {
    "roster": "roster.aspx",
    "balances": "balances.aspx",
    "daily_values": "dailybal.aspx",
    "vacation": "holidays.aspx",
    "weekend_points": "wepunkte.aspx",
    "dutyswap": "dutyswap.aspx",
}
# The roster page accepts the month as a query string, e.g. roster.aspx?2026-11-01.
CANONICAL_ROSTER = "roster.aspx"
# Each shift's detail page (its legs with real times) answers at shift.aspx?YYYY-MM-DD.
CANONICAL_SHIFT = "shift.aspx"
MAX_DETAIL_FETCHES = 16  # a hard ceiling on detail pages fetched per refresh
# When the month roster already carries the times but a working day's detail page serves no leg
# table, the portal simply has no per-shift breakdown: stop probing after this many such misses so
# we do not fetch a detail page for every working day on every refresh.
MAX_DETAIL_MISSES = 2
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
        detail_days: int = 0,
    ) -> None:
        super().__init__(session, base_url, username, password)
        self._zone = zone
        self._parser = WebCommParser(zone)
        self._overrides = {kind: path for kind, path in (page_overrides or {}).items() if path}
        self._detail_days = detail_days
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
        self._employee_name = self._parser.parse_employee_name(page.html) or self._employee_name

    def _find_pages(self, menu: _Page) -> dict[str, str]:
        """Kind -> absolute URL, from the options, then the menu links, then canonical filenames."""
        found = {kind: urljoin(self.base_url, path) for kind, path in self._overrides.items()}
        for text, href in links(menu.document):
            label = normalize_label(text)
            for kind, keywords in PAGE_KEYWORDS.items():
                if kind not in found and any(keyword in label for keyword in keywords):
                    found[kind] = urljoin(menu.url, href)
                    break
        # Fill the kinds the menu did not reveal with the filenames WebComm uses everywhere, so a
        # portal whose menu labels we do not recognise still gets probed. A canonical page that does
        # not exist simply answers 404 and is dropped when it is fetched.
        for kind, filename in CANONICAL_PAGES.items():
            found.setdefault(kind, urljoin(self.base_url, filename))
        return found

    # --- Reading -----------------------------------------------------------------------------

    async def async_fetch(self, start: date, end: date, now: datetime,
                          known: dict[date, Duty] | None = None) -> Snapshot:
        async with self._lock:  # one portal session, one request sequence at a time
            if not self._signed_in:
                await self.async_login()
            self._reachable = set()
            pages = WebCommPages(menu=self._menu_html)
            try:
                roster = await self._roster_pages(self._pages["roster"], start, end, now.date())
            except (KeyError, PerdisConnectionError, PerdisPortalError) as error:
                _LOGGER.warning("Perdis roster page unavailable for %s (%s); set it in the options",
                                self.base_url, error)
            else:
                pages.roster = roster
                self._reachable.add("roster")
            for kind in ("balances", "daily_values", "vacation", "weekend_points"):
                if kind not in self._pages:
                    continue
                try:
                    page = await self._get_signed_in(self._pages[kind])
                except (PerdisConnectionError, PerdisPortalError) as error:  # optional pages
                    _LOGGER.debug("Optional page %s unavailable: %s", kind, error)
                    continue
                setattr(pages, kind, page.html)
                self._reachable.add(kind)
            snapshot = self._parser.parse(pages, now)
            await self._enrich_with_details(snapshot, now.date(), known or {})
            await self._read_swaps(snapshot, now.date())
        return snapshot

    async def _read_swaps(self, snapshot: Snapshot, today: date) -> None:
        """Read the open shift swaps and the period the portal accepts swap requests for."""
        url = self._pages.get("dutyswap")
        if not url:
            return
        try:
            page = await self._get_signed_in(url)
        except (PerdisConnectionError, PerdisPortalError) as error:  # the portal has no swap page
            _LOGGER.debug("Duty-swap page unavailable: %s", error)
            return
        snapshot.swaps = parse_duty_swaps(page.html, today)
        snapshot.swap_window = parse_swap_window(page.html, today)
        self._reachable.add("dutyswap")

    async def _enrich_with_details(self, snapshot: Snapshot, today: date, known: dict[date, Duty]) -> None:
        """Fill in — and, where the month overview dropped a day, recover — every upcoming shift.

        The month roster gives at most a duty number and a start and end, and now and then it drops a
        working day from its grid altogether: ASP.NET renders the odd day without the usual link, so
        for instance tomorrow's shift can be missing from the overview entirely. Both are cured the
        same way, by doing exactly what a driver does in the browser — open the day's roster
        (``roster.aspx?YYYY-MM-DD``) and then its shift page (``shift.aspx?YYYY-MM-DD``). The
        navigated roster still lists the day the overview left out and carries its duty number, and
        the shift page adds the real reporting points, lines, courses and legs.

        Only the near-term window is walked, one day at a time. A day already broken down on an
        earlier refresh is reused without a request — so the whole window (next month included) stays
        detailed while only new or changed days cost anything, and a remembered shift keeps a day on
        the roster even once the overview drops it. A per-refresh ceiling spreads the first fill over
        a few refreshes, and days off and absences, which have no shift page, are left untouched.
        """
        if self._detail_days <= 0 or "roster" not in self._pages:
            return
        roster_url = self._pages["roster"]
        detail_url = urljoin(roster_url, CANONICAL_SHIFT)
        by_day = {duty.day: duty for duty in snapshot.duties}
        fetched = misses = 0
        active_month: date | None = None
        for current in _days(today - timedelta(days=1), today + timedelta(days=self._detail_days)):
            existing = by_day.get(current)
            # A day off or an absence (sick, vacation) has no per-leg page; a shift already broken
            # down needs nothing more. Everything else is a working day to detail — or a gap to fill.
            if existing is not None and (not existing.is_working or existing.segments):
                continue
            previous = known.get(current)
            if previous is not None and previous.segments and (existing is None or previous.code == existing.code):
                # The same shift was detailed on an earlier refresh: reuse it, no request. When the
                # overview has since dropped the day, the remembered shift keeps it on the roster.
                by_day[current] = _reuse_detail(previous, existing)
                continue
            if fetched >= MAX_DETAIL_FETCHES or misses >= MAX_DETAIL_MISSES:
                continue
            month = current.replace(day=1)
            if existing is None:
                # Missing from the overview: open the day (which also puts its month in context) and
                # read it straight from the navigated roster, number and all.
                existing = await self._roster_day(roster_url, current)
                active_month = month
            elif month != active_month:
                # The portal serves a shift's detail only once its month's roster is open.
                await self._open_roster_month(roster_url, current)
                active_month = month
            try:
                page = await self._get_signed_in(f"{detail_url}?{current.isoformat()}")
            except (PerdisConnectionError, PerdisPortalError) as error:
                _LOGGER.debug("Shift detail for %s unavailable: %s", current, error)
                continue
            fetched += 1
            detail = parse_shift_detail(page.html, current, self._zone)
            if detail.has_times:
                duty = existing if existing is not None else Duty(day=current, duty_type=DutyType.WORK)
                detail.apply_to(duty)
                by_day[current] = duty
            elif existing is not None and existing.duty_type is DutyType.WORK and existing.has_times:
                _LOGGER.debug("Shift %s on %s has no leg table on its detail page", existing.code, current)
                # A real shift with times whose detail page carries no legs: the portal offers no
                # per-shift breakdown, so stop probing it after a couple of such misses.
                misses += 1
        snapshot.duties = sorted(by_day.values(), key=lambda duty: duty.day)

    async def _open_roster_month(self, roster_url: str, day: date) -> None:
        """Open the roster on `day` (roster.aspx?YYYY-MM-DD) so that day's shift detail is served."""
        try:
            await self._get_signed_in(f"{roster_url}?{day.isoformat()}")
        except (PerdisConnectionError, PerdisPortalError) as error:
            _LOGGER.debug("Could not open the roster on %s before reading its shift: %s", day, error)

    async def _roster_day(self, roster_url: str, day: date) -> Duty | None:
        """Open ``roster.aspx?YYYY-MM-DD`` (as clicking the day does) and return that day's entry.

        This both puts the day's month in context for its shift page and reads the day from the
        navigated roster, which still lists it — number and all — when the month overview left it out.
        """
        try:
            page = await self._get_signed_in(f"{roster_url}?{day.isoformat()}")
        except (PerdisConnectionError, PerdisPortalError) as error:
            _LOGGER.debug("Could not open the roster on %s: %s", day, error)
            return None
        return next((duty for duty in self._parser.parse_roster(page.html, day) if duty.day == day), None)

    async def _roster_pages(self, url: str, start: date, end: date, today: date) -> list[str]:
        """The roster HTML for the needed months: by month query string, or by paging through it."""
        if url.lower().rstrip("/").endswith(CANONICAL_ROSTER):
            months = await self._roster_months(url, start, end)
            if months:
                return months
        return await self._roster_by_postback(url, end, today)

    async def _roster_months(self, url: str, start: date, end: date) -> list[str]:
        """Fetch roster.aspx?YYYY-MM-01 for each month between `start` and `end`."""
        pages: list[str] = []
        month = start.replace(day=1)
        last = end.replace(day=1)
        while month <= last and len(pages) <= MAX_ROSTER_PAGES:
            page = await self._get_signed_in(f"{url}?{month.isoformat()}")
            pages.append(page.html)
            month = (month + timedelta(days=32)).replace(day=1)
        return pages

    async def _roster_by_postback(self, url: str, end: date, today: date) -> list[str]:
        """The roster page and, while it ends before `end`, the periods reached by its next button."""
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


def _days(start: date, end: date) -> list[date]:
    """Every date from `start` to `end`, inclusive."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _reuse_detail(previous: Duty, existing: Duty | None) -> Duty:
    """Carry a shift detailed on an earlier refresh over to this one.

    When the overview still lists the day, its fresh entry is enriched in place; when the overview
    has dropped the day, the remembered entry stands in for it so the shift stays on the roster.
    """
    if existing is None:
        return previous
    ShiftDetail(list(previous.segments)).apply_to(existing)
    return existing


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

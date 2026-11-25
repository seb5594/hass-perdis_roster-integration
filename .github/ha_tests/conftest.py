"""Shared helpers for the tests inside a real Home Assistant core.

`fake_webcomm` starts a small web server that behaves like a PERDIS WebComm portal: the cookie
check redirects of ASP.NET, the login form with view state, the menu, two roster months behind
a "next" button, the accounts and the weekend points. The pages come from the fixtures of the
regular tests.
"""

from __future__ import annotations

from pathlib import Path

from aiohttp import web
from homeassistant.setup import async_setup_component
import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
USERNAME, PASSWORD = "4711", "secret"
SESSION_COOKIE = "WebComm-SID"
USER_FIELD = "ctl00$cntMainBody$lgnView$lgnLogin$UserName"
PASSWORD_FIELD = "ctl00$cntMainBody$lgnView$lgnLogin$Password"


def page(name: str, **values: str) -> str:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return text.replace("{error}", values.get("error", ""))


class FakeWebComm:
    """State of the fake portal, so tests can expire the session or count requests."""

    def __init__(self, accounts: bool = True, calendar: bool = False, swaps: bool = True,
                 navigated: bool = False, dropped: bool = False) -> None:
        self.sessions: set[str] = set()
        self.logins = 0
        self.accounts = accounts  # a roster-only portal that serves no account pages
        self.calendar = calendar  # a portal that renders roster.aspx as a month calendar
        # A navigation-based portal: a shift's detail page only carries its legs while that day's
        # month is the roster month currently open in the session (roster.aspx?YYYY-MM-DD).
        self.navigated = navigated
        # A portal whose month overview drops one working day (the 24th): only opening that day's
        # own roster, roster.aspx?2026-11-24, brings it back.
        self.dropped = dropped
        self.open_month: str | None = None
        self.swap_posts: list[dict] = []  # every form a test submitted to the duty-swap page
        self.app = web.Application()
        self.app.router.add_get("/WebComm/", self.root)
        self.app.router.add_route("*", "/WebComm/default.aspx", self.default)
        self.app.router.add_route("*", "/WebComm/Dienstplan.aspx", self.roster)
        self.app.router.add_route("*", "/WebComm/roster.aspx", self._roster_handler())
        self.app.router.add_get("/WebComm/shift.aspx", self.shift)
        if swaps:
            self.app.router.add_route("*", "/WebComm/dutyswap.aspx", self.dutyswap)
        if accounts:
            self.app.router.add_get("/WebComm/Salden.aspx", self.protected("webcomm_balances.html"))
            self.app.router.add_get("/WebComm/WEPunkte.aspx", self.protected("webcomm_weekend_points.html"))

    async def dutyswap(self, request: web.Request) -> web.Response:
        if not self.signed_in(request):
            raise web.HTTPFound("/WebComm/default.aspx")
        if request.method == "POST":
            self.swap_posts.append(dict(await request.post()))
        return web.Response(text=page("webcomm_dutyswap.html"), content_type="text/html")

    def signed_in(self, request: web.Request) -> bool:
        return request.cookies.get(SESSION_COOKIE) in self.sessions

    def _roster_handler(self):
        if self.dropped:
            return self.dropped_roster
        return self.navigated_roster if self.navigated else self.calendar_roster

    @property
    def menu(self) -> str:
        if self.calendar or self.navigated or self.dropped:
            return page("webcomm_menu_roster_aspx.html")
        return page("webcomm_menu.html" if self.accounts else "webcomm_menu_roster_only.html")

    async def calendar_roster(self, request: web.Request) -> web.Response:
        if not self.signed_in(request):
            raise web.HTTPFound("/WebComm/default.aspx")
        return web.Response(text=page("webcomm_roster_calendar_live.html"), content_type="text/html")

    async def dropped_roster(self, request: web.Request) -> web.Response:
        """roster.aspx: the month overview drops the 24th; roster.aspx?2026-11-24 lists it again."""
        if not self.signed_in(request):
            raise web.HTTPFound("/WebComm/default.aspx")
        if len(request.query_string) >= 7:
            self.open_month = request.query_string[:7]  # "2026-11"
        name = ("webcomm_roster_day_24.html" if request.query_string == "2026-11-24"
                else "webcomm_roster_calendar_dropped.html")
        return web.Response(text=page(name), content_type="text/html")

    async def navigated_roster(self, request: web.Request) -> web.Response:
        """roster.aspx?YYYY-MM-DD: opens that day's month and remembers it for the shift pages."""
        if not self.signed_in(request):
            raise web.HTTPFound("/WebComm/default.aspx")
        if len(request.query_string) >= 7:
            self.open_month = request.query_string[:7]  # "2026-12"
        name = "webcomm_roster_december.html" if self.open_month == "2026-12" else "webcomm_roster_november.html"
        return web.Response(text=page(name), content_type="text/html")

    async def shift(self, request: web.Request) -> web.Response:
        if not self.signed_in(request):
            raise web.HTTPFound("/WebComm/default.aspx")
        if self.dropped:
            # Only the dropped 24th is a working day; its legs are served once its day was opened.
            has_legs = request.query_string == "2026-11-24" and self.open_month == "2026-11"
        elif self.navigated:
            # Legs only while this day's month is the open roster month, as the real portal does.
            has_legs = bool(self.open_month) and request.query_string.startswith(self.open_month)
        else:
            # Only the 24th is a working day; every other day answers that the driver is absent/off.
            has_legs = request.query_string.endswith("-24")
        name = "webcomm_shift_detail.html" if has_legs else "webcomm_shift_absent.html"
        return web.Response(text=page(name), content_type="text/html")

    async def root(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/WebComm/default.aspx?AspxAutoDetectCookieSupport=1")

    async def default(self, request: web.Request) -> web.Response:
        if request.method == "POST":
            form = await request.post()
            if form.get(USER_FIELD) == USERNAME and form.get(PASSWORD_FIELD) == PASSWORD and "__VIEWSTATE" in form:
                self.logins += 1
                session = f"session-{self.logins}"
                self.sessions.add(session)
                response = web.Response(text=self.menu, content_type="text/html")
                response.set_cookie(SESSION_COOKIE, session)
                return response
            return web.Response(text=page("webcomm_login.html", error="Anmeldung fehlgeschlagen"),
                                content_type="text/html")
        if self.signed_in(request):
            return web.Response(text=self.menu, content_type="text/html")
        return web.Response(text=page("webcomm_login.html"), content_type="text/html")

    async def roster(self, request: web.Request) -> web.Response:
        if not self.signed_in(request):
            raise web.HTTPFound("/WebComm/default.aspx?ReturnUrl=%2fWebComm%2fDienstplan.aspx")
        form = await request.post() if request.method == "POST" else {}
        name = "webcomm_roster_december.html" if "ctl00$cntMainBody$btnNext" in form else "webcomm_roster_november.html"
        return web.Response(text=page(name), content_type="text/html")

    def protected(self, name: str):
        async def handler(request: web.Request) -> web.Response:
            if not self.signed_in(request):
                raise web.HTTPFound("/WebComm/default.aspx")
            return web.Response(text=page(name), content_type="text/html")

        return handler


@pytest.fixture(autouse=True)
async def web_server(hass):
    """The calendar platform needs Home Assistant's real web server, not just its name.

    The shared test plugin marks the manifest dependencies (`frontend`, `http`) as loaded without
    setting them up; `http` is set up for real here, the frontend stays out (it is never rendered).
    """
    if getattr(hass, "http", None) is None:
        hass.config.components.difference_update({"http"})
        assert await async_setup_component(hass, "http", {})


@pytest.fixture
async def fake_webcomm(socket_enabled, aiohttp_server):
    """The fake portal on 127.0.0.1; Home Assistant's test harness blocks sockets otherwise."""
    portal = FakeWebComm()
    server = await aiohttp_server(portal.app)
    portal.url = str(server.make_url("/WebComm/"))
    return portal


@pytest.fixture
async def fake_webcomm_calendar(socket_enabled, aiohttp_server):
    """A portal whose month roster is a calendar of codes; real times come from shift.aspx."""
    portal = FakeWebComm(calendar=True)
    server = await aiohttp_server(portal.app)
    portal.url = str(server.make_url("/WebComm/"))
    return portal


@pytest.fixture
async def fake_webcomm_roster_only(socket_enabled, aiohttp_server):
    """A portal that only exposes the roster, so the account sensors must stay away."""
    portal = FakeWebComm(accounts=False)
    server = await aiohttp_server(portal.app)
    portal.url = str(server.make_url("/WebComm/"))
    return portal


@pytest.fixture
async def fake_webcomm_navigated(socket_enabled, aiohttp_server):
    """A navigation-based portal: a shift's legs are only served while its month's roster is open."""
    portal = FakeWebComm(navigated=True)
    server = await aiohttp_server(portal.app)
    portal.url = str(server.make_url("/WebComm/"))
    return portal


@pytest.fixture
async def fake_webcomm_dropped(socket_enabled, aiohttp_server):
    """A portal whose month overview drops the 24th; only opening that day's roster brings it back."""
    portal = FakeWebComm(dropped=True)
    server = await aiohttp_server(portal.app)
    portal.url = str(server.make_url("/WebComm/"))
    return portal

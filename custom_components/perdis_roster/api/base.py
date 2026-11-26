"""What every portal client offers, and the errors it raises."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from ..models import Duty, Snapshot

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


class PerdisError(Exception):
    """Base class of every error the portal clients raise."""


class PerdisConnectionError(PerdisError):
    """The portal could not be reached or answered with a server error."""


class PerdisAuthError(PerdisError):
    """The portal refused the user name or password, or locked the account."""


class PerdisPortalError(PerdisError):
    """The portal answered, but with something the integration does not understand."""


class PortalClient(ABC):
    """Logs in to a PERDIS portal and reads one snapshot of the roster and the accounts."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, username: str, password: str) -> None:
        self._session = session
        self.base_url = base_url
        self._username = username
        self._password = password
        # Data categories the portal actually served on the last fetch, used to decide which
        # sensors a portal supports (see capabilities.py). A kind is one of "roster", "balances",
        # "vacation", "weekend_points".
        self._reachable: set[str] = set()
        # The signed-in employee's name, read from the portal header when it shows one.
        self._employee_name: str | None = None

    @property
    def reachable_pages(self) -> set[str]:
        """The data categories the portal served on the last successful fetch."""
        return set(self._reachable)

    @property
    def employee_name(self) -> str | None:
        """The name the portal greets the signed-in employee with, if any."""
        return self._employee_name

    @abstractmethod
    async def async_login(self) -> None:
        """Sign in; raises `PerdisAuthError` for wrong credentials."""

    @abstractmethod
    async def async_fetch(self, start: date, end: date, now: datetime,
                          known: dict[date, Duty] | None = None) -> Snapshot:
        """Read the roster between `start` and `end` and the current accounts.

        `known` carries the duties of the previous refresh keyed by day, so a client that enriches
        shifts from a detail page can reuse an unchanged breakdown instead of fetching it again.
        """

    @property
    def discovered_pages(self) -> dict[str, str]:
        """Pages the client found on its own (kind -> URL), for the diagnostics."""
        return {}


def normalize_base_url(url: str, default_path: str = "") -> str:
    """Turn whatever the user typed into the clean folder address of the portal.

    Examples, all with ``default_path="WebComm"``:

    * ``perdis.example.org``                         -> ``https://perdis.example.org/WebComm/``
    * ``https://perdis.example.org``                 -> ``https://perdis.example.org/WebComm/``
    * ``https://perdis.example.org/WebComm``         -> ``https://perdis.example.org/WebComm/``
    * ``.../WebComm/default.aspx?TestingCookie=1``   -> ``https://perdis.example.org/WebComm/``

    The portal always lives in a folder (``/WebComm/`` for the browser portal). When the folder is
    missing from the address the user pasted, it is appended, so a bare host name is enough.
    """
    cleaned = url.strip()
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"
    parts = urlsplit(cleaned)
    path = parts.path
    if path.lower().endswith((".aspx", ".html", ".htm")):
        path = path.rsplit("/", 1)[0]
    # Cookieless ASP.NET sessions put their id into the path: /WebComm/(X(1)S(abc))/default.aspx
    segments = [part for part in path.split("/") if part and not part.startswith("(")]
    # Append the portal folder when it is not already the last segment (case-insensitive).
    wanted = default_path.strip("/")
    if wanted and (not segments or segments[-1].lower() != wanted.lower()):
        segments.append(wanted)
    path = "/" + "/".join(segments) + "/" if segments else "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))

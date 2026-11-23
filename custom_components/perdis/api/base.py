"""What every portal client offers, and the errors it raises."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from ..models import Snapshot

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
    """Logs in to a Perdis portal and reads one snapshot of the roster and the accounts."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, username: str, password: str) -> None:
        self._session = session
        self.base_url = base_url
        self._username = username
        self._password = password

    @abstractmethod
    async def async_login(self) -> None:
        """Sign in; raises `PerdisAuthError` for wrong credentials."""

    @abstractmethod
    async def async_fetch(self, start: date, end: date, now: datetime) -> Snapshot:
        """Read the roster between `start` and `end` and the current accounts."""

    @property
    def discovered_pages(self) -> dict[str, str]:
        """Pages the client found on its own (kind -> URL), for the diagnostics."""
        return {}


def normalize_base_url(url: str, default_path: str = "") -> str:
    """`perdis.example.org` becomes `https://perdis.example.org/<default_path>`, always with a final slash.

    A link copied from the browser (`.../WebComm/default.aspx?TestingCookie=1`) is reduced to the
    folder of the application, so it works as well as the bare address.
    """
    cleaned = url.strip()
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"
    parts = urlsplit(cleaned)
    path = parts.path
    if path.lower().endswith((".aspx", ".html", ".htm")):
        path = path.rsplit("/", 1)[0]
    # Cookieless ASP.NET sessions put their id into the path: /WebComm/(X(1)S(abc))/default.aspx
    path = "/".join(part for part in path.split("/") if not part.startswith("(")) or "/"
    if path in {"", "/"} and default_path:
        path = f"/{default_path.strip('/')}"
    if not path.endswith("/"):
        path += "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))

"""Client for the JSON service behind the AppComm app ("Perdis mobile").

INIT publishes the AppComm app, not its interface. The endpoints below are therefore settings
with a sensible default, not facts: an operator's service may use other paths, which can be
entered in the options of the integration. The client authenticates with the usual patterns of
such services: a token in the login answer (sent as `Authorization: Bearer`) or a session cookie.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp

from ..const import (
    DEFAULT_APPCOMM_BALANCES_PATH,
    DEFAULT_APPCOMM_LOGIN_PATH,
    DEFAULT_APPCOMM_ROSTER_PATH,
    DEFAULT_APPCOMM_WEEKEND_POINTS_PATH,
)
from ..models import Snapshot
from ..parsing.appcomm import AppCommAnswers, AppCommParser, pick
from .base import REQUEST_TIMEOUT, PerdisAuthError, PerdisConnectionError, PerdisPortalError, PortalClient

_LOGGER = logging.getLogger(__name__)

TOKEN_KEYS = ("token", "access_token", "accessToken", "jwt", "sessionToken", "authToken", "bearer")


@dataclass(frozen=True, slots=True)
class AppCommEndpoints:
    """Paths of the service, relative to the base address."""

    login: str = DEFAULT_APPCOMM_LOGIN_PATH
    roster: str = DEFAULT_APPCOMM_ROSTER_PATH
    balances: str = DEFAULT_APPCOMM_BALANCES_PATH
    weekend_points: str = DEFAULT_APPCOMM_WEEKEND_POINTS_PATH


class AppCommClient(PortalClient):
    """Signs in to an AppComm service and reads its JSON answers."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
        zone,
        endpoints: AppCommEndpoints | None = None,
    ) -> None:
        super().__init__(session, base_url, username, password)
        self._parser = AppCommParser(zone)
        self._endpoints = endpoints or AppCommEndpoints()
        self._headers: dict[str, str] = {"Accept": "application/json"}
        self._signed_in = False
        self._lock = asyncio.Lock()

    @property
    def discovered_pages(self) -> dict[str, str]:
        return {kind: self._url(path) for kind, path in (
            ("login", self._endpoints.login), ("roster", self._endpoints.roster),
            ("balances", self._endpoints.balances), ("weekend_points", self._endpoints.weekend_points),
        )}

    async def async_login(self) -> None:
        credentials = {"username": self._username, "password": self._password}
        status, answer = await self._request("POST", self._endpoints.login, json=credentials, signing_in=True)
        if status in (400, 401, 403):
            raise PerdisAuthError("The AppComm service did not accept the user name or password")
        if status == 404:
            raise PerdisPortalError(f"No AppComm login at {self._url(self._endpoints.login)}; check the address")
        if answer is None:
            raise PerdisPortalError(f"{self._url(self._endpoints.login)} answered without JSON; not an AppComm service")
        token = pick(answer, TOKEN_KEYS) if isinstance(answer, dict) else None
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._signed_in = True

    async def async_fetch(self, start: date, end: date, now: datetime) -> Snapshot:
        async with self._lock:
            if not self._signed_in:
                await self.async_login()
            period = {"from": start.isoformat(), "to": end.isoformat()}
            answers = AppCommAnswers(roster=await self._get_signed_in(self._endpoints.roster, period))
            for kind in ("balances", "weekend_points"):
                try:
                    answer = await self._get_signed_in(getattr(self._endpoints, kind))
                except PerdisPortalError as error:  # optional answers must not fail the update
                    _LOGGER.debug("Optional AppComm answer %s unavailable: %s", kind, error)
                    continue
                if isinstance(answer, dict):
                    setattr(answers, kind, answer)
        return self._parser.parse(answers, now)

    async def _get_signed_in(self, path: str, params: dict[str, str] | None = None) -> Any:
        status, answer = await self._request("GET", path, params=params)
        if status in (401, 403):
            self._signed_in = False
            await self.async_login()
            status, answer = await self._request("GET", path, params=params)
        if status >= 400:
            raise PerdisPortalError(f"GET {self._url(path)} answered HTTP {status}")
        return answer

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    async def _request(self, method: str, path: str, signing_in: bool = False, **kwargs) -> tuple[int, Any]:
        url = self._url(path)
        try:
            async with self._session.request(method, url, headers=self._headers, timeout=REQUEST_TIMEOUT,
                                             **kwargs) as response:
                if response.status >= 500:
                    raise PerdisConnectionError(f"{method} {url} answered HTTP {response.status}")
                if response.status >= 400 or (signing_in and response.content_type != "application/json"):
                    return response.status, None
                return response.status, await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as error:
            raise PerdisConnectionError(f"{method} {url} failed: {error!r}") from error
        except ValueError as error:
            raise PerdisPortalError(f"{method} {url} answered with invalid JSON") from error

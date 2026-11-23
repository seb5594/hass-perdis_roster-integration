"""Clients for the two kinds of Perdis portals, and the one place that picks between them."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from ..const import (
    CONF_APPCOMM_BALANCES_PATH,
    CONF_APPCOMM_LOGIN_PATH,
    CONF_APPCOMM_ROSTER_PATH,
    CONF_APPCOMM_WEEKEND_POINTS_PATH,
    CONF_BALANCES_PAGE,
    CONF_ROSTER_PAGE,
    CONF_WEEKEND_POINTS_PAGE,
    PortalType,
)
from .appcomm import AppCommClient, AppCommEndpoints
from .base import (
    PerdisAuthError,
    PerdisConnectionError,
    PerdisError,
    PerdisPortalError,
    PortalClient,
    normalize_base_url,
)
from .webcomm import WebCommClient

__all__ = [
    "PerdisAuthError",
    "PerdisConnectionError",
    "PerdisError",
    "PerdisPortalError",
    "PortalClient",
    "create_client",
    "default_path",
    "normalize_base_url",
]

DEFAULT_PATHS = {PortalType.WEBCOMM: "WebComm", PortalType.APPCOMM: "AppComm"}


def default_path(portal_type: PortalType) -> str:
    """The folder a portal of this type usually lives in."""
    return DEFAULT_PATHS[portal_type]


def create_client(
    portal_type: PortalType,
    session: aiohttp.ClientSession,
    base_url: str,
    username: str,
    password: str,
    zone: ZoneInfo,
    advanced: Mapping[str, Any] | None = None,
) -> PortalClient:
    """The client for `portal_type`, set up with the advanced options of the entry."""
    advanced = advanced or {}
    if portal_type is PortalType.APPCOMM:
        defaults = AppCommEndpoints()
        endpoints = AppCommEndpoints(
            login=advanced.get(CONF_APPCOMM_LOGIN_PATH) or defaults.login,
            roster=advanced.get(CONF_APPCOMM_ROSTER_PATH) or defaults.roster,
            balances=advanced.get(CONF_APPCOMM_BALANCES_PATH) or defaults.balances,
            weekend_points=advanced.get(CONF_APPCOMM_WEEKEND_POINTS_PATH) or defaults.weekend_points,
        )
        return AppCommClient(session, base_url, username, password, zone, endpoints)
    overrides = {
        "roster": advanced.get(CONF_ROSTER_PAGE, ""),
        "balances": advanced.get(CONF_BALANCES_PAGE, ""),
        "weekend_points": advanced.get(CONF_WEEKEND_POINTS_PAGE, ""),
    }
    return WebCommClient(session, base_url, username, password, zone, overrides)

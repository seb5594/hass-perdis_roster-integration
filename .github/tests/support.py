"""Loads the parts of the integration that do not need Home Assistant.

Importing `custom_components.perdis_roster` would run its `__init__.py`, which needs Home Assistant.
The parsers, models, insights and change detection do not, so the tests load them through a
package of their own that points at the same folder but skips `__init__.py`.
"""

import importlib
import sys
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = next((ROOT / "custom_components").iterdir())
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PACKAGE = "perdis_without_home_assistant"
ZONE = ZoneInfo("Europe/Berlin")


def load(module):
    """Import `module` (e.g. "parsing.webcomm") of the integration without Home Assistant."""
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(COMPONENT)]
        sys.modules[PACKAGE] = package
    return importlib.import_module(f"{PACKAGE}.{module}")


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def at(day, hour, minute=0):
    """A point in time in the zone of the tests, e.g. at("2026-11-23", 5, 12)."""
    return datetime.fromisoformat(f"{day}T{hour:02d}:{minute:02d}").replace(tzinfo=ZONE)

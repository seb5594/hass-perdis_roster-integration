"""Only sensors a portal can actually fill are offered: capability detection from a probe."""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from support import load

capabilities = load("capabilities")
models = load("models")
Snapshot, Balances, WeekendPoints = models.Snapshot, models.Balances, models.WeekendPoints
NOW = datetime(2026, 11, 23, 3, tzinfo=ZoneInfo("Europe/Berlin"))


def snapshot(**balances_and_points):
    balances = Balances(
        overtime_minutes=balances_and_points.get("overtime"),
        vacation_remaining_days=balances_and_points.get("vacation"),
    )
    weekend = WeekendPoints(
        points=balances_and_points.get("points"),
        group_average=balances_and_points.get("average"),
        free_weekends=balances_and_points.get("free"),
    )
    return Snapshot(fetched_at=NOW, balances=balances, weekend_points=weekend)


class Detect(unittest.TestCase):
    def test_roster_follows_the_reachable_page_even_when_empty(self):
        caps = capabilities.detect({"roster"}, snapshot())
        self.assertEqual(caps, frozenset({capabilities.CAP_ROSTER}))

    def test_each_account_value_turns_on_its_capability(self):
        caps = capabilities.detect({"roster", "balances"}, snapshot(overtime=870, vacation=12.5))
        self.assertIn(capabilities.CAP_OVERTIME, caps)
        self.assertIn(capabilities.CAP_VACATION, caps)

    def test_a_portal_without_weekend_points_offers_none_of_them(self):
        caps = capabilities.detect({"roster"}, snapshot(overtime=0))
        self.assertNotIn(capabilities.CAP_WEEKEND_POINTS, caps)
        self.assertNotIn(capabilities.CAP_WEEKEND_AVERAGE, caps)
        self.assertNotIn(capabilities.CAP_WEEKEND_FREE, caps)

    def test_weekend_capabilities_are_separate(self):
        caps = capabilities.detect({"roster", "weekend_points"}, snapshot(points=38.5, free=7))
        self.assertIn(capabilities.CAP_WEEKEND_POINTS, caps)
        self.assertIn(capabilities.CAP_WEEKEND_FREE, caps)
        self.assertNotIn(capabilities.CAP_WEEKEND_AVERAGE, caps)  # no group average on this portal

    def test_a_dead_portal_offers_nothing(self):
        self.assertEqual(capabilities.detect(set(), snapshot()), frozenset())


if __name__ == "__main__":
    unittest.main()

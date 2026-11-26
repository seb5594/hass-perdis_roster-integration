"""Derived information and change detection, worked out from a small hand-made roster."""

import unittest
from datetime import date, timedelta

from support import at, load

models = load("models")
insights_module = load("insights")
changes = load("changes")
Duty, DutyType, Snapshot = models.Duty, models.DutyType, models.Snapshot
ShiftCategory = insights_module.ShiftCategory

SETTINGS = insights_module.InsightSettings(
    wake_up_lead=timedelta(minutes=90), commute=timedelta(minutes=30), minimum_rest=timedelta(hours=11)
)


def shift(day, start, end, code="4711", **extra):
    first, last = at(day, *start), at(day, *end)
    if last <= first:
        last += timedelta(days=1)
    return Duty(date.fromisoformat(day), DutyType.WORK, code, first, last, "Hbf", **extra)


def off(day, duty_type=DutyType.FREE, code="R"):
    return Duty(date.fromisoformat(day), duty_type, code)


ROSTER = [
    shift("2026-11-22", (14, 0), (22, 30), "5103"),  # Sunday, the evening before
    shift("2026-11-23", (5, 12), (13, 40)),  # Monday: early shift, only 6.7 hours of rest
    shift("2026-11-24", (13, 10), (21, 45), "5104"),
    shift("2026-11-25", (6, 0), (18, 15), "3001", split=True),
    off("2026-11-26"),
    shift("2026-11-27", (21, 30), (2, 5), "6020"),
    off("2026-11-28"),
    off("2026-11-29"),
    off("2026-11-30", DutyType.VACATION, "U"),
]


def insights_at(moment):
    return insights_module.RosterInsights(Snapshot(moment, ROSTER), moment, SETTINGS)


class Shifts(unittest.TestCase):
    def test_before_the_shift(self):
        insights = insights_at(at("2026-11-23", 2, 0))
        self.assertEqual(insights.next_shift.code, "4711")
        self.assertFalse(insights.on_duty)
        self.assertEqual(insights.wake_up_time, at("2026-11-23", 3, 42))
        self.assertEqual(insights.leave_home_time, at("2026-11-23", 4, 42))
        self.assertEqual(insights.next_shift_category, ShiftCategory.EARLY)

    def test_short_rest_after_a_late_shift(self):
        insights = insights_at(at("2026-11-23", 2, 0))
        self.assertEqual(insights.rest_before_upcoming, timedelta(hours=6, minutes=42))
        self.assertTrue(insights.short_rest)

    def test_during_the_shift_the_next_one_is_the_running_one(self):
        insights = insights_at(at("2026-11-23", 9, 0))
        self.assertTrue(insights.on_duty)
        self.assertEqual(insights.next_shift.code, "4711")
        self.assertEqual(insights.upcoming_shift.code, "5104")
        self.assertEqual(insights.wake_up_time, at("2026-11-24", 11, 40))

    def test_categories(self):
        categories = [insights_module.shift_category(duty) for duty in ROSTER[:6] if duty.is_working]
        self.assertEqual(categories, [ShiftCategory.LATE, ShiftCategory.EARLY, ShiftCategory.LATE,
                                      ShiftCategory.SPLIT, ShiftCategory.NIGHT])


class Days(unittest.TestCase):
    def test_days_until_the_next_day_off_and_the_streak(self):
        insights = insights_at(at("2026-11-23", 2, 0))
        self.assertEqual(insights.next_day_off.day, date(2026, 11, 26))
        self.assertEqual(insights.days_until_day_off, 3)
        self.assertEqual(insights.working_days_in_a_row, 3)

    def test_free_weekend(self):
        insights = insights_at(at("2026-11-23", 2, 0))
        self.assertEqual(insights.free_weekends, [date(2026, 11, 28)])
        self.assertEqual(insights_at(at("2026-11-29", 10, 0)).next_free_weekend, date(2026, 11, 28))

    def test_planned_hours_of_the_week(self):
        insights = insights_at(at("2026-11-23", 2, 0))
        self.assertEqual(insights.week, (date(2026, 11, 23), date(2026, 11, 29)))
        expected = (8 * 60 + 28) + (8 * 60 + 35) + (12 * 60 + 15) + (4 * 60 + 35)
        self.assertEqual(insights.planned_minutes(*insights.week), expected)
        self.assertEqual(insights.summary(*insights.week)["free"], 3)


class Changes(unittest.TestCase):
    def test_changed_times_and_new_duties_are_reported(self):
        today = date(2026, 11, 23)
        before = Snapshot(at("2026-11-23", 1), ROSTER)
        moved = shift("2026-11-24", (14, 10), (22, 45), "5104")
        replaced_day_off = shift("2026-11-26", (6, 0), (14, 0), "7001")
        after = Snapshot(at("2026-11-23", 2), [ROSTER[1], moved, ROSTER[3], replaced_day_off, *ROSTER[5:]])
        found = {change.day: change.kind for change in changes.detect_changes(before, after, today)}
        self.assertEqual(found, {date(2026, 11, 24): models.ChangeKind.TIMES,
                                 date(2026, 11, 26): models.ChangeKind.DUTY})

    def test_the_first_refresh_reports_nothing(self):
        self.assertEqual(changes.detect_changes(None, Snapshot(at("2026-11-23", 1), ROSTER), date(2026, 11, 23)), [])

    def test_descriptions_in_both_languages(self):
        change = models.ScheduleChange(date(2026, 11, 24), models.ChangeKind.TIMES, at("2026-11-23", 2),
                                       ROSTER[2], shift("2026-11-24", (14, 10), (22, 45), "5104"))
        # Two lines: weekday/date and what the day now is, then the times.
        self.assertEqual(changes.describe(change, "de"), "Dienstag, 24.11. Dienst 5104\n14:10 - 22:45")
        self.assertEqual(changes.describe(change, "en"), "Tuesday, 24 Nov Duty 5104\n14:10 - 22:45")

    def test_turning_into_a_day_off_reads_as_its_name(self):
        change = models.ScheduleChange(date(2026, 11, 30), models.ChangeKind.DUTY, at("2026-11-23", 2),
                                       Duty(date(2026, 11, 30), DutyType.UNKNOWN), off("2026-11-30"))
        # A day off has no times, so just the name is shown.
        self.assertEqual(changes.describe(change, "de"), "Montag, 30.11. Frei")
        self.assertEqual(changes.describe(change, "en"), "Monday, 30 Nov Day off")


if __name__ == "__main__":
    unittest.main()

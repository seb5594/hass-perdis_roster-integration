"""The parsers turn portal pages into duties, accounts and weekend points."""

import json
import unittest
from datetime import date, timedelta

from support import ZONE, at, fixture, load

values = load("parsing.values")
html = load("parsing.html")
webcomm = load("parsing.webcomm")
appcomm = load("parsing.appcomm")
models = load("models")
DutyType = models.DutyType
TODAY = date(2026, 11, 23)


class Values(unittest.TestCase):
    def test_dates_in_every_spelling(self):
        self.assertEqual(values.parse_date("Mo 23.11.2026", TODAY), date(2026, 11, 23))
        self.assertEqual(values.parse_date("2026-11-23", TODAY), date(2026, 11, 23))
        self.assertEqual(values.parse_date("ma 23-11-2026", TODAY), date(2026, 11, 23))
        self.assertEqual(values.parse_date("23.11.26", TODAY), date(2026, 11, 23))
        self.assertIsNone(values.parse_date("Dienst 4711", TODAY))

    def test_a_date_without_year_lands_in_the_closest_year(self):
        self.assertEqual(values.parse_date("02.01.", date(2026, 12, 28)), date(2027, 1, 2))
        self.assertEqual(values.parse_date("30.12.", date(2027, 1, 3)), date(2026, 12, 30))

    def test_operating_times_past_midnight(self):
        self.assertEqual(values.clock_minutes("25:45"), 25 * 60 + 45)
        start, end = values.shift_times(TODAY, 21 * 60 + 30, 26 * 60 + 5, ZONE)
        self.assertEqual((start, end), (at("2026-11-23", 21, 30), at("2026-11-24", 2, 5)))

    def test_an_end_before_the_start_runs_into_the_next_day(self):
        _, end = values.shift_times(TODAY, 22 * 60 + 15, 6 * 60 + 5, ZONE)
        self.assertEqual(end, at("2026-11-24", 6, 5))

    def test_durations_and_numbers(self):
        self.assertEqual(values.parse_duration("+14:30"), 870)
        self.assertEqual(values.parse_duration("-2:15 h"), -135)
        self.assertEqual(values.parse_duration("12,5 Std."), 750)
        self.assertEqual(values.parse_duration("45 min"), 45)
        self.assertEqual(values.parse_number("1.234,5"), 1234.5)
        self.assertEqual(values.parse_number("1,234.5"), 1234.5)
        self.assertEqual(values.parse_number("12,5"), 12.5)
        self.assertIsNone(values.parse_number("keine Angabe"))

    def test_duty_types_from_codes_and_remarks(self):
        self.assertEqual(values.classify_duty("4711", has_times=True), DutyType.WORK)
        self.assertEqual(values.classify_duty("R"), DutyType.FREE)
        self.assertEqual(values.classify_duty("U"), DutyType.VACATION)
        self.assertEqual(values.classify_duty("BD1", has_times=True), DutyType.RESERVE)
        self.assertEqual(values.classify_duty("X7", "Seminar Fahrgastrechte"), DutyType.TRAINING)
        self.assertEqual(values.classify_duty("ZZ", "Krankmeldung"), DutyType.SICK)
        self.assertEqual(values.classify_duty("VRIJ"), DutyType.FREE)
        self.assertEqual(values.classify_duty("??"), DutyType.UNKNOWN)


class HtmlTree(unittest.TestCase):
    def test_missing_end_tags_are_closed_like_a_browser_does(self):
        document = html.parse_html("<table><tr><td>a<td>b<tr><td>c</table>")
        rows = html.table_rows(document.find("table"))
        self.assertEqual(rows, [(False, ["a", "b"]), (False, ["c"])])

    def test_login_form_of_webcomm(self):
        form = html.login_form(html.parse_html(fixture("webcomm_login.html")))
        self.assertEqual(form.action, "./default.aspx?TestingCookie=1")
        self.assertEqual(form.username_field, "ctl00$cntMainBody$lgnView$lgnLogin$UserName")
        self.assertEqual(form.password_field, "ctl00$cntMainBody$lgnView$lgnLogin$Password")
        self.assertEqual(form.submit, ("ctl00$cntMainBody$lgnView$lgnLogin$LoginButton", "Anmelden"))
        self.assertEqual(form.fields["__VIEWSTATE"], "dGVzdA==")

    def test_postback_links_and_buttons_are_found(self):
        form = html.parse_forms(html.parse_html(fixture("webcomm_roster_december.html")))[0]
        targets = [control.target for control in form.postbacks]
        self.assertIn("ctl00$cntMainBody$lnkNext", targets)


class WebCommRoster(unittest.TestCase):
    def setUp(self):
        self.parser = webcomm.WebCommParser(ZONE)
        roster = self.parser.parse_roster(fixture("webcomm_roster_november.html"), TODAY)
        self.duties = {duty.day: duty for duty in roster}

    def test_columns_are_recognised_by_their_headers(self):
        duty = self.duties[date(2026, 11, 23)]
        self.assertEqual(duty.code, "4711")
        self.assertEqual(duty.duty_type, DutyType.WORK)
        self.assertEqual((duty.start, duty.end), (at("2026-11-23", 5, 12), at("2026-11-23", 13, 40)))
        self.assertEqual((duty.start_location, duty.end_location), ("Betriebshof Lierenfeld", "Hbf"))
        self.assertEqual(duty.lines, ("705", "U79"))
        self.assertEqual(duty.paid_minutes, 7 * 60 + 58)

    def test_two_rows_of_one_day_form_a_split_shift(self):
        duty = self.duties[date(2026, 11, 25)]
        self.assertTrue(duty.split)
        self.assertEqual((duty.start, duty.end), (at("2026-11-25", 6), at("2026-11-25", 18, 15)))
        self.assertEqual(duty.paid_minutes, 4 * 60 + 3 * 60 + 45)
        self.assertEqual(duty.end_location, "Betriebshof Heerdt")

    def test_night_shift_ends_on_the_next_calendar_day(self):
        duty = self.duties[date(2026, 11, 27)]
        self.assertEqual(duty.end, at("2026-11-28", 2, 5))

    def test_days_off_and_vacation(self):
        self.assertEqual(self.duties[date(2026, 11, 26)].duty_type, DutyType.FREE)
        self.assertEqual(self.duties[date(2026, 11, 30)].duty_type, DutyType.VACATION)

    def test_header_row_made_of_td_cells_and_dates_without_year(self):
        duties = {d.day: d for d in self.parser.parse_roster(fixture("webcomm_roster_december.html"), TODAY)}
        self.assertEqual(duties[date(2026, 12, 1)].duty_type, DutyType.RESERVE)
        self.assertEqual(duties[date(2026, 12, 1)].start_location, "Leitstelle")
        self.assertEqual(duties[date(2026, 12, 2)].duty_type, DutyType.SICK)
        self.assertEqual(duties[date(2026, 12, 5)].duty_type, DutyType.COMPENSATION)
        self.assertEqual(duties[date(2026, 12, 6)].duty_type, DutyType.TRAINING)

    def test_dutch_table_without_header(self):
        duties = {d.day: d for d in self.parser.parse_roster(fixture("webcomm_roster_dutch_headerless.html"), TODAY)}
        self.assertEqual(duties[date(2026, 11, 23)].code, "D1204")
        self.assertEqual(duties[date(2026, 11, 23)].start_location, "Garage Zuid")
        self.assertEqual(duties[date(2026, 11, 24)].duty_type, DutyType.FREE)
        self.assertEqual(duties[date(2026, 11, 25)].end, at("2026-11-26", 6, 5))


class WebCommAccounts(unittest.TestCase):
    def setUp(self):
        pages = webcomm.WebCommPages(
            menu=fixture("webcomm_menu.html"),
            roster=[fixture("webcomm_roster_november.html"), fixture("webcomm_roster_december.html")],
            balances=fixture("webcomm_balances.html"),
            weekend_points=fixture("webcomm_weekend_points.html"),
        )
        self.snapshot = webcomm.WebCommParser(ZONE).parse(pages, at("2026-11-23", 3))

    def test_pages_of_two_months_are_combined(self):
        self.assertEqual(self.snapshot.duties[0].day, date(2026, 11, 23))
        self.assertEqual(self.snapshot.duties[-1].day, date(2026, 12, 6))

    def test_balances(self):
        balances = self.snapshot.balances
        self.assertEqual(balances.overtime_minutes, 870)
        self.assertEqual(balances.target_minutes, 169 * 60)
        self.assertEqual(balances.actual_minutes, 121 * 60 + 15)
        self.assertEqual(balances.vacation_remaining_days, 12.5)
        self.assertEqual(balances.vacation_planned_days, 6.0)
        self.assertEqual(balances.vacation_entitlement_days, 30.0)
        self.assertEqual(balances.raw["Nachtzuschlag"], "18:45")

    def test_weekend_points(self):
        points = self.snapshot.weekend_points
        self.assertEqual((points.points, points.group_average, points.free_weekends), (38.5, 42.0, 7))
        self.assertEqual([entry.points for entry in points.entries], [1.0, 1.5])

    def test_employee_name_from_the_header(self):
        self.assertEqual(self.snapshot.employee_name, "Max Mustermann (4711)")

    def test_snapshot_survives_the_storage_round_trip(self):
        restored = models.Snapshot.from_dict(json.loads(json.dumps(self.snapshot.to_dict())))
        self.assertEqual(restored, self.snapshot)


class AppComm(unittest.TestCase):
    def test_any_layout_with_the_usual_field_names(self):
        answers = appcomm.AppCommAnswers(
            roster=json.loads(fixture("appcomm_roster.json")),
            balances={"overtimeMinutes": 870, "vacationRemaining": "12,5"},
            weekend_points={"points": 38.5, "groupAverage": 42},
        )
        snapshot = appcomm.AppCommParser(ZONE).parse(answers, at("2026-11-23", 3))
        duties = {duty.day: duty for duty in snapshot.duties}
        first = duties[date(2026, 11, 23)]
        self.assertEqual((first.code, first.start_location, first.lines), ("4711", "Betriebshof", ("705", "U79")))
        self.assertEqual(first.paid_minutes, 478)
        self.assertEqual(duties[date(2026, 11, 24)].duty_type, DutyType.FREE)
        night = duties[date(2026, 11, 25)]
        self.assertEqual(night.end - night.start, timedelta(hours=4, minutes=35))
        self.assertEqual(duties[date(2026, 11, 26)].duty_type, DutyType.VACATION)
        self.assertEqual(snapshot.balances.overtime_minutes, 870)
        self.assertEqual(snapshot.balances.vacation_remaining_days, 12.5)
        self.assertEqual(snapshot.weekend_points.group_average, 42.0)


if __name__ == "__main__":
    unittest.main()

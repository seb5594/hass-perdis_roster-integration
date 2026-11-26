"""The parsers turn portal pages into duties, accounts and weekend points."""

import json
import unittest
from datetime import date, timedelta

from support import ZONE, at, fixture, load

values = load("parsing.values")
html = load("parsing.html")
webcomm = load("parsing.webcomm")
appcomm = load("parsing.appcomm")
shift_detail = load("parsing.shift_detail")
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
        self.assertEqual((duty.start_location, duty.end_location), ("Betriebshof Musterstadt", "Hbf"))
        self.assertEqual(duty.lines, ("705", "U79"))
        self.assertEqual(duty.paid_minutes, 7 * 60 + 58)

    def test_two_rows_of_one_day_form_a_split_shift(self):
        duty = self.duties[date(2026, 11, 25)]
        self.assertTrue(duty.split)
        self.assertEqual((duty.start, duty.end), (at("2026-11-25", 6), at("2026-11-25", 18, 15)))
        self.assertEqual(duty.paid_minutes, 4 * 60 + 3 * 60 + 45)
        self.assertEqual(duty.end_location, "Betriebshof Beispielheim")

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
            daily_values=fixture("webcomm_daily_values.html"),
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

    def test_daily_values_are_read_per_day(self):
        daily = self.snapshot.daily_values
        self.assertEqual([entry.day for entry in daily.entries],
                         [date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25)])
        monday = daily.entries[0]
        self.assertEqual((monday.target_minutes, monday.actual_minutes), (7 * 60 + 42, 8 * 60 + 12))
        self.assertEqual((monday.balance_minutes, monday.cumulative_minutes), (30, 15 * 60))
        self.assertEqual(daily.columns[0], "Datum")

    def test_daily_values_current_day_is_todays_row(self):
        current = self.snapshot.daily_values.current(date(2026, 11, 24))
        self.assertEqual((current.day, current.balance_minutes), (date(2026, 11, 24), -30))

    def test_employee_name_from_the_header(self):
        self.assertEqual(self.snapshot.employee_name, "Max Mustermann (4711)")

    def test_snapshot_survives_the_storage_round_trip(self):
        restored = models.Snapshot.from_dict(json.loads(json.dumps(self.snapshot.to_dict())))
        self.assertEqual(restored, self.snapshot)


class BalancesAccountsTable(unittest.TestCase):
    """Some portals list the accounts as a "Konto | Von | Bis | Wert" table, value in the last column."""

    def test_time_account_is_read_from_the_value_column(self):
        pages = webcomm.WebCommPages(balances=fixture("webcomm_balances_accounts.html"))
        snapshot = webcomm.WebCommParser(ZONE).parse(pages, at("2026-11-23", 3))
        # "Differenz Verf. J" is the running time-account balance; -10:17 means 10 h 17 min short.
        self.assertEqual(snapshot.balances.overtime_minutes, -(10 * 60 + 17))
        self.assertEqual(snapshot.balances.raw["Differenz Verf. J"], "-10:17")


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


class CalendarRoster(unittest.TestCase):
    """Portals that render the roster as an ASP.NET calendar with the shift in each day's tooltip."""

    def setUp(self):
        self.duties = {
            duty.day: duty
            for duty in webcomm.WebCommParser(ZONE).parse_roster(fixture("webcomm_roster_calendar.html"), TODAY)
        }

    def test_timed_shifts_from_the_tooltip(self):
        duty = self.duties[date(2026, 11, 23)]
        self.assertEqual(duty.code, "4711")
        self.assertEqual(duty.duty_type, DutyType.WORK)
        self.assertEqual((duty.start, duty.end), (at("2026-11-23", 5, 12), at("2026-11-23", 13, 40)))
        self.assertEqual(duty.start_location, "Betriebshof Musterstadt")
        self.assertEqual(duty.lines, ("705", "U79"))

    def test_two_time_ranges_make_a_split_shift(self):
        duty = self.duties[date(2026, 11, 25)]
        self.assertTrue(duty.split)
        self.assertEqual((duty.start, duty.end), (at("2026-11-25", 6), at("2026-11-25", 18, 15)))

    def test_night_shift_crosses_midnight(self):
        self.assertEqual(self.duties[date(2026, 11, 27)].end, at("2026-11-28", 2, 5))

    def test_all_day_code_in_a_span(self):
        self.assertEqual(self.duties[date(2026, 11, 26)].duty_type, DutyType.VACATION)
        self.assertEqual(self.duties[date(2026, 11, 30)].duty_type, DutyType.VACATION)

    def test_a_table_roster_still_wins_over_the_calendar_fallback(self):
        # The November table fixture must parse as a table, not fall through to the calendar reader.
        duties = webcomm.WebCommParser(ZONE).parse_roster(fixture("webcomm_roster_november.html"), TODAY)
        self.assertTrue(any(duty.start_location == "Betriebshof Musterstadt" for duty in duties))


class CalendarWithAMissingDateLink(unittest.TestCase):
    """A day next to the selected one can render without its date link; it must not be dropped."""

    def setUp(self):
        self.duties = {
            duty.day: duty
            for duty in webcomm.WebCommParser(ZONE).parse_roster(fixture("webcomm_roster_calendar_gap.html"), TODAY)
        }

    def test_the_undated_day_is_recovered_from_its_neighbours(self):
        # The 26th carries only "3095" and no date link, between the dated 25th and 27th.
        self.assertIn(date(2026, 11, 26), self.duties)
        self.assertEqual(self.duties[date(2026, 11, 26)].code, "3095")
        self.assertEqual(self.duties[date(2026, 11, 26)].duty_type, DutyType.WORK)

    def test_the_dated_neighbours_keep_their_own_days(self):
        self.assertEqual(self.duties[date(2026, 11, 27)].code, "SF Neu")
        self.assertEqual(self.duties[date(2026, 11, 30)].code, "3088")


class CalendarCodes(unittest.TestCase):
    """A month calendar that shows only a duty code per day (times live on the detail page)."""

    def setUp(self):
        self.duties = {
            duty.day: duty
            for duty in webcomm.WebCommParser(ZONE).parse_roster(
                fixture("webcomm_roster_calendar_codes.html"), date(2026, 11, 1))
        }

    def test_the_month_is_read_from_the_heading_and_dates_the_cells(self):
        self.assertEqual(min(self.duties), date(2026, 11, 1))
        self.assertEqual(max(self.duties), date(2026, 11, 8))

    def test_codes_become_the_right_types(self):
        self.assertEqual(self.duties[date(2026, 11, 1)].duty_type, DutyType.FREE)
        self.assertEqual(self.duties[date(2026, 11, 2)].code, "3088")
        self.assertEqual(self.duties[date(2026, 11, 2)].duty_type, DutyType.WORK)
        self.assertEqual(self.duties[date(2026, 11, 8)].duty_type, DutyType.VACATION)

    def test_adjacent_month_cells_are_skipped(self):
        # The leading cells 26..31 belong to October and must not become November duties; only the
        # ascending run 1..8 of the fetched month is kept.
        self.assertEqual(sorted(duty.day.day for duty in self.duties.values()), list(range(1, 9)))


class ShiftDetailPage(unittest.TestCase):
    """The detail page of a shift gives its real times, places, lines and legs."""

    def setUp(self):
        self.detail = shift_detail.parse_shift_detail(fixture("webcomm_shift_detail.html"), date(2026, 11, 24), ZONE)

    def test_only_timed_legs_become_segments(self):
        self.assertEqual(len(self.detail.segments), 5)  # the "- / -" separator rows are skipped

    def test_relief_marker_is_attached_to_the_leg_above_it(self):
        # The driving leg is followed by a "+ / -" row: take a vehicle over, do not hand it over.
        self.assertEqual(self.detail.segments[1].relief, "+ / -")
        self.assertEqual(self.detail.segments[0].relief, "- / -")

    def test_line_and_course_of_a_driving_leg(self):
        leg = self.detail.segments[1]
        self.assertEqual((leg.line, leg.course), ("21", "11"))

    def test_applying_the_detail_fills_the_duty(self):
        duty = models.Duty(day=date(2026, 11, 24), duty_type=DutyType.WORK, code="3095")
        self.detail.apply_to(duty)
        self.assertEqual((duty.start, duty.end), (at("2026-11-24", 10, 22), at("2026-11-24", 18, 3)))
        self.assertEqual(duty.start_location, "HB")
        self.assertEqual(duty.lines, ("21", "16"))
        self.assertEqual(duty.break_minutes, 41)  # the ÜZ transition counts as a break
        self.assertFalse(duty.split)

    def test_segments_survive_the_storage_round_trip(self):
        duty = models.Duty(day=date(2026, 11, 24))
        self.detail.apply_to(duty)
        restored = models.Duty.from_dict(json.loads(json.dumps(duty.to_dict())))
        self.assertEqual(restored, duty)


class CalendarTooltipRoster(unittest.TestCase):
    """A month calendar whose day cells carry the shift in a bullet-separated tooltip."""

    def setUp(self):
        duties = webcomm.WebCommParser(ZONE).parse_roster(
            fixture("webcomm_roster_calendar_tooltip.html"), TODAY)
        self.duties = {duty.day: duty for duty in duties}

    def test_neighbouring_month_cells_are_left_out(self):
        # The faded 30/31 October cells link to October dates but must not be dated into November.
        self.assertNotIn(date(2026, 10, 30), self.duties)
        self.assertEqual(min(self.duties), date(2026, 11, 1))

    def test_times_place_and_paid_hours_from_the_tooltip(self):
        duty = self.duties[date(2026, 11, 26)]
        self.assertEqual((duty.start, duty.end), (at("2026-11-26", 10, 22), at("2026-11-26", 18, 3)))
        self.assertEqual(duty.code, "3095")
        self.assertEqual(duty.start_location, "Hbf, Hauptbahnhof")
        self.assertEqual(duty.paid_minutes, 7 * 60 + 11)  # "Lohnstunden: 07:11 Std."
        self.assertEqual(duty.duty_type, DutyType.WORK)

    def test_absence_codes_are_classified(self):
        self.assertEqual(self.duties[date(2026, 11, 23)].duty_type, DutyType.FREE)   # FREI
        self.assertEqual(self.duties[date(2026, 11, 24)].duty_type, DutyType.SICK)   # k
        self.assertEqual(self.duties[date(2026, 11, 25)].duty_type, DutyType.VACATION)  # u


class HolidaysVacationSummary(unittest.TestCase):
    """The leave page lists remaining vacation in a key-value table of several accounts per row."""

    def test_remaining_and_entitlement_days(self):
        pages = webcomm.WebCommPages(vacation=fixture("webcomm_holidays.html"))
        balances = webcomm.WebCommParser(ZONE).parse(pages, at("2026-11-23", 3)).balances
        self.assertEqual(balances.vacation_remaining_days, 3.0)   # Restanspruch of the main account
        self.assertEqual(balances.vacation_entitlement_days, 32.0)  # Urlaubsanspruch


class DutySwapPage(unittest.TestCase):
    """The duty-swap page lists open swap offers and the period new requests may cover."""

    def setUp(self):
        self.dutyswap = load("parsing.dutyswap")

    def test_open_swaps_without_the_placeholder_row(self):
        swaps = self.dutyswap.parse_duty_swaps(fixture("webcomm_dutyswap.html"), TODAY)
        self.assertEqual(len(swaps), 1)  # the empty "-" row is left out
        swap = swaps[0]
        self.assertEqual(swap.swap_id, "90201")  # the handle the portal acts on
        self.assertEqual(swap.day, date(2026, 11, 26))
        self.assertEqual((swap.duty, swap.time, swap.partner), ("3095", "10:22 - 18:03", "Mustermann"))
        self.assertEqual((swap.status, swap.kind), ("Angeboten", "Abgabe"))

    def test_request_window_from_the_heading(self):
        window = self.dutyswap.parse_swap_window(fixture("webcomm_dutyswap.html"), TODAY)
        self.assertEqual(window, (date(2026, 11, 25), date(2026, 12, 9)))


class OperatorShortName(unittest.TestCase):
    """The operator's short name seeds the account title "<short> - <personnel number>"."""

    def test_short_name_is_the_first_word_of_the_name(self):
        operators = load("operators")
        shorts = {operator.key: operator.short for operator in operators.OPERATORS}
        self.assertEqual(shorts["dvg_duisburg"], "DVG")
        self.assertEqual(shorts["rheinbahn"], "Rheinbahn")
        self.assertEqual(shorts["uestra"], "ÜSTRA")  # written in capitals, as the company does

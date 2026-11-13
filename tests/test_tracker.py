import os
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo  # noqa: E402
import tracker  # noqa: E402
import xlsx  # noqa: E402

TODAY = date(2026, 11, 12)
NOV10 = 46336.0  # Excel serial for 2026-11-10


def wb_from(*sheets):
    return tracker.parse_workbook(xlsx.read_workbook(xlsx.write_workbook(list(sheets))), TODAY)


class Minutes(unittest.TestCase):
    def test_excel_time_fraction(self):
        self.assertEqual(tracker.minutes(0.020138888), 29)       # shown as 0:29 / 12:29:00 AM
        self.assertEqual(tracker.minutes(5 / 24 + 33 / 1440), 333)
        self.assertEqual(tracker.minutes(0.0), 0)

    def test_text(self):
        self.assertEqual(tracker.minutes("5:33"), 333)
        self.assertEqual(tracker.minutes("12:29:00 AM"), 29)
        self.assertEqual(tracker.minutes("2.5h"), 150)
        self.assertEqual(tracker.minutes("90m"), 90)
        self.assertEqual(tracker.minutes("3h 15m"), 195)
        self.assertIsNone(tracker.minutes("Not logged"))
        self.assertIsNone(tracker.minutes(None))
        self.assertIsNone(tracker.minutes(float("nan")))
        self.assertIsNone(tracker.minutes(-0.1))

    def test_decimal_hours_and_datetimes(self):
        self.assertEqual(tracker.minutes(5.5), 330)
        self.assertEqual(tracker.minutes(46000.25), 360)


class Dates(unittest.TestCase):
    def test_tab_names(self):
        self.assertEqual(tracker.tab_date("10 Nov", TODAY), date(2026, 11, 10))
        self.assertEqual(tracker.tab_date("02 Nov", TODAY), date(2026, 11, 2))
        self.assertEqual(tracker.tab_date("Nov 3", TODAY), date(2026, 11, 3))
        self.assertEqual(tracker.tab_date("3-Nov-25", TODAY), date(2025, 11, 3))
        self.assertIsNone(tracker.tab_date("App Usage", TODAY))

    def test_year_rolls_back_in_january(self):
        self.assertEqual(tracker.tab_date("30 Dec", date(2027, 1, 4)), date(2026, 12, 30))

    def test_cell_dates(self):
        self.assertEqual(tracker.cell_date(NOV10), date(2026, 11, 10))
        self.assertEqual(tracker.cell_date("2026-11-10"), date(2026, 11, 10))
        self.assertEqual(tracker.cell_date("11/10/2026"), date(2026, 11, 10))
        self.assertIsNone(tracker.cell_date("Date"))
        self.assertIsNone(tracker.cell_date(5.0))

    def test_emp_key(self):
        self.assertEqual(tracker.emp_key("5560 VM"), "5560")
        self.assertEqual(tracker.emp_key(5618.0), "5618")
        self.assertEqual(tracker.emp_key("5633(VM)"), "5633")
        self.assertEqual(tracker.emp_key(None), "")
        self.assertEqual(tracker.emp_key("VM"), "")


HEAD = ["User", "Date", "Emp ID", "Email Id", "Break Reasons", "T. Logged hours", "T.Non Productive hours",
        "T.Productive hours", "Reason"]


class Parse(unittest.TestCase):
    def test_columns_by_header_not_position(self):
        rows = [
            HEAD,
            ["Ana Ruiz", NOV10, "5560 VM", "ARuiz@x.com", "Lunch", 0.4, 0.5, 0.020138888, None],
            ["Ben Ode", NOV10, 5618.0, "BOde@x.com", None, 0, 0, 0, "Not logged"],
            [None] * 9,
            ["Total", None, None, None, None, 1, 0, 1, None],
        ]
        d = wb_from(("10 Nov", rows))["days"][0]
        c = d["candidates"]
        self.assertEqual([x["name"] for x in c], ["Ana Ruiz", "Ben Ode"])
        self.assertEqual(c[0]["productive"], 29)
        self.assertEqual(c[0]["logged"], 576)
        self.assertEqual(c[1]["reason"], "Not logged")       # not "Break Reasons"
        self.assertEqual(c[0]["row"], 2)
        self.assertEqual(c[0]["key"], "2026-11-10|aruiz@x.com")
        self.assertEqual(d["warnings"], [])

    def test_missing_columns_is_an_error_not_a_crash(self):
        d = wb_from(("10 Nov", [["User", "Something"], ["A", 1]]))["days"][0]
        self.assertTrue(d["error"])

    def test_bad_rows_become_warnings_and_the_rest_still_works(self):
        rows = [
            HEAD,
            ["Good One", NOV10, 1, "good@x.com", None, 0.4, 0, 0.1, None],
            ["Blank Hours", NOV10, 2, "blank@x.com", None, 0.4, 0, None, None],
            ["Text Hours", NOV10, 3, "text@x.com", None, 0.4, 0, "lots", None],
            ["Too Much", NOV10, 4, "much@x.com", None, 0.1, 0, 0.3, None],
            ["Wrong Day", 46335.0, 5, "wrong@x.com", None, 0.4, 0, 0.1, None],
            ["Good One", NOV10, 1, "good@x.com", None, 0.4, 0, 0.1, None],
            [None, None, None, None, "orphan data", None, None, None, None],
        ]
        d = wb_from(("10 Nov", rows))["days"][0]
        msgs = " | ".join(w["msg"] for w in d["warnings"])
        self.assertIn("Productive hours is blank", msgs)
        self.assertIn("isn't a time", msgs)
        self.assertIn("more than logged", msgs)
        self.assertIn("Date column says 09 Nov 2026, but the tab is 10 Nov 2026", msgs)
        self.assertIn("Appears twice", msgs)
        self.assertIn("no name or email", msgs)
        self.assertEqual(len(d["candidates"]), 6)  # nothing dropped silently
        blank = next(c for c in d["candidates"] if c["name"] == "Blank Hours")
        self.assertIsNone(blank["productive"])

    def test_one_broken_tab_does_not_hide_the_others(self):
        wb = wb_from(("10 Nov", [HEAD, ["A B", NOV10, 1, "ab@x.com", None, 0.4, 0, 0.1, None]]),
                     ("09 Nov", [["nothing useful"]]))
        by = {d["sheet"]: d for d in wb["days"]}
        self.assertIsNone(by["10 Nov"]["error"])
        self.assertTrue(by["09 Nov"]["error"])

    def test_without_a_company_domain_only_lone_domains_are_doubted(self):
        # no domain set: any domain two people use counts as real, even one letter from another
        rows = [["User", "Email Id", "T.Productive hours"],
                ["A One", "aone@pcs-example.com", 0.1], ["B Two", "btwo@pcs-example.com", 0.1],
                ["C Three", "cthree@ccs-example.com", 0.1], ["D Four", "dfour@ccs-example.com", 0.1],
                ["E Five", "efive@pcs-example.compush", 0.1]]
        c = {x["name"]: x for x in wb_from(("10 Nov", rows))["days"][0]["candidates"]}
        for n in ("A One", "B Two", "C Three", "D Four"):
            self.assertEqual(c[n]["email_issue"], "", n)
        self.assertIn("typo", c["E Five"]["email_issue"])
        self.assertEqual(c["E Five"]["email_suggestion"], "efive@pcs-example.com")


ROWS = [["User", "Email Id", "T.Productive hours"],
        ["Ann Lee", "ALee@pcs-example.com", 0.1], ["Bo Chen", "bchen@ccs-example.com", 0.1],
        ["Cy Park", "CPark@pcs-example.compush", 0.1], ["Dee  Roy", "DRoy@pcs-example.com", 0.1]]


def people(**kw):
    sheets = xlsx.read_workbook(xlsx.write_workbook([("10 Nov", ROWS)]))
    return {x["name"]: x for x in tracker.parse_workbook(sheets, TODAY, **kw)["days"][0]["candidates"]}


class Record(unittest.TestCase):
    def test_record_has_every_filled_column_in_sheet_order_but_not_who_or_when(self):
        head = ["User", "Date", "Emp ID", "Email Id", "Late Login Duration", "Late Login Comment",
                "T. Logged hours", "T.Productive hours", "T.Idle hours", "No. of Break", "Reason", "Status"]
        row = ["Ann Lee", 46336, "5560 VM", "alee@x.com", 0.0215277, "Late login in Offline mode.",
               0.3, 0.1, 0.05, 2, "", None]
        c = wb_from(("10 Nov", [head, row]))["days"][0]["candidates"][0]
        self.assertEqual(c["record"], [["Late Login Duration", "0:31"], ["Late Login Comment", "Late login in Offline mode."],
                                       ["T. Logged hours", "7:12"], ["T.Productive hours", "2:24"],
                                       ["T.Idle hours", "1:12"], ["No. of Break", "2"]])


class Emails(unittest.TestCase):
    def test_company_domain_flags_every_other_domain_with_a_fix(self):
        c = people(domain="ccs-example.com")
        self.assertEqual(c["Bo Chen"]["email_issue"], "")
        self.assertEqual(c["Ann Lee"]["email_suggestion"], "ALee@ccs-example.com")
        self.assertIn("isn't the company domain", c["Ann Lee"]["email_issue"])
        self.assertEqual(c["Cy Park"]["email_suggestion"], "CPark@ccs-example.com")

    def test_directory_replaces_the_sheet_address_and_keeps_the_key(self):
        before = people(domain="ccs-example.com")
        after = people(domain="ccs-example.com", directory=[
            {"name": "ann lee", "email": "alee@ccs-example.com"},
            {"name": "Roy Dee", "email": "dravi@ccs-example.com"}])  # words in another order still match
        self.assertEqual(after["Ann Lee"]["email"], "alee@ccs-example.com")
        self.assertEqual(after["Ann Lee"]["email_source"], "directory")
        self.assertEqual(after["Ann Lee"]["email_issue"], "")
        self.assertEqual(after["Ann Lee"]["sheet_email"], "ALee@pcs-example.com")
        self.assertEqual(after["Ann Lee"]["key"], before["Ann Lee"]["key"])  # the sent log still lines up
        self.assertEqual(after["Dee  Roy"]["email"], "dravi@ccs-example.com")
        self.assertEqual(after["Cy Park"]["email_source"], "sheet")  # not listed: still checked

    def test_parse_directory(self):
        text = ("Ann Lee        alee@ccs-example.com\n\nSam Lee\tslee\n"
                "Mary Ann O'Neil   moneil\nnobody\nBad One   bad@@x\nann  lee  other@ccs-example.com\n")
        entries, problems = tracker.parse_directory(text, "ccs-example.com")
        self.assertEqual(entries, [{"name": "Ann Lee", "email": "alee@ccs-example.com"},
                                   {"name": "Sam Lee", "email": "slee@ccs-example.com"},
                                   {"name": "Mary Ann O'Neil", "email": "moneil@ccs-example.com"}])
        self.assertEqual(len(problems), 3)  # no address, invalid address, listed twice
        self.assertTrue(tracker.parse_directory("Sam Lee slee", "")[1])  # a username needs the domain


USAGE_HEAD = ["User", "Employee ID", "Date", "Logged Hours ", "Time On System ", "Time Away From System ",
              "MS Teams ", "ChatGPT ", "Youtube ", "Idle Time "]


class AppUsage(unittest.TestCase):
    def test_blocks_ids_and_names(self):
        day = ("10 Nov", [HEAD,
                          ["Ana Ruiz", NOV10, "5560 VM", "ana@x.com", None, 0.5, 0, 0.1, None],
                          ["Ben Ode", NOV10, 5618.0, "ben@x.com", None, 0, 0, 0, "Not logged"],
                          ["Cy Lo", NOV10, None, "cy@x.com", None, 0.4, 0, 0.2, None]])
        usage = ("App Usage", [
            USAGE_HEAD,
            ["Ana Ruiz", "5560 VM", 46335.0, 0.3, 0.2, None, 0.05, None, None, 0.1],  # 9 Nov block
            [None] * 10,
            USAGE_HEAD,                                                              # repeated header
            ["Ana Ruiz", 5560.0, NOV10, 0.5, 0.3, None, 0.1, 0.0416666667, 0.0069444444, 0.2],
            ["Cy Lo", None, NOV10, 0.4, 0.3, None, None, 0.1, None, 0.05],               # no id: by name
        ])
        wb = wb_from(day, usage)
        c = {x["name"]: x for x in wb["days"][0]["candidates"]}
        self.assertEqual(c["Ana Ruiz"]["apps"], [["MS Teams", 144], ["ChatGPT", 60], ["Youtube", 10]])
        self.assertEqual(c["Ana Ruiz"]["usage"]["logged"], 720)
        self.assertEqual(c["Cy Lo"]["apps"], [["ChatGPT", 144]])
        self.assertEqual(c["Ben Ode"]["apps"], [])           # no row: no activity, not an error
        self.assertEqual(wb["days"][0]["warnings"], [])
        self.assertIn("App Usage", wb["other_tabs"])

    def test_active_person_without_usage_row_is_noted(self):
        day = ("10 Nov", [HEAD, ["Ana Ruiz", NOV10, 1, "ana@x.com", None, 0.5, 0, 0.1, None],
                          ["Dee Dee", NOV10, 2, "dee@x.com", None, 0.5, 0, 0.1, None]])
        usage = ("App Usage", [USAGE_HEAD, ["Ana Ruiz", 1, NOV10, 0.5, 0.3, None, 0.1, None, None, 0.2]])
        d = wb_from(day, usage)["days"][0]
        self.assertTrue(any("No App Usage row" in w["msg"] and w["who"] == "Dee Dee" for w in d["warnings"]))

    def test_demo_workbook_matches_real_shape(self):
        wb = tracker.parse_workbook(xlsx.read_workbook(demo.workbook_bytes(TODAY)), TODAY)
        self.assertEqual(wb["usage_tab"], "App Usage")
        self.assertEqual(wb["days"][0]["date"], "2026-11-11")  # newest first
        active = [c for d in wb["days"] for c in d["candidates"] if c["logged"]]
        self.assertTrue(active and all(c["apps"] or c["usage"] for c in active))
        self.assertTrue(all(d["warnings"] == [] for d in wb["days"]), [d["warnings"] for d in wb["days"]])
        vik = next(c for c in wb["days"][0]["candidates"] if c["name"] == "Vikram Rao")
        self.assertEqual(vik["email_suggestion"], "VRao@example-tech.com")


@unittest.skipUnless(os.environ.get("NUDGE_REAL_TRACKER"), "set NUDGE_REAL_TRACKER to a real tracker .xlsx")
class RealTracker(unittest.TestCase):
    """Runs against a real tracker file kept outside the repo (it holds intern data)."""

    def test_reads_cleanly(self):
        wb = tracker.parse_workbook(xlsx.read_workbook(Path(os.environ["NUDGE_REAL_TRACKER"]).read_bytes()))
        self.assertTrue(wb["days"])
        for d in wb["days"]:
            self.assertIsNone(d["error"], d["sheet"])
            self.assertTrue(d["candidates"], d["sheet"])
            unreadable = [c["name"] for c in d["candidates"] if c["productive"] is None]
            self.assertEqual(unreadable, [], d["sheet"])
        flagged = {c["email"] for d in wb["days"] for c in d["candidates"] if c["email_issue"]}
        self.assertLessEqual(len(flagged), 2, flagged)  # real domains must not be flagged as typos


if __name__ == "__main__":
    unittest.main()

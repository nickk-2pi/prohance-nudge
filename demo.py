"""A made-up tracker shaped exactly like the real one (fictional people), for --demo and tests.

Day tabs: the real column headers, including the Date column. App Usage: blocks per date, each with its own
header row and a blank row between blocks, one row per person who was active that day.
"""
import random
from datetime import date, timedelta

import xlsx

HEADERS = ["User", "Type (Laptop/VDI)", "Date", "User Groups", "Emp ID", "Email Id", "Location", "Manager1",
           "Manager2", "Late Login Duration", "Late Login Comment", "Early Logout Duration", "Early Logout Comment",
           "T. Logged hours", "T.Time on System", "T.Time away  system", "T.Productive hours",
           "T.Non Productive hours", "T.Idle hours", "Total Break", "No. of Break", "Break Reasons", "Reason",
           "Manager Response", "Status"]
APPS = ["MS Teams ", "UNKNOWN AOS ", "Text Editors ", "Youtube ", "ChatGPT ", "Sharepoint ", "MS Outlook ",
        "Claude ", "MS Word ", "Zoom ", "GitHub ", "MS Excel ", "PDF Readers ", "Python "]
USAGE_HEADERS = ["User", "Employee ID", "Date", "Logged Hours ", "Time On System ", "Time Away From System ",
                 *APPS, "Idle Time "]

PEOPLE = [
    ("Asha Verma", "AVerma@example-tech.com", "5560 VM"), ("Rohan Mehta", "RMehta@example-tech.com", 5618),
    ("Lena Fischer", "LFischer@example-tech.com", 5565), ("Kabir Nair", "KNair@example-tech.com", "5592 VM"),
    ("Mei Lin", "MLin@example-labs.com", 5526), ("Daniel Okafor", "DOkafor@example-tech.com", 5487),
    ("Priya Iyer", "PIyer@example-tech.com", 5485), ("Tomás Rivera", "TRivera@example-tech.com", 5478),
    ("Sara Haddad", "SHaddad@example-labs.com", "5633(VM)"), ("Vikram Rao", "VRao@example-tech.compush", 5561),
    ("Nora Lindqvist", "NLindqvist@example-tech.com", 5562), ("Arjun Desai", "ADesai@example-tech.com", 5564),
    ("Ines Moreau", "IMoreau@example-tech.com", 5570), ("Yusuf Karim", "YKarim@example-tech.com", 5571),
]


def _t(minutes):
    return round(minutes / 1440, 10)


def _serial(d):
    return float((d - date(1899, 12, 30)).days)


def workbook_bytes(today=None, days=7, seed=7):
    today = today or date.today()
    rnd = random.Random(seed)
    tabs, d = [], today - timedelta(days=1)
    while len(tabs) < days:
        if d.weekday() < 5:
            tabs.append(d)
        d -= timedelta(days=1)
    sheets, usage_rows = [], []
    for day in reversed(tabs):
        rows = [HEADERS]
        usage_rows += [USAGE_HEADERS]
        for name, email, emp in PEOPLE:
            kind = rnd.random()
            if kind < 0.18:  # no activity at all: no App Usage row either
                logged = prod = idle = late = 0
                reason = "Not logged"
            else:
                logged = rnd.randint(240, 720)
                prod = rnd.randint(20, min(logged, 460)) if kind < 0.55 else rnd.randint(240, min(max(logged, 250), 520))
                idle = max(0, logged - prod - rnd.randint(0, 60))
                late = rnd.choice([0, 0, rnd.randint(5, 110)])
                reason = f"{prod // 60}:{prod % 60:02d} hr unaccounted" if rnd.random() < 0.15 else ""
            rows.append([
                name, "Laptop", _serial(day), "TDP US Interns", emp, email, None, "Jordan Blake", "IT Support",
                _t(late), "Late Login" if late else None, _t(rnd.choice([0, 0, rnd.randint(2, 300)])) if logged else 0,
                None, _t(logged), _t(round(logged * 0.6)), 0, _t(prod), 0, _t(idle), 0, 0, None, reason or None,
                None, None,
            ])
            if logged:
                left, apps = prod, []
                for _ in APPS:
                    take = rnd.choice([0, 0, rnd.randint(0, max(1, left // 2))])
                    apps.append(_t(take) if take else None)
                    left -= take
                usage_rows.append([name, emp, _serial(day), _t(logged), _t(round(logged * 0.6)), None, *apps, _t(idle)])
        usage_rows.append([None] * len(USAGE_HEADERS))
        sheets.append((f"{day.day:02d} {day.strftime('%b')}", rows))
    sheets.append(("App Usage", usage_rows))
    return xlsx.write_workbook(sheets)

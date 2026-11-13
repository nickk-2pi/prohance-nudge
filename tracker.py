"""Turn the ProHance daily tracker workbook into one candidate list per day tab, plus data checks.

Rules that keep this robust:
- Columns are found by header text, never by letter (the sheet hides, adds and reorders columns).
- A day tab is a tab named like a date ("10 Nov"). Its Date column, when present, is cross-checked.
- Nothing raises on bad data: a row or tab that can't be read becomes a warning, and the rest still works.
- Hours become whole minutes here. Who is "under the threshold" is decided in the UI, so the threshold can
  change without re-reading the file.
"""
import re
from collections import Counter
from datetime import date, datetime, timedelta

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_TAB_DAY_FIRST = re.compile(r"^\s*(\d{1,2})(?:st|nd|rd|th)?[\s\-_/.]*([A-Za-z]{3,9})\.?(?:[\s\-_/,]*(\d{2,4}))?\s*$")
_TAB_MONTH_FIRST = re.compile(r"^\s*([A-Za-z]{3,9})\.?[\s\-_/]*(\d{1,2})(?:st|nd|rd|th)?(?:[\s\-_/,]*(\d{2,4}))?\s*$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
DURATION_HEADER = re.compile(r"hour|hrs|\bhr\b|time|idle|logged|productive|late|early|break h|duration")
EXCEL_EPOCH = date(1899, 12, 30)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def tab_date(name, today):
    """'10 Nov' / 'Nov 10' / '10-Nov-26' -> date. Without a year: the latest year not after next week."""
    m = _TAB_DAY_FIRST.match(name or "")
    if m:
        day, mon, year = m.group(1), m.group(2), m.group(3)
    else:
        m = _TAB_MONTH_FIRST.match(name or "")
        if not m:
            return None
        mon, day, year = m.group(1), m.group(2), m.group(3)
    month = MONTHS.get(mon[:3].lower())
    if not month:
        return None
    years = [int(year) + (2000 if len(year) == 2 else 0)] if year else [today.year, today.year - 1]
    for y in years:
        try:
            d = date(y, month, int(day))
        except ValueError:
            continue
        if year or d <= today + timedelta(days=7):
            return d
    return None


def cell_date(v):
    """A Date cell -> date, or None. Excel serial numbers, datetimes and common text forms."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        if 20000 < v < 80000:  # 1954..2119 as Excel serials
            return EXCEL_EPOCH + timedelta(days=int(v))
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d-%b-%Y", "%d %b %Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def minutes(v):
    """A ProHance duration cell -> whole minutes, or None when it is not a duration."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if v != v or v < 0:  # NaN or negative
            return None
        if v > 1000:          # a full date-time: keep the time of day
            v = v % 1
        elif v > 1:           # typed as decimal hours (5.5); a day's log never exceeds 24 h
            return round(v * 60)
        return round(v * 1440)
    s = str(v).strip().lower()
    if not s or s in ("-", "na", "n/a"):
        return None
    m = re.match(r"^(\d{1,3}):(\d{2})(?::(\d{2}))?\s*(am|pm)?$", s)
    if m:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        if m.group(4):  # "12:29:00 AM" means 0:29
            h = h % 12 + (12 if m.group(4) == "pm" else 0)
        return h * 60 + mi + round(sec / 60)
    m = re.match(r"^(?:(\d+(?:\.\d+)?)\s*h(?:rs?|ours?)?)?\s*(?:(\d+)\s*m(?:in(?:s|utes?)?)?)?$", s)
    if m and (m.group(1) or m.group(2)):
        return round(float(m.group(1) or 0) * 60) + int(m.group(2) or 0)
    try:
        return minutes(float(s))
    except ValueError:
        return None


def hm(mins):
    if mins is None:
        return ""
    return f"{mins // 60}:{mins % 60:02d}"


def emp_key(v):
    """'5560 VM', '5560', 5560.0 -> '5560'. Empty when there is no number."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    m = re.search(r"\d+", str(v))
    if not m:
        return ""
    return m.group(0).lstrip("0") or "0"


# field -> test on the normalised header text; the first matching column wins
FIELDS = {
    "email": lambda h: "email" in h or h in ("mail", "mail id"),
    "productive": lambda h: "productive" in h and "non" not in h.split() and "unproductive" not in h,
    "name": lambda h: h in ("user", "user name", "name", "candidate", "candidate name", "employee",
                            "employee name", "full name", "intern", "intern name"),
    "date": lambda h: h in ("date", "day", "tracker date", "activity date"),
    "logged": lambda h: "logged" in h,
    "idle": lambda h: "idle" in h,
    "reason": lambda h: ("reason" in h or "remark" in h or "comment" in h) and "break" not in h
                        and "late" not in h and "early" not in h,
    "manager": lambda h: h.startswith("manager") and "response" not in h,
    "emp_id": lambda h: h in ("emp id", "employee id", "empid", "emp no", "employee code", "emp code"),
}


def _find_header(rows):
    for i, row in enumerate(rows[:25]):
        heads = [norm(c) if isinstance(c, str) else "" for c in row]
        cols = {}
        for field, test in FIELDS.items():
            for j, h in enumerate(heads):
                if h and j not in cols.values() and test(h):
                    cols[field] = j
                    break
        if "email" in cols and "productive" in cols:
            return i, cols
    return None, None


def _text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _display(header, v):
    h = norm(header)
    if isinstance(v, (int, float)) and not isinstance(v, bool) and DURATION_HEADER.search(h) \
            and "no of" not in h and "count" not in h:
        return hm(minutes(v))
    return _text(v)


def first_name(name):
    first = (name or "").split()[0] if (name or "").split() else ""
    return first.title() if first.isupper() or first.islower() else first


def parse_sheet(rows, tab_day=None):
    """-> (candidates, headers, error, warnings). Never raises on bad cell data."""
    hi, cols = _find_header(rows)
    if hi is None:
        return [], [], "No header row with an Email column and a Productive hours column", []
    headers = [_text(h) for h in rows[hi]]
    keyed = set(cols.values())
    out, warnings = [], []
    seen_email = {}
    date_counts = Counter()
    for r, row in enumerate(rows[hi + 1:], hi + 2):
        def get(field):
            j = cols.get(field)
            return row[j] if j is not None and j < len(row) else None

        name, email = _text(get("name")), _text(get("email"))
        if not name and not email:
            if any(v not in (None, "") for v in row):
                warnings.append({"level": "info", "row": r, "msg": "Row has data but no name or email; skipped"})
            continue
        if norm(name) in ("total", "grand total", "totals"):
            continue
        prod_raw = get("productive")
        prod = minutes(prod_raw)
        logged = minutes(get("logged"))
        who = name or email
        if prod is None:
            if _text(prod_raw):
                warnings.append({"level": "warn", "row": r, "who": who,
                                 "msg": f"Productive hours “{_text(prod_raw)}” isn't a time; left out"})
            else:
                warnings.append({"level": "warn", "row": r, "who": who, "msg": "Productive hours is blank"})
        elif logged is not None and prod > logged + 5:
            warnings.append({"level": "warn", "row": r, "who": who,
                             "msg": f"Productive {hm(prod)} is more than logged {hm(logged)}"})
        key = email.lower() or name.lower()
        if key in seen_email:
            warnings.append({"level": "warn", "row": r, "who": who,
                             "msg": f"Appears twice on this tab (also row {seen_email[key]})"})
        seen_email.setdefault(key, r)
        if "date" in cols:
            d = cell_date(get("date"))
            if d:
                date_counts[d] += 1
                if tab_day and d != tab_day:
                    warnings.append({"level": "warn", "row": r, "who": who,
                                     "msg": f"Date column says {d:%d %b %Y}, but the tab is {tab_day:%d %b %Y}"})
        extra = [[headers[j], _display(headers[j], v)] for j, v in enumerate(row)
                 if j not in keyed and j < len(headers) and headers[j] and v not in (None, "")]
        out.append({
            "row": r,
            "name": name or email.split("@")[0],
            "first_name": first_name(name) or email.split("@")[0],
            "email": email,
            "productive": prod,
            "productive_raw": _text(prod_raw),
            "logged": logged,
            "idle": minutes(get("idle")),
            "reason": _text(get("reason")),
            "manager": _text(get("manager")),
            "emp_id": _text(get("emp_id")),
            "extra": extra,
            "apps": [],
            "usage": None,
        })
    return out, headers, None, warnings


# ---------------------------------------------------------------- App Usage tab

USAGE_SUMMARY = {"logged hours": "logged", "time on system": "on_system", "time away from system": "away",
                 "idle time": "idle", "productive hours": "productive"}


def parse_app_usage(rows):
    """The App Usage tab: blocks of [header row, one row per person per date], separated by blank rows.
    -> ({(iso_date, 'emp:5560' or 'name:...'): {"apps": [[app, minutes]...], <summary fields>}}, warnings)."""
    usage, warnings = {}, []
    cols = None
    for r, row in enumerate(rows, 1):
        cells = [norm(v) if isinstance(v, str) else "" for v in row]
        if "user" in cells and "date" in cells:  # a (repeated) header row
            cols = {"user": cells.index("user"), "date": cells.index("date"),
                    "emp": next((j for j, h in enumerate(cells) if h in ("employee id", "emp id")), None),
                    "apps": {}, "summary": {}}
            for j, raw in enumerate(row):
                h = norm(raw) if isinstance(raw, str) else ""
                if not h or j in (cols["user"], cols["date"], cols["emp"]):
                    continue
                if h in USAGE_SUMMARY:
                    cols["summary"][j] = USAGE_SUMMARY[h]
                else:
                    cols["apps"][j] = str(raw).strip()
            continue
        if not any(v not in (None, "") for v in row):
            continue
        if cols is None:
            warnings.append({"level": "info", "row": r, "msg": "App Usage row before any header row; skipped"})
            continue

        def at(j):
            return row[j] if j is not None and j < len(row) else None

        name, d = _text(at(cols["user"])), cell_date(at(cols["date"]))
        if not name or not d:
            warnings.append({"level": "info", "row": r, "msg": "App Usage row without a user or a readable date; skipped"})
            continue
        entry = {"apps": []}
        for j, field in cols["summary"].items():
            entry[field] = minutes(at(j))
        for j, app in cols["apps"].items():
            m = minutes(at(j))
            if m:
                entry["apps"].append([app, m])
        entry["apps"].sort(key=lambda a: -a[1])
        emp = emp_key(at(cols["emp"])) if cols["emp"] is not None else ""
        if emp:
            usage[(d.isoformat(), "emp:" + emp)] = entry
        usage[(d.isoformat(), "name:" + norm(name))] = entry
    return usage, warnings


# ---------------------------------------------------------------- email checks

def norm_name(s):
    """'  Huimin  GUO ' -> 'huimin guo': for matching directory names to the tracker's."""
    return " ".join(re.sub(r"[^a-z]+", " ", str(s or "").lower()).split())


def parse_directory(text, domain=""):
    """Pasted lines of 'Name<tab or spaces>address' -> ([{name, email}], [problems]).

    The address is the line's last word. A bare username (no @) gets @domain added. Blank lines are skipped.
    """
    domain = (domain or "").strip().lstrip("@").lower()
    entries, problems, seen = [], [], set()
    for n, line in enumerate(str(text or "").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(None, 1)
        if len(parts) < 2:
            problems.append(f"Line {n}: “{line}” needs a name and an address")
            continue
        name, addr = parts[0].strip(" \t,;:-"), parts[1].strip(" <>,;")
        if "@" not in addr:
            if not domain:
                problems.append(f"Line {n}: “{addr}” is a username; set the company email domain first")
                continue
            addr = f"{addr}@{domain}"
        if not EMAIL_RE.match(addr):
            problems.append(f"Line {n}: “{addr}” isn't a valid email address")
            continue
        if norm_name(name) in seen:
            problems.append(f"Line {n}: {name} is listed twice")
            continue
        seen.add(norm_name(name))
        entries.append({"name": name, "email": addr})
    return entries, problems


def _directory_lookup(directory):
    exact, loose = {}, {}
    for e in directory or []:
        n = norm_name(e.get("name"))
        if n and e.get("email"):
            exact[n] = e["email"]
            loose.setdefault(frozenset(n.split()), e["email"])  # same words in another order
    return lambda name: exact.get(norm_name(name)) or loose.get(frozenset(norm_name(name).split()))


def _check_emails(days, directory=None, domain=""):
    """Settle each person's address and flag doubtful ones.

    1. The email directory (Settings) wins: its address replaces the sheet's.
    2. With a company domain set, any other domain is flagged, with the fix username@domain.
    3. Without one, a domain used by two or more people counts as real, and a fix is only suggested when a lone
       domain is a real one with extra characters on the end (example.compush -> example.com).
    The sheet's address is kept in sheet_email; the person's key (and so the sent log) never changes.
    """
    domain = (domain or "").strip().lstrip("@").lower()
    lookup = _directory_lookup(directory)
    people = {}
    for d in days:
        for c in d["candidates"]:
            e = c.get("sheet_email", c["email"]).strip().lower()
            if e and EMAIL_RE.match(e):
                people.setdefault(e.split("@", 1)[1], set()).add(e)
    known = {dom for dom, addrs in people.items() if len(addrs) >= 2}
    for d in days:
        for c in d["candidates"]:
            c.setdefault("sheet_email", c["email"])
            c["email"], c["email_source"] = c["sheet_email"], "sheet"
            c["email_issue"] = c["email_suggestion"] = ""
            listed = lookup(c["name"])
            if listed:
                c["email"], c["email_source"] = listed, "directory"
                continue
            e = c["email"].strip()
            if not e:
                c["email_issue"] = "No email address in the sheet"
                continue
            if not EMAIL_RE.match(e):
                c["email_issue"] = "Not a valid email address"
                continue
            local, dom = e.split("@", 1)[0], e.split("@", 1)[1].lower()
            if domain:
                if dom != domain:
                    c["email_issue"] = (f"@{dom} looks like a typo of @{domain}" if dom.startswith(domain)
                                        else f"@{dom} isn't the company domain @{domain}")
                    c["email_suggestion"] = f"{local}@{domain}"
                continue
            if dom in known or len(people) < 2:
                continue
            c["email_issue"] = f"Nobody else uses @{dom}"
            fixes = [k for k in known if dom.startswith(k) and len(dom) > len(k)]
            if fixes:
                good = max(fixes, key=len)
                c["email_issue"] = f"@{dom} looks like a typo of @{good}"
                c["email_suggestion"] = e.split("@", 1)[0] + "@" + good


# ---------------------------------------------------------------- the whole workbook

def parse_workbook(sheets, today=None, directory=None, domain=""):
    """sheets from xlsx.read_workbook -> {days: [...newest first], other_tabs, warnings}.

    directory ([{name, email}]) and domain come from Settings; see _check_emails."""
    today = today or date.today()
    days, other, file_warnings = [], [], []
    usage, usage_tab = {}, None
    for s in sheets:
        d = tab_date(s["name"], today)
        if not d:
            other.append(s["name"])
            if "usage" in norm(s["name"]) and usage_tab is None:
                usage_tab = s["name"]
                try:
                    usage, uw = parse_app_usage(s["rows"])
                except Exception as e:  # noqa: BLE001 - a broken optional tab must not stop the day tabs
                    usage, uw = {}, [{"level": "warn", "msg": f"Couldn't read the App Usage tab: {e}"}]
                file_warnings += [{**w, "tab": s["name"]} for w in uw]
            continue
        try:
            candidates, headers, error, warnings = parse_sheet(s["rows"], d)
        except Exception as e:  # noqa: BLE001 - one broken tab must not hide the others
            candidates, headers, error, warnings = [], [], f"Couldn't read this tab: {type(e).__name__}: {e}", []
        days.append({"sheet": s["name"], "date": d.isoformat(), "hidden": s["hidden"], "headers": headers,
                     "error": error, "candidates": candidates, "warnings": warnings})

    for d in days:
        for c in d["candidates"]:
            c["key"] = f'{d["date"]}|{(c["email"] or c["name"]).lower()}'
    dupes = Counter(d["date"] for d in days)
    for d in days:
        if dupes[d["date"]] > 1:
            for c in d["candidates"]:
                c["key"] = f'{d["date"]}#{d["sheet"]}|{(c["email"] or c["name"]).lower()}'
            file_warnings.append({"level": "warn", "tab": d["sheet"],
                                  "msg": f"Another tab is also for {d['date']}; both are kept separately"})

    # attach App Usage rows; a missing row is normal when the person wasn't active that day
    usage_dates = {k[0] for k in usage}
    for d in days:
        for c in d["candidates"]:
            e = usage.get((d["date"], "emp:" + emp_key(c["emp_id"]))) if emp_key(c["emp_id"]) else None
            e = e or usage.get((d["date"], "name:" + norm(c["name"])))
            if e:
                c["usage"] = {k: v for k, v in e.items() if k != "apps"}
                c["apps"] = e["apps"]
            elif usage_tab and d["date"] in usage_dates and (c["logged"] or 0) > 0:
                d["warnings"].append({"level": "info", "row": c["row"], "who": c["name"],
                                      "msg": f"No App Usage row, though logged {hm(c['logged'])}"})
    day_dates = {d["date"] for d in days}
    for iso in sorted(usage_dates - day_dates):
        file_warnings.append({"level": "info", "tab": usage_tab,
                              "msg": f"App Usage has rows for {iso}, which has no day tab"})

    _check_emails(days, directory, domain)
    days.sort(key=lambda d: (d["date"], d["sheet"]), reverse=True)
    return {"days": days, "other_tabs": other, "warnings": file_warnings, "usage_tab": usage_tab}

"""Nudge from the command line: who's under the threshold, and what the data checks found.

    python cli.py check --file "TDP US Interns (Nov Daily Tracker).xlsx"
    python cli.py check --file tracker.xlsx --day "10 Nov"          (or --day 2026-11-10)
    python cli.py check --link "https://...sharepoint.com/:x:/..."   (token in MS_GRAPH_ACCESS_TOKEN)
    python cli.py check --cached                                     (the copy the app last loaded)
    python cli.py outlook-check                                      (will emails open in classic Outlook?)

Exit codes: 0 fine, 1 couldn't read the source, 2 a day tab couldn't be read.
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

import tracker
import xlsx
from msgraph import Graph, GraphError, describe_token

ROOT = Path(__file__).parent


def load(a):
    if a.file:
        return Path(a.file).read_bytes(), Path(a.file).name
    if a.cached:
        p = ROOT / "data" / "cache" / "workbook.xlsx"
        if not p.exists():
            raise ValueError("No cached workbook yet; load the tracker in the app first.")
        return p.read_bytes(), "cached copy"
    token = os.environ.get("MS_GRAPH_ACCESS_TOKEN", "").strip()
    if not token:
        raise ValueError("Set MS_GRAPH_ACCESS_TOKEN (Graph Explorer → Access token) to read from SharePoint.")
    info = describe_token(token)
    g = Graph(info["token"])
    item = g.resolve_link(a.link)
    return g.download(item["parentReference"]["driveId"], item["id"]), item.get("name", "SharePoint file")


def pick_day(days, want):
    if not want:
        return None
    for d in days:
        if want.strip().lower() in (d["sheet"].strip().lower(), d["date"]):
            return d
    raise ValueError(f"No tab for {want!r}. Tabs: {', '.join(d['sheet'] for d in days)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="summary per day, or one day's list, plus data checks")
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="a downloaded .xlsx")
    src.add_argument("--link", help="the SharePoint sharing link")
    src.add_argument("--cached", action="store_true", help="the copy the app last loaded")
    c.add_argument("--day", help='a tab name ("10 Nov") or date (2026-11-10)')
    c.add_argument("--threshold", default="4:00", help="h:mm (default 4:00)")
    sub.add_parser("outlook-check", help="will emails open in classic Outlook? (touches nothing)")
    a = ap.parse_args()

    if a.cmd == "outlook-check":
        import outlook
        st = outlook.status()
        exe = outlook.outlook_exe()
        print(f"classic Outlook: {exe or 'not found'}")
        print(f"'New Outlook' toggle on: {st['new_outlook_on']}")
        if not exe:
            print("Emails will open with whatever app opens .eml files on this PC.")
            return 1
        if st["new_outlook_on"]:
            print("Turn the toggle off so emails open in classic Outlook as new messages.")
            return 1
        print("Emails will open in classic Outlook as new messages. (Nudge doesn't connect to Outlook; nothing was opened.)")
        return 0

    try:
        h, _, m = a.threshold.partition(":")
        thr = int(h) * 60 + int(m or 0)
        data, label = load(a)
        wb = tracker.parse_workbook(xlsx.read_workbook(data), date.today())
        day = pick_day(wb["days"], a.day)
    except (ValueError, OSError, GraphError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - e.g. not a zip file
        print(f"Error: couldn't read the workbook ({type(e).__name__}: {e})", file=sys.stderr)
        return 1

    print(f"{label}: {len(wb['days'])} day tabs" + (f", other tabs: {', '.join(wb['other_tabs'])}" if wb["other_tabs"] else ""))
    bad_tab = any(d["error"] for d in wb["days"])
    if day is None:
        print(f"\n{'Tab':<10} {'Date':<11} {'People':>6} {'Under ' + a.threshold:>11} {'No activity':>12} {'Checks':>7}")
        for d in wb["days"]:
            cs = d["candidates"]
            none = sum(1 for x in cs if x["productive"] == 0 and not x["logged"])
            under = sum(1 for x in cs if x["productive"] is not None and x["productive"] < thr) - none
            print(f"{d['sheet']:<10} {d['date']:<11} {len(cs):>6} {under:>11} {none:>12} {len(d['warnings']):>7}"
                  + (f"   ERROR: {d['error']}" if d["error"] else ""))
        print("\nUse --day \"10 Nov\" for one day's list.")
    else:
        if day["error"]:
            print(f"\n{day['sheet']}: {day['error']}")
        rows = sorted((x for x in day["candidates"] if x["productive"] is not None and x["productive"] < thr),
                      key=lambda x: x["productive"])
        print(f"\n{day['sheet']} ({day['date']}): {len(rows)} under {a.threshold}\n")
        print(f"{'Name':<26} {'Productive':>10} {'Logged':>7} {'Top app':<22} Email")
        for x in rows:
            top = f"{x['apps'][0][0]} {tracker.hm(x['apps'][0][1])}" if x["apps"] else "-"
            flag = f"   <- {x['email_issue']}" if x["email_issue"] else ""
            print(f"{x['name'][:26]:<26} {tracker.hm(x['productive']):>10} {tracker.hm(x['logged']) or '-':>7} {top[:22]:<22} {x['email']}{flag}")
    days = [day] if day else wb["days"]
    warns = [{**w, "tab": d["sheet"]} for d in days for w in d["warnings"]] + wb["warnings"]
    if warns:
        print(f"\nData checks ({len(warns)}):")
        for w in warns:
            where = " · ".join(x for x in (w.get("tab"), f"row {w['row']}" if w.get("row") else "", w.get("who")) if x)
            print(f"  [{w['level']}] {where + ': ' if where else ''}{w['msg']}")
    else:
        print("\nData checks: all clear")
    return 2 if bad_tab else 0


if __name__ == "__main__":
    sys.exit(main())

# Nudge

Prepares emails for interns whose ProHance productive hours fell short. Nudge reads the daily tracker (one
tab per day, e.g. "10 Nov", plus the App Usage tab), lists everyone under the threshold (4:00 by default)
with a ready email, and opens the ones you pick in **classic Outlook** as new, filled-in, formatted messages.
You check each one and press **Send**, then tick them off in Nudge with **Mark sent**.

Nudge never sends email and never automates Outlook: it writes each email as an unsent `.eml` file and asks
Windows to open it in Outlook, like double-clicking it. It runs on your machine only and needs nothing but
Python (standard library).

## Set up on a new PC

Needs Windows, **Python 3.9 or newer** and **classic Outlook** (new Outlook can't open the emails as new
messages; turn off its "New Outlook" toggle).

1. Install Python from [python.org](https://www.python.org/downloads/) and tick **Add python.exe to PATH**.
   The Microsoft Store's "python" placeholder doesn't count: if typing `python --version` in a terminal opens
   the Store or prints nothing, install from python.org.
2. Get the code: `git clone <this repo's URL>` (or **Code → Download ZIP** on GitHub and unzip it).
3. Check it works: `python -m unittest discover -s tests` should end with `OK`.
4. Double-click **Start Nudge.cmd**. It opens http://localhost:8770 in your browser and leaves a minimized
   **Nudge server** window on the taskbar (closing it stops Nudge). If something is wrong, the launcher
   or that window says what. You can also start it by hand from this folder: `python server.py --open`.
5. In **Settings**: your name for the sign-off, and the **Extra recipients** (who goes in To next to the
   candidate, and who in Cc). These are saved on your PC only, in `data/`.
6. Load the tracker: paste the SharePoint link plus a token (see below), or open a downloaded copy.

Your settings, sent log and email files live in `data/` and are never committed. Each person's copy keeps its
own log, so agree who emails which days.

**Known issue:** on at least one PC, classic Outlook froze when Nudge handed it an email file (and earlier when
it was automated). Open Outlook **before** using **Open in Outlook**; Nudge refuses if Outlook's main window
isn't open. If Outlook still freezes, use **Copy** on a person and paste the email into a new message instead.

## Daily use

1. Open Nudge: double-click **Start Nudge.cmd** (or the desktop shortcut, see below), or `python server.py --open`.
2. Tracker: either paste today's access token ([Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer)
   → sign in → **Access token** tab → copy; memory only, lasts about a day) so Nudge reads the SharePoint
   link, or **open a downloaded copy** (.xlsx). The link is remembered; paste next month's in **Settings**.
3. Pick a day, tick people (those under the threshold are pre-ticked), **Open in Outlook**.
4. In Outlook, check each message and press Send. Back in Nudge, **Mark sent** (top bar) lists everyone
   opened but not marked; untick anyone you didn't send. **Not sent** puts a person back on the to-do list.

The email files are kept in `data/outbox/<date>/` (they hold intern data; gitignored).

```text
python server.py --open            the app, http://localhost:8770
python server.py --demo --open     made-up data; nothing touches Outlook (data-demo/)
python cli.py check --file tracker.xlsx [--day "10 Nov"]     summary or one day, plus data checks
python cli.py check --cached       the copy the app last loaded
python -m unittest discover -s tests
```

**Start automatically (optional):** `powershell -ExecutionPolicy Bypass -File install-autostart.ps1` starts
Nudge silently when you sign in to Windows and adds a **Nudge** desktop shortcut. Undo with `-Remove`.

## The token

Only for reading the tracker from SharePoint. A token from Graph Explorer acts as you for about a day (24 h
when your tenant issues long-lived tokens); Nudge needs `Files.Read.All` or `Sites.Read.All` from it. The app
shows what the pasted token allows and when it expires. Treat it like a password: don't paste it into chats,
tickets or files.

## How the tracker is read (`tracker.py`)

- **Day tabs:** tabs named like a date (`10 Nov`, `Nov 10`, `10-Nov-26`). The tab's **Date** column is
  checked against the tab name.
- **Columns by header text**, never by letter: `User`, `Email Id`, `Emp ID`, `T.Productive hours` (not "Non
  Productive"), `T. Logged hours`, `T.Idle hours`, `Reason` (not "Break Reasons"). The header can be on any
  of the first 25 rows.
- **Durations:** Excel time values (fractions of a day), text like `5:33` or `2.5h`, decimal hours.
- **App Usage tab:** blocks per date, each with its own header row: User, Employee ID, Date, Logged Hours,
  Time On System, Time Away From System, one column per app, Idle Time. Rows are matched to the day tabs by
  Employee ID (`5560 VM` = `5560`), then by name. No row means no activity that day, which is not an error.
- **Nothing fails silently or loudly:** a bad row becomes a **data check** and the rest still works; a tab
  that can't be read is shown as such and the other tabs still load. Checks: blank or unreadable hours,
  productive above logged, duplicates, Date column vs tab, active people without an App Usage row,
  email addresses whose domain nobody else uses (with a fix for things like `.compush`).
- **Statuses:** under threshold, or "No activity" (productive and logged both 0:00, own template).

`tests/` covers each rule. `NUDGE_REAL_TRACKER=<path to a real tracker>` also runs a test against a real
file (keep real files out of the repo: they hold intern data).

## Files (`data/`, gitignored)

| File | What |
|---|---|
| `config.json` | tracker link, threshold, Cc, sign-off name, templates |
| `ledger.jsonl` | one line per email opened in Outlook, marked sent, skipped, or put back, with the email's HTML |
| `outbox/` | the `.eml` files Nudge opened in Outlook |
| `edits.json` | per-person edits to an email |
| `cache/` | the last downloaded workbook (refreshed only when SharePoint says it changed) |
| `logs/app.jsonl` | JSON log of requests and Graph timings; never the token |

## Keyboard

`J`/`K` move · `X` select (Shift for a range) · `E` edit email · `/` search · `[` `]` previous/next day ·
`1`–`6` filters · `R` refresh · `Ctrl+Enter` create drafts for the selection

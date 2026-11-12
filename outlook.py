"""Hand emails to classic Outlook as unsent .eml files.

Nudge writes each email as an .eml file marked "X-Unsent: 1" and asks Windows to open it with classic Outlook
(OUTLOOK.EXE /eml), exactly like double-clicking it. Outlook opens it as a new, formatted message with To, Cc
and Subject filled in; you check it and press Send.

Nudge never automates Outlook (no COM): connecting to Outlook from another program froze it on this PC.
Because of that, Nudge can't see your Sent folder; you mark people as sent in Nudge after sending.
"""
import os
import re
import subprocess
import time
import winreg
from email import policy
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html import unescape
from pathlib import Path

OUTLOOK_CANDIDATES = [
    r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE",
    r"C:\Program Files\Microsoft Office\Office16\OUTLOOK.EXE",
    r"C:\Program Files (x86)\Microsoft Office\Office16\OUTLOOK.EXE",
]


class OutlookError(Exception):
    def __init__(self, message, code="outlook"):
        super().__init__(message)
        self.code, self.message = code, message


def outlook_exe():
    try:  # where the installed classic Outlook says it lives
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE") as k:
            p = winreg.QueryValueEx(k, None)[0].strip('"')
            if os.path.isfile(p):
                return p
    except OSError:
        pass
    return next((p for p in OUTLOOK_CANDIDATES if os.path.isfile(p)), None)


def status():
    """Is classic Outlook installed, and is the 'new Outlook' toggle on?"""
    new_on = False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Office\16.0\Outlook\Preferences") as k:
            new_on = winreg.QueryValueEx(k, "UseNewOutlook")[0] == 1
    except OSError:
        pass
    return {"installed": bool(outlook_exe()), "new_outlook_on": new_on}


def _outlook_pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq OUTLOOK.EXE", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, creationflags=0x08000000).stdout
    return {int(row.split('","')[1]) for row in out.splitlines() if row.lower().startswith('"outlook.exe"')}


def main_window_open():
    """Is classic Outlook running with its main window showing? Looks at windows only; never talks to Outlook.

    Outlook started by opening an email file (OUTLOOK.EXE /eml) runs without a main window, and then you can't
    open Outlook normally until it's closed. So Nudge only hands over emails when the main window is there."""
    import ctypes
    from ctypes import wintypes
    pids = _outlook_pids()
    if not pids:
        return False
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if cls.value == "rctrl_renwnd32":  # Outlook's main (Explorer) window
                found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    return bool(found)


def require_open():
    if main_window_open():
        return
    if _outlook_pids():
        raise OutlookError("Outlook is running without its main window (probably from an email file opened earlier). "
                           "Close any Outlook message windows, end OUTLOOK.EXE in Task Manager if needed, open Outlook "
                           "normally, then try again.", "no_main_window")
    raise OutlookError("Open classic Outlook first and wait for your mailbox to load, then try again. "
                       "Nudge doesn't start Outlook itself.", "not_running")


def html_to_text(html):
    """A readable plain-text version for mail apps that don't show HTML."""
    t = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</(p|div|tr|table)>", "\n", t)
    t = re.sub(r"(?i)</td>", "   ", t)
    t = unescape(re.sub(r"<[^>]+>", "", t))
    t = "\n".join(line.strip() for line in t.splitlines())
    return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"


def _safe(name):
    return re.sub(r"[^A-Za-z0-9 ._-]+", "", name).strip()[:60] or "email"


def write_eml(folder, name, to, cc, subject, html):
    """Write one unsent message; returns its path."""
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="nudge.local")
    msg["X-Unsent"] = "1"  # tells Outlook to open it as a new message to send, not as a received one
    # base64 bodies and CRLF line endings: Outlook mangled quoted-printable soft line breaks written with bare
    # LF ("short" showed as "s=ort"), so no line-wrapping encoding is used at all.
    msg.set_content(html_to_text(html), cte="base64")
    msg.add_alternative(html, subtype="html", cte="base64")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{_safe(name)}.eml"
    n = 2
    while path.exists():
        path = folder / f"{_safe(name)} ({n}).eml"
        n += 1
    path.write_bytes(msg.as_bytes(policy=policy.SMTP))
    return str(path)


def open_eml(path):
    """Open the message in classic Outlook, like double-clicking the file. Doesn't wait for Outlook."""
    if not os.path.isfile(path):
        raise OutlookError("That email file isn't there any more. Create it again.", "gone")
    require_open()  # never let opening a file start Outlook in its windowless single-message mode
    exe = outlook_exe()
    try:
        if exe:
            subprocess.Popen([exe, "/eml", path], close_fds=True)
        else:
            os.startfile(path)  # whatever opens .eml files on this PC
    except OSError as e:
        raise OutlookError(f"Windows couldn't open the email in Outlook: {e}", "open_failed") from None


def open_many(paths, gap=0.6):
    """Open several messages one after another, giving Outlook a moment between them."""
    for i, p in enumerate(paths):
        if i:
            time.sleep(gap)
        open_eml(p)

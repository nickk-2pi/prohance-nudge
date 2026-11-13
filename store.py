"""Everything kept on disk under the data folder: settings, the ledger, draft edits, the cached workbook.
No secrets are stored: the access token lives in memory only."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TEMPLATES = {
    "low": {
        "subject": "Action required: productive time below {threshold_words} on {date_short}",
        "body": (
            "Hi {first_name},\n\n"
            "ProHance recorded {productive_words} of productive time for you on {date}. "
            "The required minimum is {threshold_words} a day.\n\n"
            "Your ProHance record for the day:\n\n"
            "{details}\n\n"
            "You must reply to this email at the earliest, as soon as you see it. In your reply, explain why "
            "your productive time was below the required minimum and account for the rest of your logged time, "
            "with supporting evidence.\n\n"
            "Regards,\n{sender_name}"
        ),
    },
    "none": {
        "subject": "Action required: no ProHance activity on {date_short}",
        "body": (
            "Hi {first_name},\n\n"
            "ProHance has no activity recorded for you on {date}.\n\n"
            "Your ProHance record for the day:\n\n"
            "{details}\n\n"
            "You must reply to this email at the earliest, as soon as you see it. In your reply, explain why "
            "no activity was recorded for you on this day, with supporting evidence.\n\n"
            "Regards,\n{sender_name}"
        ),
    },
}

# Earlier built-in wordings. A saved template that is exactly one of these was never edited by hand, so it
# is upgraded to the current default instead of being kept.
LEGACY_TEMPLATES = {
    "low": [
        ("Your productive hours on {date_short}: {productive} (below {threshold})",
         "Hi {first_name},\n\nProHance recorded {productive} productive hours for you on {date}. The minimum we "
         "expect is {threshold} hours a day.\n\n{stats}\n\nIf something got in the way, such as system or VPN "
         "problems, meetings away from your laptop, or ProHance not tracking correctly, please reply with a short "
         "note so we can record it.\n\nOtherwise, please make sure you reach at least {threshold} productive hours "
         "each day.\n\nThanks,\n{sender_name}"),
        ("Productive hours below {threshold} on {date_short}",
         "Hi {first_name},\n\nProHance recorded {productive} of productive time for you on {date}, below the daily "
         "minimum of {threshold}.\n\n{stats}\n\nIf something got in the way, such as system or VPN problems, "
         "meetings away from your laptop, or ProHance not tracking correctly, please reply with a short note so we "
         "can record it.\n\nOtherwise, please make sure you reach at least {threshold} of productive time each "
         "day.\n\nThanks,\n{sender_name}"),
        ("Productive hours below {threshold} on {date_short}",
         "Hi {first_name},\n\nProHance recorded {productive} of productive time for you on {date}, below the daily "
         "minimum of {threshold}.\n\n{stats}\n\n{apps}\n\nIf something got in the way, such as system or VPN "
         "problems, meetings away from your laptop, or ProHance not tracking correctly, please reply with a short "
         "note so we can record it.\n\nOtherwise, please make sure you reach at least {threshold} of productive "
         "time each day.\n\nThanks,\n{sender_name}"),
        ("Productive time below {threshold_words} on {date_short}",
         "Hi {first_name},\n\nProHance recorded {productive_words} of productive time for you on {date}. The daily "
         "minimum is {threshold_words}.\n\n{stats}\n\n{apps}\n\nIf something affected your tracked time, such as "
         "system or VPN issues or ProHance not recording correctly, please reply with a short note so we can update "
         "the record.\n\nPlease make sure you reach at least {threshold_words} of productive time each working "
         "day.\n\nThanks,\n{sender_name}"),
        ("Productive time below {threshold_words} on {date_short}",
         "Hi {first_name},\n\nProHance recorded {productive_words} of productive time for you on {date}. The daily "
         "minimum is {threshold_words}.\n\n{stats}\n\n{details}\n\n{apps}\n\nIf something affected your tracked "
         "time, such as system or VPN issues or ProHance not recording correctly, please reply with a short note so "
         "we can update the record.\n\nPlease make sure you reach at least {threshold_words} of productive time "
         "each working day.\n\nThanks,\n{sender_name}"),
    ],
    "none": [
        ("No ProHance activity recorded for you on {date_short}",
         "Hi {first_name},\n\nProHance shows no activity for you on {date}. If you were on leave or had trouble "
         "logging in, please reply with a short note so we can record it.\n\nIf you did work that day, please "
         "check that the ProHance agent is running and signed in when you start your day.\n\nThanks,\n{sender_name}"),
        ("No ProHance activity recorded on {date_short}",
         "Hi {first_name},\n\nProHance has no activity recorded for you on {date}.\n\nIf you were on leave or had "
         "trouble signing in to ProHance, please reply with a short note so we can update the record. If you were "
         "working that day, please make sure the ProHance agent is running and signed in at the start of each "
         "day.\n\nThanks,\n{sender_name}"),
    ],
}
# the earlier "Action required" wordings: with the {stats} summary, first with a longer lead-in to the record
for _kind, _t in DEFAULT_TEMPLATES.items():
    _with_stats = _t["body"].replace("a day.\n\nYour ProHance record", "a day.\n\n{stats}\n\nYour ProHance record")
    LEGACY_TEMPLATES[_kind].append((_t["subject"], _with_stats))
    LEGACY_TEMPLATES[_kind].append((_t["subject"], _with_stats.replace(
        "Your ProHance record for the day:",
        "Below is your complete ProHance record for the day, exactly as it appears in the tracker.")))

DEFAULT_CONFIG = {
    "link": "",
    "drive_id": "",
    "item_id": "",
    "threshold_min": 240,
    "cc": [],          # derived: extra recipients on by default in Cc
    "to_also": [],     # derived: extra recipients on by default in To, next to the candidate
    "cc_list": [],     # [{"email": ..., "field": "to" | "cc", "default": true}] managed in Settings
    "sender_name": "",
    "link_off": False,   # this person removed the link (or uses a downloaded copy): don't bring back the team's
    "email_domain": "",  # e.g. "ccsglobaltech.com": other domains in the sheet are flagged as typos
    "directory": [],     # [{"name", "email"}]: these addresses replace the sheet's (matched by name)
    "templates": DEFAULT_TEMPLATES,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path):
    try:
        data = json.loads(Path(path).read_text("utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_atomic(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# Shared starting settings for everyone on the team (tracker link, extra recipients, company domain, email
# directory, threshold). Committed with the code; it holds people's names and addresses, so the repo must be private.
TEAM_FILE = Path(__file__).resolve().parent / "team-defaults.json"
TEAM_KEYS = ("link", "cc_list", "email_domain", "directory", "threshold_min")


def _merge_directory(team, own):
    """Team entries first, then the person's own; the person's own address wins for the same name."""
    def key(e):
        return " ".join(str(e.get("name", "")).lower().split())
    out = {key(e): e for e in team or [] if key(e) and e.get("email")}
    out.update({key(e): e for e in own or [] if key(e) and e.get("email")})
    return sorted(out.values(), key=lambda e: e["name"].lower())


class Store:
    def __init__(self, root, team_file=TEAM_FILE):
        self.team_file = Path(team_file) if team_file else None
        self.root = Path(root)
        (self.root / "cache").mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._ledger = None

    # ---- settings
    def config(self):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        saved = _read_json(self.root / "config.json")  # damaged or missing: defaults apply
        cfg.update({k: v for k, v in saved.items() if k in DEFAULT_CONFIG})
        # team defaults fill what this person hasn't set; their own directory entries win over the team's
        team = self.team()
        for k in ("link", "cc_list", "email_domain", "threshold_min"):
            if k == "link" and saved.get("link_off"):
                continue
            if team.get(k) and (k not in saved or not saved[k]):
                cfg[k] = json.loads(json.dumps(team[k]))
        if team.get("directory"):
            cfg["directory"] = _merge_directory(team["directory"], cfg.get("directory"))
        for kind, tpl in DEFAULT_TEMPLATES.items():
            cfg["templates"].setdefault(kind, dict(tpl))
            saved = cfg["templates"][kind]
            if (saved.get("subject"), saved.get("body")) in LEGACY_TEMPLATES.get(kind, []):
                cfg["templates"][kind] = dict(tpl)
        if not cfg["cc_list"] and cfg["cc"]:  # older settings had a plain "Always Cc" list
            cfg["cc_list"] = [{"email": e, "default": True} for e in cfg["cc"]]
        for c in cfg["cc_list"]:
            c["field"] = "to" if c.get("field") == "to" else "cc"
        cfg["cc"] = [c["email"] for c in cfg["cc_list"] if c.get("default") and c["field"] == "cc"]
        cfg["to_also"] = [c["email"] for c in cfg["cc_list"] if c.get("default") and c["field"] == "to"]
        return cfg

    def save_config(self, cfg):
        with self.lock:
            _write_atomic(self.root / "config.json", json.dumps(cfg, indent=2).encode())

    def team(self):
        """team-defaults.json, limited to the shareable keys; {} when there is none or it can't be read."""
        t = _read_json(self.team_file) if self.team_file else {}
        return {k: t[k] for k in TEAM_KEYS if k in t}

    def save_team(self, cfg):
        """Write this person's shareable settings as the team defaults file."""
        data = {"_note": "Nudge team defaults: tracker link, extra recipients, company domain, email directory, "
                         "threshold. Holds names and email addresses: keep this repo private.",
                **{k: cfg[k] for k in TEAM_KEYS}}
        _write_atomic(self.team_file, json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
        return self.team_file

    # ---- ledger: drafted / sent / skipped / discarded / cleared. Append-only; the last line per key wins.
    def _load_ledger(self):
        if self._ledger is None:
            self._ledger = []
            p = self.root / "ledger.jsonl"
            if p.exists():
                for line in p.read_text("utf-8").splitlines():
                    if line.strip():
                        try:
                            self._ledger.append(json.loads(line))
                        except ValueError:
                            pass  # a half-written last line after a crash: skip it, keep the rest
        return self._ledger

    def ledger(self):
        with self.lock:
            return list(self._load_ledger())

    def latest(self, key):
        with self.lock:
            for e in reversed(self._load_ledger()):
                if e.get("key") == key:
                    return e
        return None

    def append(self, entry):
        entry = {"at": now_iso(), **entry}
        with self.lock:
            self._load_ledger().append(entry)
            with open(self.root / "ledger.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return entry

    # ---- per-person edits to the email text
    def edits(self):
        p = self.root / "edits.json"
        try:
            return json.loads(p.read_text("utf-8")) if p.exists() else {}
        except ValueError:
            return {}

    def save_edit(self, key, edit):
        with self.lock:
            d = self.edits()
            if edit:
                d[key] = edit
            else:
                d.pop(key, None)
            _write_atomic(self.root / "edits.json", json.dumps(d, indent=1, ensure_ascii=False).encode())

    # ---- cached workbook
    def cached_meta(self):
        p = self.root / "cache" / "meta.json"
        if not (p.exists() and (self.root / "cache" / "workbook.xlsx").exists()):
            return None
        try:
            return json.loads(p.read_text("utf-8"))
        except ValueError:
            return None

    def cached_file(self):
        meta = self.cached_meta()
        if not meta:
            return None, None
        return meta, (self.root / "cache" / "workbook.xlsx").read_bytes()

    def save_file(self, meta, data):
        with self.lock:
            _write_atomic(self.root / "cache" / "workbook.xlsx", data)
            _write_atomic(self.root / "cache" / "meta.json", json.dumps(meta, indent=1).encode())

    def clear_file(self):
        for name in ("workbook.xlsx", "meta.json"):
            (self.root / "cache" / name).unlink(missing_ok=True)

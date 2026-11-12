"""Everything kept on disk under the data folder: settings, the ledger, draft edits, the cached workbook.
No secrets are stored: the access token lives in memory only."""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_TEMPLATES = {
    "low": {
        "subject": "Productive time below {threshold_words} on {date_short}",
        "body": (
            "Hi {first_name},\n\n"
            "ProHance recorded {productive_words} of productive time for you on {date}. "
            "The daily minimum is {threshold_words}.\n\n"
            "{stats}\n\n"
            "{apps}\n\n"
            "If something affected your tracked time, such as system or VPN issues or ProHance not recording "
            "correctly, please reply with a short note so we can update the record.\n\n"
            "Please make sure you reach at least {threshold_words} of productive time each working day.\n\n"
            "Thanks,\n{sender_name}"
        ),
    },
    "none": {
        "subject": "No ProHance activity recorded on {date_short}",
        "body": (
            "Hi {first_name},\n\n"
            "ProHance has no activity recorded for you on {date}.\n\n"
            "If you were on leave or had trouble signing in to ProHance, please reply with a short note so we "
            "can update the record. If you were working that day, please make sure the ProHance agent is running "
            "and signed in at the start of each day.\n\n"
            "Thanks,\n{sender_name}"
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
    ],
    "none": [
        ("No ProHance activity recorded for you on {date_short}",
         "Hi {first_name},\n\nProHance shows no activity for you on {date}. If you were on leave or had trouble "
         "logging in, please reply with a short note so we can record it.\n\nIf you did work that day, please "
         "check that the ProHance agent is running and signed in when you start your day.\n\nThanks,\n{sender_name}"),
    ],
}

DEFAULT_CONFIG = {
    "link": "",
    "drive_id": "",
    "item_id": "",
    "threshold_min": 240,
    "cc": [],          # derived: extra recipients on by default in Cc
    "to_also": [],     # derived: extra recipients on by default in To, next to the candidate
    "cc_list": [],     # [{"email": ..., "field": "to" | "cc", "default": true}] managed in Settings
    "sender_name": "",
    "templates": DEFAULT_TEMPLATES,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_atomic(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "cache").mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._ledger = None

    # ---- settings
    def config(self):
        p = self.root / "config.json"
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        if p.exists():
            try:
                saved = json.loads(p.read_text("utf-8"))
            except ValueError:
                saved = {}  # a damaged settings file must not stop the app; defaults apply
            cfg.update({k: v for k, v in saved.items() if k in DEFAULT_CONFIG})
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

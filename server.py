"""Nudge: draft emails in your Outlook for interns whose ProHance productive hours fell short.
Local web app, Python standard library only.

    python server.py --open          http://localhost:8770
    python server.py --demo --open   made-up data; nothing touches Outlook (data in data-demo/)

Drafts go into classic Outlook on this PC (outlook.py). Nudge never sends email: you review and send the
drafts in Outlook, and "Sync with Outlook" records what was sent. Reading the tracker from SharePoint uses
a pasted Microsoft Graph access token (memory only); a downloaded copy works without one.
"""
import argparse
import base64
import binascii
import hashlib
import json
import logging
import logging.handlers
import random
import re
import threading
import time
import traceback
import urllib.parse
import webbrowser
import zipfile
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET

import demo
import outlook
import tracker
import xlsx
from msgraph import Graph, GraphError, describe_token
from outlook import OutlookError
from store import Store, now_iso

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
UNFILLED = re.compile(r"\{([a-z_]{2,30})\}")  # a template field that wasn't replaced
log = logging.getLogger("app")


class ApiError(Exception):
    def __init__(self, message, status=400, code="bad_request"):
        super().__init__(message)
        self.status, self.code = status, code


def _emails(v):
    items = v if isinstance(v, list) else str(v or "").replace(";", ",").split(",")
    out = [s.strip() for s in items if s and s.strip()]
    bad = [s for s in out if not tracker.EMAIL_RE.match(s)]
    if bad:
        raise ApiError(f"Not a valid email address: {', '.join(bad)}")
    return out


class App:
    def __init__(self, store, demo_mode=False, port=8770):
        self.store = store
        self.demo = demo_mode
        self.port = port
        self.lock = threading.Lock()
        self.inflight = set()
        self._parsed = None
        self.token = None  # {"token", "user", "name", "expires_at", "can_read", ...}; memory only
        if demo_mode:
            self.token = {"token": "demo", "user": "you@example-tech.com", "name": "Demo User", "app": "Demo",
                          "expires_at": int(time.time()) + 86400, "can_read": True, "scopes": []}

    # ------------------------------------------------------------- token (only for reading SharePoint)
    def _token(self, need=None):
        t = self.token
        if t and t["expires_at"] <= time.time() + 30:
            self.token = t = None
        if not t:
            raise ApiError("Paste a Microsoft access token to read the tracker from SharePoint "
                           "(Graph Explorer → Access token), or open a downloaded copy.", 401, "token_needed")
        if need == "read" and not t["can_read"]:
            raise ApiError("This token can't read files. In Graph Explorer, consent to Files.Read.All.", 403, "token_scope")
        return t

    def graph(self, need=None):
        return Graph(self._token(need)["token"])

    def token_public(self):
        t = self.token
        if t and t["expires_at"] <= time.time() + 30:
            self.token = t = None
        return {k: v for k, v in t.items() if k != "token"} if t else None

    # ------------------------------------------------------------- workbook
    def workbook(self):
        meta = self.store.cached_meta()
        if not meta:
            return None
        cfg = self.store.config()
        key = (meta.get("ctag"), meta.get("fetched_from"), date.today(),
               json.dumps([cfg["directory"], cfg["email_domain"]], sort_keys=True))
        if self._parsed and self._parsed[0] == key:
            return {**self._parsed[1], "file": meta}
        meta, data = self.store.cached_file()
        t0 = time.perf_counter()
        try:
            result = tracker.parse_workbook(xlsx.read_workbook(data), directory=cfg["directory"],
                                            domain=cfg["email_domain"])
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
            raise ApiError(f"The saved copy of the workbook can't be read ({type(e).__name__}). Load it again.") from None
        log.info("parsed workbook", extra={"days": len(result["days"]), "ms": round((time.perf_counter() - t0) * 1000)})
        self._parsed = (key, result)
        return {**result, "file": meta}

    def _resolve(self, cfg):
        """Turn the saved sharing link into drive and item ids (needs the token once per link)."""
        item = self.graph("read").resolve_link(cfg["link"])
        name = item.get("name", "")
        if not name.lower().endswith((".xlsx", ".xlsm")):
            raise ApiError(f"That link points to {name or 'something'}, not an Excel workbook")
        cfg.update(drive_id=item["parentReference"]["driveId"], item_id=item["id"])
        self.store.save_config(cfg)
        return cfg

    def _fetch(self, force=False):
        cfg = self.store.config()
        meta = self.store.cached_meta()
        if self.demo:
            if meta and not force:
                return False
            data = demo.workbook_bytes()
            self.store.save_file({"name": "Demo Interns Daily Tracker.xlsx", "ctag": str(time.time()),
                                  "modified": now_iso(), "modified_by": "Demo data", "web_url": "",
                                  "fetched_at": now_iso(), "fetched_from": "demo", "size": len(data)}, data)
            self._parsed = None
            return True
        if not cfg.get("link"):
            if meta:
                return False  # a downloaded copy, nothing to check
            raise ApiError("Add the tracker's SharePoint link first", code="no_link")
        if not cfg.get("item_id"):
            cfg = self._resolve(cfg)
        graph = self.graph("read")
        item = graph.item(cfg["drive_id"], cfg["item_id"])
        tag = item.get("cTag") or item.get("eTag")
        new_meta = {
            "name": item.get("name"), "ctag": tag, "modified": item.get("lastModifiedDateTime"),
            "modified_by": ((item.get("lastModifiedBy") or {}).get("user") or {}).get("displayName", ""),
            "web_url": item.get("webUrl", ""), "fetched_at": now_iso(), "fetched_from": cfg["item_id"],
            "size": item.get("size"),
        }
        if not force and meta and meta.get("ctag") == tag and meta.get("fetched_from") == cfg["item_id"]:
            _, data = self.store.cached_file()
            self.store.save_file(new_meta, data)
            return False
        t0 = time.perf_counter()
        data = graph.download(cfg["drive_id"], cfg["item_id"])
        try:
            xlsx.read_workbook(data)  # never replace a good cached copy with an unreadable download
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            raise ApiError("SharePoint returned a file that isn't a readable workbook. Try again in a minute.") from None
        log.info("downloaded workbook", extra={"bytes": len(data), "ms": round((time.perf_counter() - t0) * 1000)})
        self.store.save_file(new_meta, data)
        self._parsed = None
        return True

    # ------------------------------------------------------------- api
    def public_state(self):
        cfg = self.store.config()
        meta = self.store.cached_meta()
        return {
            "demo": self.demo,
            "outlook": {"installed": True, "new_outlook_on": False} if self.demo else outlook.status(),
            "token": self.token_public(),
            "settings": {k: cfg.get(k) for k in ("link", "threshold_min", "cc", "to_also", "cc_list", "templates",
                                                 "sender_name", "email_domain", "directory")},
            "source": "demo" if self.demo else ("sharepoint" if meta and meta.get("fetched_from") not in (None, "local")
                                                  else ("local" if meta else None)),
        }

    def api_state(self, _):
        out = self.public_state()
        out["workbook"] = self.workbook()
        out["ledger"] = self.store.ledger()
        out["edits"] = self.store.edits()
        return out

    def api_token(self, p):
        info = describe_token(p.get("token"))
        if not self.demo:
            me = Graph(info["token"]).me()  # proves the token works right now
            info["name"] = me.get("displayName") or info["name"]
            info["user"] = me.get("mail") or me.get("userPrincipalName") or info["user"]
        self.token = info
        log.info("token set", extra={"expires_in_min": round((info["expires_at"] - time.time()) / 60),
                                     "can_read": info["can_read"]})
        return {"token": self.token_public()}

    def api_token_clear(self, _):
        if not self.demo:
            self.token = None
        return {"token": self.token_public()}

    def api_refresh(self, p):
        changed = self._fetch(force=bool(p.get("force")))
        return {"changed": changed, "workbook": self.workbook(), "source": self.public_state()["source"]}

    def api_settings(self, p):
        cfg = self.store.config()
        if "threshold_min" in p:
            t = int(p["threshold_min"])
            if not 1 <= t <= 24 * 60:
                raise ApiError("Threshold must be between 0:01 and 24:00")
            cfg["threshold_min"] = t
        if "cc_list" in p:
            seen, cc_list = set(), []
            for c in p["cc_list"] or []:
                addr = _emails([str(c.get("email", ""))])
                if addr and addr[0].lower() not in seen:
                    seen.add(addr[0].lower())
                    cc_list.append({"email": addr[0], "field": "to" if c.get("field") == "to" else "cc",
                                    "default": bool(c.get("default", True))})
            cfg["cc_list"] = cc_list
        if "sender_name" in p:
            cfg["sender_name"] = str(p["sender_name"]).strip()[:120]
        emails_changed = False
        if "email_domain" in p:
            dom = str(p["email_domain"] or "").strip().lstrip("@").lower()
            if dom and not tracker.EMAIL_RE.match("x@" + dom):
                raise ApiError(f"“{dom}” isn't a domain; it should look like company.com")
            emails_changed |= dom != cfg["email_domain"]
            cfg["email_domain"] = dom
        if "directory_text" in p:
            entries, problems = tracker.parse_directory(p["directory_text"], cfg["email_domain"])
            if problems:
                raise ApiError("Email directory: " + "; ".join(problems[:3])
                               + (f" (and {len(problems) - 3} more)" if len(problems) > 3 else ""))
            emails_changed |= entries != cfg["directory"]
            cfg["directory"] = entries
        if "templates" in p:
            for kind, tpl in p["templates"].items():
                if kind in cfg["templates"] and tpl.get("subject", "").strip() and tpl.get("body", "").strip():
                    cfg["templates"][kind] = {"subject": tpl["subject"], "body": tpl["body"]}
        load = False
        if "link" in p and str(p["link"]).strip() != cfg.get("link"):
            link = str(p["link"]).strip()
            if link and not link.startswith("https://"):
                raise ApiError("Paste the full https:// SharePoint link (Share → Copy link)")
            cfg.update(link=link, drive_id="", item_id="")
            if (self.store.cached_meta() or {}).get("fetched_from") not in (None, "local"):
                self.store.clear_file()  # the old SharePoint file's copy no longer applies
                self._parsed = None
            load = bool(link) and not self.demo
        self.store.save_config(cfg)
        out = self.public_state()
        if load and self.token:
            self._fetch(force=True)
            out = self.public_state()
            out["workbook"] = self.workbook()
        elif emails_changed:
            out["workbook"] = self.workbook()  # addresses changed: the page needs the re-checked list
        return out

    def api_upload(self, p):
        """A downloaded copy of the tracker, sent from the browser as base64. Works without a token."""
        name = str(p.get("name") or "workbook.xlsx")
        if not name.lower().endswith((".xlsx", ".xlsm")):
            raise ApiError("Choose an Excel workbook (.xlsx). An old .xls file has to be saved as .xlsx first.")
        try:
            data = base64.b64decode(p.get("data") or "", validate=True)
        except (binascii.Error, ValueError):
            raise ApiError("Couldn't read that file") from None
        if len(data) > 30_000_000:
            raise ApiError("That file is over 30 MB; is it the right workbook?")
        try:
            sheets = xlsx.read_workbook(data)
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            raise ApiError("That isn't a readable .xlsx workbook. In Excel use File > Save As > Excel Workbook.") from None
        parsed = tracker.parse_workbook(sheets)
        if not parsed["days"]:
            raise ApiError(f"No day tabs (like “10 Nov”) in {name}. Tabs found: {', '.join(parsed['other_tabs'][:8])}")
        self.store.save_file({"name": name, "ctag": hashlib.sha1(data).hexdigest(),
                              "modified": p.get("modified") or now_iso(), "modified_by": "", "web_url": "",
                              "fetched_at": now_iso(), "fetched_from": "local", "size": len(data)}, data)
        cfg = self.store.config()
        cfg.update(link="", drive_id="", item_id="")  # the downloaded copy replaces the SharePoint source
        self.store.save_config(cfg)
        self._parsed = None
        log.info("opened local copy", extra={"bytes": len(data), "days": len(parsed["days"])})
        out = self.public_state()
        out["workbook"] = self.workbook()
        return out

    def api_drafts_create(self, p):
        """Write each person's email as an .eml file and open them in classic Outlook. A person who already has
        an email open or was sent for that day is skipped unless `again` is set."""
        items, again = p.get("items") or [], bool(p.get("again"))
        if not items:
            raise ApiError("No one selected")
        if not self.demo and p.get("open", True):
            outlook.require_open()  # before writing anything: nothing is recorded if Outlook isn't ready
        todo, duplicates, failed = [], [], []
        for it in items:
            key = it.get("key") or ""
            try:
                to, cc = _emails(it.get("to")), _emails(it.get("cc") or [])
            except ApiError as e:
                failed.append({"key": key, "message": str(e)})
                continue
            subject, html = str(it.get("subject") or "").strip(), str(it.get("html") or "")
            if not key or not to or not subject or not html:
                failed.append({"key": key, "message": "Missing address, subject or text"})
                continue
            unfilled = sorted(set(UNFILLED.findall(subject + " " + html)))
            if unfilled:
                failed.append({"key": key, "message": "The email still has an unfilled field: "
                                                      + ", ".join("{" + u + "}" for u in unfilled)})
                continue
            prev = self.store.latest(key)
            if prev and prev.get("status") in ("drafted", "sent") and not again:
                duplicates.append(prev)
                continue
            todo.append({**it, "to": to, "cc": cc, "subject": subject, "html": html})
        with self.lock:
            busy = [t for t in todo if t["key"] in self.inflight]
            if busy:
                raise ApiError("Drafts for some of these people are already being created", 409, "in_flight")
            self.inflight.update(t["key"] for t in todo)
        try:
            entries, paths = [], []
            for t in todo:
                try:
                    if self.demo:
                        path = f"demo-{hashlib.sha1((t['key'] + now_iso()).encode()).hexdigest()[:12]}.eml"
                    else:
                        path = outlook.write_eml(self.store.root / "outbox" / (t.get("date") or "undated"),
                                                 t.get("name") or t["to"][0], t["to"], t["cc"], t["subject"], t["html"])
                except OSError as e:
                    failed.append({"key": t["key"], "message": f"Couldn't write the email file: {e}"})
                    continue
                paths.append(path)
                entries.append(self.store.append({
                    "key": t["key"], "status": "drafted", "message_id": path, "date": t.get("date"),
                    "sheet": t.get("sheet"), "name": t.get("name"), "to": t["to"], "cc": t["cc"],
                    "subject": t["subject"], "html": t["html"], "productive": t.get("productive"),
                    "kind": t.get("kind"), **({"demo": True} if self.demo else {}),
                }))
            if paths and not self.demo and p.get("open", True):
                threading.Thread(target=_open_quietly, args=(paths,), daemon=True).start()
            log.info("emails opened in Outlook", extra={"made": len(entries), "failed": len(failed), "skipped": len(duplicates)})
            return {"entries": entries, "duplicates": duplicates, "failed": failed}
        finally:
            with self.lock:
                self.inflight.difference_update(t["key"] for t in todo)

    def api_open_draft(self, p):
        """Open a person's email in Outlook again (e.g. you closed it without sending)."""
        e = self.store.latest(p.get("key") or "")
        if not e or e.get("status") != "drafted":
            raise ApiError("There's no open email for this person")
        if self.demo:
            return {"ok": True}
        outlook.require_open()
        if e.get("html") and e.get("to") and e.get("subject"):
            # rebuild the file from the saved email, so an email first written with an older (broken) encoding
            # opens correctly too
            path = outlook.write_eml(self.store.root / "outbox" / (e.get("date") or "undated"),
                                     e.get("name") or e["to"][0], e["to"], e.get("cc") or [], e["subject"], e["html"])
        else:
            path = e["message_id"]
        outlook.open_eml(path)
        return {"ok": True}

    def api_mark(self, p):
        """skipped / cleared (back to to-do) / sent (you sent it from Outlook)."""
        status = p.get("status")
        if status not in ("skipped", "cleared", "sent"):
            raise ApiError("status must be skipped, cleared or sent")
        out = []
        for it in p.get("items", []):
            prev = self.store.latest(it.get("key"))
            if prev and prev.get("status") == "sent":
                continue  # an email that went out stays recorded
            if status == "sent":
                if not prev or prev.get("status") != "drafted":
                    continue  # only an email Nudge opened in Outlook can be marked sent
                out.append(self.store.append({**_carry(prev), "status": "sent", "sent_at": now_iso()}))
                continue
            out.append(self.store.append({"key": it["key"], "status": status, "date": it.get("date"),
                                          "sheet": it.get("sheet"), "name": it.get("name"),
                                          "to": [it["email"]] if it.get("email") else [],
                                          "productive": it.get("productive")}))
        return {"entries": out}

    def api_edit(self, p):
        self.store.save_edit(p["key"], p.get("edit"))
        return {"ok": True}


def _open_quietly(paths):
    try:
        outlook.open_many(paths)
    except Exception as e:  # noqa: BLE001 - the files exist; the person can open them again from Nudge
        log.warning("couldn't open emails in Outlook", extra={"error": str(e)})


def _carry(e):
    keep = ("key", "message_id", "date", "sheet", "name", "to", "cc", "subject", "html", "productive", "kind", "demo")
    return {k: e[k] for k in keep if k in e}


# Fixed types, not mimetypes: on Windows it reads the registry, which on many PCs says .js is text/plain,
# and the browser then refuses to run the app's module script (the page stays on "Loading" forever).
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


def content_type(name):
    return TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


class Handler(BaseHTTPRequestHandler):
    server_version = "Nudge/2.0"
    nudge = None  # the App

    def log_message(self, fmt, *args):
        pass

    def _host_ok(self):
        port = self.nudge.port
        return self.headers.get("Host", "") in (f"localhost:{port}", f"127.0.0.1:{port}")

    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, '{"error":"bad host"}')
        path = urllib.parse.urlparse(self.path).path
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        f = (PUBLIC / rel).resolve()
        if PUBLIC.resolve() not in f.parents or not f.is_file():
            return self._send(404, '{"error":"not found"}')
        self._send(200, f.read_bytes(), content_type(f.name))

    def do_POST(self):
        port = self.nudge.port
        origin = self.headers.get("Origin")
        if not self._host_ok() or (origin and origin not in (f"http://localhost:{port}", f"http://127.0.0.1:{port}")):
            return self._send(403, '{"error":"bad origin"}')
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._send(415, '{"error":"JSON only"}')
        path = urllib.parse.urlparse(self.path).path
        name = path[len("/api/"):].strip("/") if path.startswith("/api/") else ""
        fn = getattr(self.nudge, "api_" + name, None) if name.replace("_", "").isalnum() else None
        if not fn:
            return self._send(404, '{"error":"no such endpoint"}')
        t0 = time.perf_counter()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            out, status = fn(body), 200
        except ApiError as e:
            out, status = {"error": str(e), "code": e.code}, e.status
        except GraphError as e:
            if e.code == "token_expired":
                self.nudge.token = None
            status = e.status if 400 <= e.status < 600 else 502
            out = {"error": e.message, "code": e.code}
        except OutlookError as e:
            out, status = {"error": e.message, "code": "outlook_" + e.code}, 503
        except Exception as e:  # noqa: BLE001
            log.error("unhandled", extra={"path": path, "trace": traceback.format_exc()})
            out, status = {"error": f"{type(e).__name__}: {e}", "code": "internal"}, 500
        log.info("api", extra={"path": path, "status": status, "ms": round((time.perf_counter() - t0) * 1000)})
        self._send(status, json.dumps(out, ensure_ascii=False))


class JsonFormatter(logging.Formatter):
    SKIP = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

    def format(self, r):
        out = {"ts": self.formatTime(r, "%Y-%m-%dT%H:%M:%S"), "level": r.levelname, "logger": r.name,
               "event": r.getMessage()}
        out.update({k: v for k, v in vars(r).items() if k not in self.SKIP})
        return json.dumps(out, default=str)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--demo", action="store_true", help="made-up data; nothing touches Outlook")
    ap.add_argument("--open", action="store_true", help="open the browser")
    ap.add_argument("--data", help="data folder (default data/, or data-demo/ with --demo)")
    a = ap.parse_args()

    data_dir = Path(a.data) if a.data else ROOT / ("data-demo" if a.demo else "data")
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(data_dir / "logs" / "app.jsonl", maxBytes=1_000_000, backupCount=3,
                                             encoding="utf-8")
    h.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[h])

    Handler.nudge = App(Store(data_dir), a.demo, a.port)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError:
        print(f"Port {a.port} is busy: Nudge is probably already running at http://localhost:{a.port}")
        if a.open:
            webbrowser.open(f"http://localhost:{a.port}")
        return
    srv.daemon_threads = True
    url = f"http://localhost:{a.port}"
    print(f"Nudge{' (demo)' if a.demo else ''} on {url}  - Ctrl+C to stop")
    if a.open:
        threading.Timer(0.4, webbrowser.open, [url]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

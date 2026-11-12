"""Microsoft Graph with a pasted access token (e.g. from Graph Explorer), used only to read the tracker
from SharePoint. Email goes through classic Outlook on this PC (outlook.py), not Graph.

The token is held in memory only. It is never written to disk or to the log.
"""
import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.microsoft.com/v1.0"
UA = "prohance-nudge/2.0"
GRAPH_AUDIENCES = {"00000003-0000-0000-c000-000000000000", "https://graph.microsoft.com"}
READ_SCOPES = {"Files.Read", "Files.Read.All", "Files.ReadWrite", "Files.ReadWrite.All",
               "Sites.Read.All", "Sites.ReadWrite.All"}

log = logging.getLogger("graph")


class GraphError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_plain = urllib.request.build_opener()
_noredirect = urllib.request.build_opener(_NoRedirect)


def _http(method, url, *, headers=None, body=None, timeout=60, follow=True):
    req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": UA, **(headers or {})})
    try:
        with (_plain if follow else _noredirect).open(req, timeout=timeout) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except urllib.error.URLError as e:
        raise GraphError(0, "network", f"Network error: {e.reason}") from None
    except TimeoutError:
        raise GraphError(0, "timeout", "Microsoft didn't answer in time. Try again.") from None


def _err(status, body):
    try:
        j = json.loads(body or b"{}")
    except ValueError:
        return GraphError(status, "http", f"HTTP {status}")
    e = j.get("error") if isinstance(j.get("error"), dict) else {}
    return GraphError(status, e.get("code", "error"), e.get("message") or f"HTTP {status}")


def share_id(url):
    """Graph's encoding of a sharing link for /shares/{id}."""
    return "u!" + base64.urlsafe_b64encode(url.strip().encode()).decode().rstrip("=")


def token_claims(token):
    """Decode (not verify) the token's claims, to show who it's for and what it allows."""
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception:  # noqa: BLE001
        raise GraphError(400, "bad_token", "That doesn't look like an access token. Copy it again from "
                                           "Graph Explorer's Access token tab.") from None


def describe_token(token):
    """-> dict for the UI: who, expiry, which features it allows. Raises GraphError when unusable."""
    token = (token or "").strip().removeprefix("Bearer ").strip()
    c = token_claims(token)
    if c.get("aud") not in GRAPH_AUDIENCES:
        raise GraphError(400, "bad_audience", "That token isn't for Microsoft Graph.")
    exp = int(c.get("exp", 0))
    if exp <= time.time() + 60:
        raise GraphError(400, "expired", "That token has expired. Get a fresh one from Graph Explorer.")
    scopes = set((c.get("scp") or "").split())
    return {
        "token": token,
        "user": c.get("upn") or c.get("unique_name") or c.get("preferred_username") or "",
        "name": c.get("name") or "",
        "app": c.get("app_displayname") or "",
        "expires_at": exp,
        "can_read": bool(scopes & READ_SCOPES),
        "scopes": sorted(scopes),
    }


class Graph:
    def __init__(self, token):
        self.token = token

    def call(self, method, path, *, json_body=None, headers=None):
        url = path if path.startswith("https://") else GRAPH + path
        body = json.dumps(json_body).encode() if json_body is not None else None
        hdrs = {"Authorization": "Bearer " + self.token, **({"Content-Type": "application/json"} if body else {}),
                **(headers or {})}
        for attempt in range(4):
            t0 = time.perf_counter()
            status, rh, data = _http(method, url, headers=hdrs, body=body)
            log.info("graph", extra={"method": method, "path": urllib.parse.urlsplit(url).path[:100], "status": status,
                                     "ms": round((time.perf_counter() - t0) * 1000)})
            if status in (429, 503, 504) and attempt < 3:
                time.sleep(min(float(rh.get("Retry-After") or 2 ** attempt), 10))
                continue
            break
        if status == 401:
            raise GraphError(401, "token_expired", "Microsoft rejected the token (it may have expired). "
                                                   "Paste a fresh one from Graph Explorer.")
        if status >= 400:
            raise _err(status, data)
        return json.loads(data) if data else {}

    def me(self):
        return self.call("GET", "/me?$select=displayName,mail,userPrincipalName")

    # ---- the workbook
    def resolve_link(self, link):
        """Sharing link -> driveItem (id, parentReference.driveId, name, ...)."""
        return self.call("GET", f"/shares/{share_id(link)}/driveItem?$select=id,name,parentReference,webUrl",
                         headers={"Prefer": "redeemSharingLinkIfNecessary"})

    def item(self, drive_id, item_id):
        return self.call("GET", f"/drives/{drive_id}/items/{item_id}"
                                "?$select=id,name,cTag,eTag,size,lastModifiedDateTime,lastModifiedBy,webUrl")

    def download(self, drive_id, item_id):
        """File bytes. Graph answers with a redirect to a pre-authenticated URL; the token isn't sent there."""
        status, rh, data = _http("GET", f"{GRAPH}/drives/{drive_id}/items/{item_id}/content",
                                 headers={"Authorization": "Bearer " + self.token}, timeout=120, follow=False)
        if status in (301, 302, 303, 307, 308) and rh.get("Location"):
            status, _, data = _http("GET", rh["Location"], timeout=120)
        if status == 401:
            raise GraphError(401, "token_expired", "Microsoft rejected the token. Paste a fresh one.")
        if status != 200:
            raise _err(status, data) if status >= 400 else GraphError(status, "download", f"Download failed ({status})")
        return data

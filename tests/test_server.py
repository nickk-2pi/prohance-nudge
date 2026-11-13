import base64
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import msgraph  # noqa: E402
import server  # noqa: E402
from store import Store  # noqa: E402


def fake_token(**claims):
    def part(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    body = {"aud": sorted(msgraph.GRAPH_AUDIENCES)[0], "exp": int(time.time()) + 3600, "upn": "sam@example.com",
            "name": "Sam Lee", "scp": "Files.Read.All User.Read", **claims}
    return f"{part({'alg': 'none'})}.{part(body)}.sig"


class Token(unittest.TestCase):
    def test_pasting_a_token_works(self):
        app = server.App(Store(tempfile.mkdtemp(), team_file=None), demo_mode=True)  # demo: no call to Microsoft
        out = app.api_token({"token": fake_token()})["token"]
        self.assertTrue(out["can_read"])
        self.assertEqual(out["user"], "sam@example.com")
        self.assertNotIn("token", out)  # the token itself never goes back to the page

    def test_token_without_file_access_is_accepted_but_flagged(self):
        app = server.App(Store(tempfile.mkdtemp(), team_file=None), demo_mode=True)
        self.assertFalse(app.api_token({"token": fake_token(scp="User.Read")})["token"]["can_read"])


class EmailSettings(unittest.TestCase):
    def setUp(self):
        self.app = server.App(Store(tempfile.mkdtemp(), team_file=None), demo_mode=True)

    def test_directory_usernames_get_the_domain(self):
        s = self.app.api_settings({"email_domain": "@Example-Tech.com", "directory_text": "Sam Lee\tslee"})["settings"]
        self.assertEqual(s["email_domain"], "example-tech.com")
        self.assertEqual(s["directory"], [{"name": "Sam Lee", "email": "slee@example-tech.com"}])

    def test_a_bad_line_is_refused_and_nothing_is_saved(self):
        self.app.api_settings({"email_domain": "example-tech.com", "directory_text": "Sam Lee slee"})
        with self.assertRaises(server.ApiError) as e:
            self.app.api_settings({"directory_text": "Sam Lee slee\nJust-a-name"})
        self.assertIn("Line 2", str(e.exception))
        self.assertEqual(len(self.app.store.config()["directory"]), 1)

    def test_a_bad_domain_is_refused(self):
        with self.assertRaises(server.ApiError):
            self.app.api_settings({"email_domain": "not a domain"})


class ContentTypes(unittest.TestCase):
    def test_scripts_are_javascript_whatever_the_registry_says(self):
        self.assertEqual(server.content_type("app.js"), "text/javascript; charset=utf-8")
        self.assertEqual(server.content_type("APP.JS"), "text/javascript; charset=utf-8")

    def test_every_served_file_has_a_known_type(self):
        for f in (ROOT / "public").rglob("*"):
            if f.is_file():
                self.assertNotEqual(server.content_type(f.name), "application/octet-stream", f.name)


if __name__ == "__main__":
    unittest.main()

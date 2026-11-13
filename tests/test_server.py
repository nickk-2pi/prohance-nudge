import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


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

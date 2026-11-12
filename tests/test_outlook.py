import email
import sys
import tempfile
import unittest
from email import policy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import outlook  # noqa: E402

# Long lines with punctuation, digits and non-ASCII: exactly what quoted-printable wrapping used to break.
HTML = ("<div style=\"font-family:'Segoe UI',Arial,sans-serif;font-size:14px;line-height:1.55;color:#1f2328\">"
        "<p style=\"margin:0 0 12px\">Hi Alex,</p>"
        "<p style=\"margin:0 0 12px\">ProHance shows no activity for you on Monday, November 2, 2026. If you were on "
        "leave or had trouble logging in, please reply with a short note so we can record it.</p>"
        "<p style=\"margin:0 0 12px\">If you did work that day, please check that the ProHance agent is running and "
        "signed in when you start your day. Tomás, Zoë &amp; 100% = fine.</p>"
        "<p style=\"margin:0 0 12px\">Thanks,<br>Sam Lee</p></div>")


class Eml(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = outlook.write_eml(self.dir, "Alex Rivera", ["ARivera@example-tech.com"],
                                      ["lead@example-tech.com", "hr@example-tech.com"],
                                      "No ProHance activity recorded for you on Mon, Nov 2", HTML)
        self.raw = Path(self.path).read_bytes()
        self.msg = email.message_from_bytes(self.raw, policy=policy.default)

    def test_headers(self):
        self.assertEqual(self.msg["To"], "ARivera@example-tech.com")
        self.assertEqual(self.msg["Cc"], "lead@example-tech.com, hr@example-tech.com")
        self.assertEqual(self.msg["Subject"], "No ProHance activity recorded for you on Mon, Nov 2")
        self.assertEqual(self.msg["X-Unsent"], "1")

    def test_body_round_trips_exactly(self):
        html = self.msg.get_body(preferencelist=("html",)).get_content()
        self.assertEqual(html.strip(), HTML)
        text = self.msg.get_body(preferencelist=("plain",)).get_content()
        self.assertIn("Monday, November 2, 2026", text)
        self.assertIn("a short note", text)
        self.assertIn("Tomás, Zoë & 100% = fine.", text)

    def test_no_quoted_printable_and_crlf_only(self):
        self.assertNotIn(b"quoted-printable", self.raw.lower())
        for part in self.msg.walk():
            if not part.is_multipart():
                self.assertEqual(part["Content-Transfer-Encoding"], "base64")
        self.assertNotIn(b"\n", self.raw.replace(b"\r\n", b""))  # every line ends in CRLF

    def test_same_name_twice_gets_its_own_file(self):
        second = outlook.write_eml(self.dir, "Alex Rivera", ["a@b.com"], [], "s", "<p>x</p>")
        self.assertNotEqual(second, self.path)
        self.assertTrue(Path(second).exists())


if __name__ == "__main__":
    unittest.main()

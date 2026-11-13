import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import store  # noqa: E402
from store import Store  # noqa: E402

TEAM = {
    "cc_list": [{"email": "lead@example-tech.com", "field": "to", "default": True},
                {"email": "hr@example-tech.com", "field": "cc", "default": True}],
    "email_domain": "example-tech.com",
    "directory": [{"name": "Ann Lee", "email": "alee@example-tech.com"},
                  {"name": "Bo Chen", "email": "bchen@example-tech.com"}],
    "threshold_min": 270,
}


def make(team=TEAM, own=None):
    root = Path(tempfile.mkdtemp())
    team_file = root / "team-defaults.json"
    if team is not None:
        team_file.write_text(json.dumps(team), "utf-8")
    if own is not None:
        (root / "data").mkdir()
        (root / "data" / "config.json").write_text(json.dumps(own), "utf-8")
    return Store(root / "data", team_file=team_file)


class TeamDefaults(unittest.TestCase):
    def test_a_new_install_starts_from_the_team_file(self):
        cfg = make().config()
        self.assertEqual(cfg["email_domain"], "example-tech.com")
        self.assertEqual(cfg["to_also"], ["lead@example-tech.com"])
        self.assertEqual(cfg["cc"], ["hr@example-tech.com"])
        self.assertEqual(len(cfg["directory"]), 2)
        self.assertEqual(cfg["threshold_min"], 270)

    def test_own_settings_win_and_own_directory_entries_are_kept(self):
        own = {"cc_list": [{"email": "me@example-tech.com", "field": "cc", "default": True}], "threshold_min": 240,
               "email_domain": "other.com", "directory": [{"name": "ann  LEE", "email": "ann2@example-tech.com"},
                                                          {"name": "Cy Park", "email": "cpark@example-tech.com"}]}
        cfg = make(own=own).config()
        self.assertEqual(cfg["cc"], ["me@example-tech.com"])
        self.assertEqual(cfg["email_domain"], "other.com")
        self.assertEqual(cfg["threshold_min"], 240)
        by = {e["name"].lower().split()[0]: e["email"] for e in cfg["directory"]}
        self.assertEqual(by, {"ann": "ann2@example-tech.com", "bo": "bchen@example-tech.com",
                              "cy": "cpark@example-tech.com"})

    def test_empty_own_values_take_the_team_ones(self):
        cfg = make(own={"cc_list": [], "email_domain": "", "directory": []}).config()
        self.assertEqual(cfg["email_domain"], "example-tech.com")
        self.assertEqual(len(cfg["cc_list"]), 2)

    def test_no_team_file_or_a_broken_one_changes_nothing(self):
        self.assertEqual(make(team=None).config()["directory"], [])
        root = Path(tempfile.mkdtemp())
        (root / "team-defaults.json").write_text("{not json", "utf-8")
        self.assertEqual(Store(root / "data", team_file=root / "team-defaults.json").config()["cc_list"], [])

    def test_save_team_writes_only_the_shareable_settings(self):
        st = make(team=None, own={"sender_name": "Sam Lee", "link": "https://example.sharepoint.com/x",
                                  "email_domain": "example-tech.com", "directory": TEAM["directory"]})
        data = json.loads(Path(st.save_team(st.config())).read_text("utf-8"))
        self.assertEqual(set(data) - {"_note"}, set(store.TEAM_KEYS))
        self.assertNotIn("sender_name", data)
        self.assertNotIn("link", data)


class Templates(unittest.TestCase):
    def test_an_unedited_older_default_upgrades_to_the_one_with_details(self):
        old_low = store.LEGACY_TEMPLATES["low"][-1]
        st = make(team=None, own={"templates": {"low": {"subject": old_low[0], "body": old_low[1]}}})
        self.assertIn("{details}", st.config()["templates"]["low"]["body"])

    def test_the_previous_default_is_exactly_the_new_one_without_details(self):
        new = store.DEFAULT_TEMPLATES["low"]
        self.assertEqual(store.LEGACY_TEMPLATES["low"][-1],
                         (new["subject"], new["body"].replace("{details}\n\n", "")))

    def test_an_edited_template_is_kept(self):
        st = make(team=None, own={"templates": {"low": {"subject": "Hi", "body": "Custom {stats}"}}})
        self.assertEqual(st.config()["templates"]["low"]["body"], "Custom {stats}")


if __name__ == "__main__":
    unittest.main()

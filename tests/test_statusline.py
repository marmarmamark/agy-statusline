#!/usr/bin/env python3
"""Unit tests for agy-statusline rendering and formatting."""

import json
import subprocess
import tempfile
import unittest
import sys
import os
from datetime import datetime, timezone, timedelta

# Import statusline module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import statusline
import statusline as sl

class TestStatusline(unittest.TestCase):

    def setUp(self):
        """
        Pin every ambient dependency. get_classifier_remaining() reads the real
        ~/.gemini/config/classifier_usage.json, so without this the rendering tests
        pass or fail depending on the developer's live classifier usage.
        """
        self._saved_usage_file = statusline.CLASSIFIER_USAGE_FILE
        self._saved_cache_file = statusline.CACHE_FILE
        statusline.CLASSIFIER_USAGE_FILE = "/nonexistent/classifier_usage.json"
        statusline.CACHE_FILE = "/nonexistent/agy_statusline_cache.json"

    def tearDown(self):
        statusline.CLASSIFIER_USAGE_FILE = self._saved_usage_file
        statusline.CACHE_FILE = self._saved_cache_file

    def test_strip_ansi(self):
        colored = "\033[32m5h: 80% left\033[0m"
        self.assertEqual(statusline.strip_ansi(colored), "5h: 80% left")

    def test_format_percentage_thresholds(self):
        # Green >= 50
        self.assertIn("\033[32m75%\033[0m", statusline.format_percentage(75))
        # Yellow >= 20 and < 50
        self.assertIn("\033[33m35%\033[0m", statusline.format_percentage(35))
        # Red < 20
        self.assertIn("\033[1;31m10%\033[0m", statusline.format_percentage(10))

    def test_format_countdown_seconds(self):
        # Hours and minutes
        self.assertEqual(statusline.format_countdown(seconds=7260), "2h 1m")
        # Minutes only
        self.assertEqual(statusline.format_countdown(seconds=1800), "30m")
        # Days
        self.assertEqual(statusline.format_countdown(seconds=100000), "1d 3h")
        # Resets soon
        self.assertEqual(statusline.format_countdown(seconds=0), "resets soon")
        self.assertEqual(statusline.format_countdown(seconds=-10), "resets soon")

    def test_format_countdown_iso_str(self):
        future = datetime.now(timezone.utc) + timedelta(hours=3, minutes=15)
        iso = future.isoformat()
        res = statusline.format_countdown(iso_str=iso)
        self.assertIn("h", res)
        self.assertIn("m", res)

    def test_render_statusline_full(self):
        sample_data = {
            "context_window": {"used_percentage": 35.0},
            "quota": {
                "gemini-5h": {
                    "remaining_fraction": 0.82,
                    "reset_in_seconds": 7200,
                    "reset_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                },
                "gemini-weekly": {
                    "remaining_fraction": 0.95
                }
            },
            "terminal_width": 120
        }
        output = statusline.render_statusline(sample_data, term_width=120)
        plain = statusline.strip_ansi(output)

        self.assertIn("35%", plain)
        self.assertIn("5h: 82% left", plain)
        self.assertIn("Week: 95% left", plain)
        self.assertIn("│", plain)

    def test_render_statusline_narrow_terminal_collapse(self):
        sample_data = {
            "context_window": {"used_percentage": 42.0},
            "quota": {
                "gemini-5h": {
                    "remaining_fraction": 0.60,
                    "reset_in_seconds": 3600,
                },
                "gemini-weekly": {
                    "remaining_fraction": 0.85
                }
            },
            "terminal_width": 40
        }
        # Width 35 forces compact layout
        output = statusline.render_statusline(sample_data, term_width=35)
        plain = statusline.strip_ansi(output)

        self.assertIn("Ctx: 42%", plain)
        self.assertIn("5h: 60%", plain)
        self.assertIn("Wk: 85%", plain)

    def test_format_countdown_naive_iso_str(self):
        # Naive datetime string without timezone must not crash with TypeError
        naive_str = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1, minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")
        res = statusline.format_countdown(iso_str=naive_str)
        self.assertTrue("h" in res or "m" in res or res == "resets soon")

    def test_render_statusline_tokens_fallback(self):
        sample = {
            "context_window": {"used_tokens": 25000, "total_tokens": 100000},
            "quota": {"gemini-5h": {"remaining_fraction": 0.90}}
        }
        output = statusline.render_statusline(sample, term_width=100)
        plain = statusline.strip_ansi(output)
        self.assertIn("25%", plain)
        self.assertIn("5h: 90% left", plain)

    def test_render_statusline_naive_reset_time(self):
        naive_rt = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        sample = {
            "quota": {
                "gemini-5h": {
                    "remaining_fraction": 0.50,
                    "reset_time": naive_rt
                }
            }
        }
        output = statusline.render_statusline(sample, term_width=100)
        plain = statusline.strip_ansi(output)
        self.assertIn("5h: 50% left", plain)

    def test_render_statusline_empty_data(self):
        output = statusline.render_statusline({})
        plain = statusline.strip_ansi(output)
        self.assertIn("[Quota: syncing...]", plain)

    def test_no_leading_divider_without_context_bar(self):
        """Quota tokens alone must not render a dangling '│' with nothing to its left."""
        statusline.CLASSIFIER_USAGE_FILE = self._saved_usage_file  # allow a real value
        sample = {"quota": {"gemini-5h": {"remaining_fraction": 0.5, "reset_in_seconds": 3600}}}
        plain = statusline.strip_ansi(statusline.render_statusline(sample, term_width=100))
        self.assertFalse(plain.lstrip().startswith("│"), f"dangling divider: {plain!r}")
        self.assertIn("5h: 50% left", plain)

    def test_subprocess_is_importable_for_background_sync(self):
        """
        trigger_background_quota_sync() calls subprocess.Popen inside a bare
        `except Exception: pass`. A missing import raised NameError there, silently
        disabling every quota refresh after a reset.
        """
        self.assertTrue(hasattr(statusline, "subprocess"))

class TestInstaller(unittest.TestCase):
    """Runs the real install.sh against a throwaway HOME."""

    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_install_sh_is_valid_bash(self):
        res = subprocess.run(["bash", "-n", os.path.join(self.REPO, "install.sh")],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)

    def _run_installer(self, existing_settings=None):
        home = tempfile.mkdtemp()
        settings = os.path.join(home, ".gemini", "antigravity-cli", "settings.json")
        os.makedirs(os.path.dirname(settings))
        if existing_settings is not None:
            with open(settings, "w") as f:
                json.dump(existing_settings, f)
        env = dict(os.environ, HOME=home)
        res = subprocess.run(["bash", os.path.join(self.REPO, "install.sh")],
                             capture_output=True, text=True, env=env, cwd=self.REPO)
        return home, settings, res

    def test_installer_writes_the_settings_file_agy_reads(self):
        """
        It used to write ~/.gemini/config/settings.json, which agy never loads, so the
        statusline installed and then never appeared.
        """
        home, settings, res = self._run_installer(existing_settings={})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.exists(settings), "did not write antigravity-cli/settings.json")
        with open(settings) as f:
            data = json.load(f)
        self.assertEqual(data["statusLine"]["type"], "command")
        self.assertIn("statusline.py", data["statusLine"]["command"])

    def test_installer_preserves_unrelated_settings_and_extra_keys(self):
        """
        The statusLine block was assigned wholesale, silently dropping keys the user
        had set (stack_with_default), and permissions must never be disturbed.
        """
        home, settings, res = self._run_installer(existing_settings={
            "permissions": {"allow": ["command(*)", "mcp(*)"]},
            "statusLine": {"type": "", "command": "python3 /old.py", "stack_with_default": True},
            "trustedWorkspaces": ["/somewhere"],
        })
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(settings) as f:
            data = json.load(f)
        self.assertEqual(data["statusLine"].get("stack_with_default"), True)
        self.assertEqual(data["permissions"]["allow"], ["command(*)", "mcp(*)"])
        self.assertEqual(data["trustedWorkspaces"], ["/somewhere"])
        self.assertEqual(data["statusLine"]["type"], "command")


class TestQuotaFreshness(unittest.TestCase):
    """The 5h reading stayed pinned because refreshes could never survive."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_background_sync_is_detached_from_the_caller(self):
        """
        `agy -p /usage` needs seconds; the statusline returns in milliseconds. Without
        start_new_session the child stayed in the caller's process group and was killed
        by the group teardown 2-3s in, so the sync never once completed.
        """
        src = open(os.path.join(os.path.dirname(__file__), "..", "statusline.py")).read()
        popen_call = src.split("subprocess.Popen(", 1)[1].split(")", 1)[0]
        self.assertIn("start_new_session=True", popen_call)

    def test_nested_render_does_not_write_the_cache(self):
        """A render triggered by our own quota fetch must not overwrite that fetch."""
        cache = os.path.join(self.tmp, "cache.json")
        with open(cache, "w") as f:
            json.dump({"quota": {"gemini-5h": {"remaining_fraction": 0.83,
                                               "reset_time": "2099-01-01T00:00:00Z"}}}, f)
        env = dict(os.environ, STATUSLINE_CACHE_PATH=cache, STATUSLINE_NO_RECURSE="1")
        payload = json.dumps({"quota": {"gemini-5h": {"remaining_fraction": 0.01,
                                                      "reset_time": "2020-01-01T00:00:00Z"}}})
        subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(__file__), "..", "statusline.py")],
                       input=payload, capture_output=True, text=True, env=env)
        with open(cache) as f:
            self.assertEqual(json.load(f)["quota"]["gemini-5h"]["remaining_fraction"], 0.83)

    def test_stale_payload_does_not_overwrite_fresher_cache(self):
        """A long-lived agy session pipes the quota it read at startup, forever."""
        fresh = {"remaining_fraction": 0.83, "reset_time": "2099-01-01T00:00:00Z"}
        stale = {"remaining_fraction": 0.01, "reset_time": "2020-01-01T00:00:00Z"}
        merged = sl.merge_quota({"gemini-5h": stale}, {"gemini-5h": fresh})
        self.assertEqual(merged["gemini-5h"], fresh)
        # ... and a genuinely newer reading still wins.
        merged = sl.merge_quota({"gemini-5h": fresh}, {"gemini-5h": stale})
        self.assertEqual(merged["gemini-5h"], fresh)
        # A bucket the cache has never seen is always adopted.
        self.assertEqual(sl.merge_quota({"new": stale}, {})["new"], stale)

    def test_elapsed_reset_does_not_fabricate_full_quota(self):
        """
        An elapsed timestamp means the reading is out of date, not that the bucket
        refilled. Reporting 100% invented a number that stuck for as long as the
        refresh kept failing -- which, given the process-group kill, was always.
        """
        out = sl.render_statusline({"quota": {"gemini-5h": {
            "remaining_fraction": 0.58, "reset_time": "2020-01-01T00:00:00Z"}}},
            term_width=200)
        plain = sl.strip_ansi(out)
        self.assertIn("58%", plain)
        self.assertIn("syncing", plain)
        self.assertNotIn("100%", plain)


class TestLiveWindowFreshness(unittest.TestCase):
    """The displayed figure has to be able to move while the window is still open."""

    FUTURE = "2099-01-01T00:00:00Z"
    LATER = "2099-06-01T00:00:00Z"

    def _bucket(self, frac, reset=None):
        return {"remaining_fraction": frac, "reset_time": reset or self.FUTURE}

    def test_usage_accrual_is_accepted_within_one_window(self):
        """
        reset_time is pinned for the whole window, so comparing it alone made every
        mid-window reading "not fresher" and froze the number at the window's first
        value. Usage only accumulates, so a smaller fraction is the later reading.
        """
        merged = sl.merge_quota({"g": self._bucket(0.65)}, {"g": self._bucket(0.67)})
        self.assertEqual(merged["g"]["remaining_fraction"], 0.65)

    def test_stale_higher_reading_still_loses_within_one_window(self):
        merged = sl.merge_quota({"g": self._bucket(0.67)}, {"g": self._bucket(0.65)})
        self.assertEqual(merged["g"]["remaining_fraction"], 0.65)

    def test_window_rollover_beats_the_fraction_rule(self):
        """A refilled bucket has a higher fraction; the newer window must still win."""
        merged = sl.merge_quota({"g": self._bucket(0.99, self.LATER)},
                                {"g": self._bucket(0.10)})
        self.assertEqual(merged["g"]["reset_time"], self.LATER)
        merged = sl.merge_quota({"g": self._bucket(0.10)},
                                {"g": self._bucket(0.99, self.LATER)})
        self.assertEqual(merged["g"]["reset_time"], self.LATER)

    def test_live_window_requests_a_refresh(self):
        """A sync used to be requested only after the window had already expired."""
        calls = []
        original = sl.trigger_background_quota_sync
        sl.trigger_background_quota_sync = lambda *a, **k: calls.append(a[0] if a else None)
        try:
            sl.render_statusline({"quota": {"gemini-5h": {
                "remaining_fraction": 0.83, "reset_time": self.FUTURE,
                "reset_in_seconds": 9000}}}, term_width=200)
            self.assertEqual(calls, [sl.SYNC_INTERVAL_SECS])

            calls.clear()
            sl.render_statusline({"quota": {"gemini-5h": {
                "remaining_fraction": 0.08, "reset_time": self.FUTURE,
                "reset_in_seconds": 9000}}}, term_width=200)
            self.assertEqual(calls, [sl.SYNC_INTERVAL_URGENT_SECS],
                             "near exhaustion the figure should be re-measured sooner")
        finally:
            sl.trigger_background_quota_sync = original

    def test_nested_render_never_spawns_a_sync(self):
        """A nested render belongs to a sync already in flight."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            cooldown = tf.name
        saved_cooldown = sl.COOLDOWN_FILE
        sl.COOLDOWN_FILE = cooldown
        os.environ["STATUSLINE_NO_RECURSE"] = "1"
        try:
            if os.path.exists(cooldown):
                os.remove(cooldown)
            sl.trigger_background_quota_sync(20)
            self.assertFalse(os.path.exists(cooldown))
        finally:
            sl.COOLDOWN_FILE = saved_cooldown
            os.environ.pop("STATUSLINE_NO_RECURSE", None)
            if os.path.exists(cooldown):
                os.remove(cooldown)


if __name__ == "__main__":
    unittest.main()

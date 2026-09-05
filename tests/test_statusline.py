#!/usr/bin/env python3
"""Unit tests for agy-statusline rendering and formatting."""

import unittest
import sys
import os
from datetime import datetime, timezone, timedelta

# Import statusline module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import statusline

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

if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
agy-statusline: Claude Code-style Statusline for Antigravity CLI (agy)
---------------------------------------------------------------------
Displays an interactive, color-coded statusline in the terminal:
[Context Bar] XX%  │  5h: XX% left (countdown) · Week: XX% left · Auto: XXXX left

Reads JSON payload piped by `agy` via stdin and caches state in /tmp/agy_statusline_cache.json.
When quota resets, triggers an asynchronous background sync without freezing the terminal.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

# Overridable so a self-test or a harness can render a sample payload without
# writing it over the real quota cache that agy-auto-resume and gemini-worker read.
CACHE_FILE = os.environ.get("STATUSLINE_CACHE_PATH") or "/tmp/agy_statusline_cache.json"
CLASSIFIER_USAGE_FILE = os.path.expanduser("~/.gemini/config/classifier_usage.json")
DEFAULT_CLASSIFIER_LIMIT = 1500

def get_classifier_remaining():
    """Retrieve remaining daily AI classifier requests using a rolling 24-hour sliding window."""
    if os.path.exists(CLASSIFIER_USAGE_FILE):
        try:
            with open(CLASSIFIER_USAGE_FILE, "r") as f:
                data = json.load(f)
                cutoff = time.time() - 86400
                timestamps = [t for t in data.get("timestamps", []) if isinstance(t, (int, float)) and t > cutoff]
                daily_limit = data.get("daily_limit", DEFAULT_CLASSIFIER_LIMIT)
                if timestamps or "timestamps" in data:
                    return max(0, daily_limit - len(timestamps))
                return data.get("remaining", daily_limit)
        except Exception:
            pass
    return None

def format_countdown(seconds=None, iso_str=None):
    """Format remaining time into a concise, human-friendly countdown."""
    if seconds is None and iso_str:
        try:
            rt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            if rt.tzinfo is None:
                rt = rt.replace(tzinfo=timezone.utc)
            seconds = (rt - datetime.now(timezone.utc)).total_seconds()
        except Exception:
            seconds = None

    if seconds is None or seconds <= 0:
        return "resets soon"

    sec_int = int(seconds)
    hrs = sec_int // 3600
    mins = (sec_int % 3600) // 60
    if hrs >= 24:
        days = hrs // 24
        rem_hrs = hrs % 24
        return f"{days}d {rem_hrs}h"
    elif hrs > 0:
        return f"{hrs}h {mins}m"
    else:
        return f"{mins}m"

def colorize(text, color_code):
    """Wrap text with ANSI color code."""
    return f"\033[{color_code}m{text}\033[0m"

def strip_ansi(text):
    """Remove ANSI escape sequences from text for width calculation."""
    return re.sub(r"\033\[[0-9;]*m", "", text)

def format_percentage(pct):
    """Colorize percentages (Green >= 50%, Yellow >= 20%, Bold Red < 20%)."""
    if pct >= 50:
        return colorize(f"{pct}%", "32")      # Green
    elif pct >= 20:
        return colorize(f"{pct}%", "33")      # Yellow
    else:
        return colorize(f"{pct}%", "1;31")    # Bold Red

def find_agy_binary():
    """Locate the agy executable in PATH or standard user directories."""
    found = shutil.which("agy")
    if found:
        return found
    candidates = [
        os.path.expanduser("~/.local/bin/agy"),
        os.path.expanduser("~/.antigravity-ide/antigravity-ide/bin/agy"),
        "/usr/local/bin/agy",
        "/opt/homebrew/bin/agy",
    ]
    for c in candidates:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return "agy"

def trigger_background_quota_sync():
    """Trigger an asynchronous, non-blocking background fetch of fresh quota from agy."""
    cooldown_file = "/tmp/agy_quota_sync_cooldown"
    now = time.time()
    if os.path.exists(cooldown_file):
        try:
            with open(cooldown_file, "r") as f:
                last_time = float(f.read().strip())
                if now - last_time < 60:
                    return
        except Exception:
            pass
    try:
        with open(cooldown_file, "w") as f:
            f.write(str(now))
    except Exception:
        pass

    agy_bin = find_agy_binary()
    env = os.environ.copy()
    env["STATUSLINE_NO_RECURSE"] = "1"
    env["AGY_BIN_PATH"] = agy_bin
    env["STATUSLINE_CACHE_PATH"] = CACHE_FILE

    bg_script = """
import json, subprocess, os
try:
    agy_bin = os.environ.get("AGY_BIN_PATH", "agy")
    cache_file = os.environ.get("STATUSLINE_CACHE_PATH", "/tmp/agy_statusline_cache.json")
    env = os.environ.copy()
    env["STATUSLINE_NO_RECURSE"] = "1"
    res = subprocess.run(
        [agy_bin, "-p", "/usage", "--output-format", "json"],
        capture_output=True, text=True, timeout=20, env=env
    )
    if res.returncode == 0:
        data = json.loads(res.stdout)
        cmd_data = data.get("command", {}).get("data", {})
        buckets = cmd_data.get("groups") or data.get("data", {}).get("groups") or data.get("groups", [])
        new_quota = {}
        for g in buckets:
            for b in g.get("buckets", []):
                bid = b.get("id")
                if bid:
                    new_quota[bid] = {
                        "remaining_fraction": b.get("remaining_fraction"),
                        "reset_in_seconds": b.get("reset_in_seconds"),
                        "reset_time": b.get("reset_time"),
                    }
        cdata = {}
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cdata = json.load(f)
            except Exception:
                cdata = {}
        cdata.setdefault("quota", {})
        cdata["quota"].update(new_quota)
        tmp = cache_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cdata, f)
        os.replace(tmp, cache_file)
except Exception:
    pass
"""
    try:
        subprocess.Popen(
            [sys.executable, "-c", bg_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            close_fds=True,
            # `agy -p /usage` needs ~4s, and the statusline that spawned it returns
            # in milliseconds. Closing fds is not detaching: the child stayed in the
            # caller's process group, so the group teardown that follows the
            # statusline command killed it 2-3s in -- every time, silently. It has
            # to outlive its parent to be a background sync at all.
            start_new_session=True,
        )
    except Exception:
        pass

def render_statusline(data, term_width=80):
    """Render the full statusline string based on JSON input data."""
    parts = []

    # 1. Context Window Usage Bar (Claude Code style)
    ctx = data.get("context_window", {})
    used_pct = ctx.get("used_percentage")
    if used_pct is None:
        used_tokens = ctx.get("used_tokens") or ctx.get("tokens") or ctx.get("current_usage")
        total_tokens = ctx.get("total_tokens") or ctx.get("max_tokens") or ctx.get("capacity")
        if used_tokens is not None and total_tokens:
            try:
                used_pct = (float(used_tokens) / float(total_tokens)) * 100
            except Exception:
                pass
    if used_pct is not None:
        bar_width = 10
        filled = max(0, min(bar_width, int(round((used_pct / 100) * bar_width))))
        empty = bar_width - filled
        bar = "█" * filled + "░" * empty
        pct_rounded = int(round(used_pct))
        parts.append(f"[{bar}] {pct_rounded}%")

    # 2. Quota Usage Limits
    quota_data = data.get("quota") or data.get("current_usage", {}).get("quota") or {}

    g_5h = quota_data.get("gemini-5h")
    g_wk = quota_data.get("gemini-weekly")

    quota_tokens = []
    if isinstance(g_5h, dict):
        rem_frac = g_5h.get("remaining_fraction")
        secs = g_5h.get("reset_in_seconds")
        reset_time = g_5h.get("reset_time")

        reset_elapsed = False
        if reset_time:
            try:
                rt = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
                if rt.tzinfo is None:
                    rt = rt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= rt:
                    reset_elapsed = True
            except Exception:
                pass
        if secs is not None and secs <= 0 and reset_time:
            reset_elapsed = True

        syncing = False
        if reset_elapsed and (rem_frac is None or rem_frac < 0.95):
            # An elapsed timestamp means this reading is out of date. It is not
            # evidence that the bucket refilled, and reporting 100% here invented
            # a number -- one that stuck at 100% for as long as the refresh failed
            # to land. Show the last figure actually measured, marked as stale.
            syncing = True
            pct = max(0, min(100, int(round(rem_frac * 100)))) if rem_frac is not None else None
            cd = None
            trigger_background_quota_sync()
        else:
            pct = max(0, min(100, int(round(rem_frac * 100)))) if rem_frac is not None else 100
            cd = format_countdown(seconds=secs, iso_str=reset_time)

        if pct is None:
            token = "5h: " + colorize("syncing", "90")
        else:
            token = f"5h: {format_percentage(pct)} left"
            if pct < 100 and cd and cd != "resets soon":
                token += f" ({colorize(cd, '90')})"
            if syncing:
                token += " " + colorize("(syncing)", "90")
        quota_tokens.append(token)

    if isinstance(g_wk, dict):
        rem_frac = g_wk.get("remaining_fraction")
        if rem_frac is not None:
            pct = max(0, min(100, int(round(rem_frac * 100))))
            quota_tokens.append(f"Week: {format_percentage(pct)} left")

    # 3. Auto-Mode Classifier Daily Free Quota
    rem_ai = get_classifier_remaining()
    rem_str = ""
    if rem_ai is not None:
        if rem_ai >= 500:
            rem_str = colorize(f"{rem_ai}", "32")
        elif rem_ai >= 100:
            rem_str = colorize(f"{rem_ai}", "33")
        else:
            rem_str = colorize(f"{rem_ai}", "1;31")
        quota_tokens.append(f"Auto: {rem_str} left")

    if quota_tokens:
        # The divider separates the context bar from the quota tokens, so it is only
        # meaningful when there is something to its left
        if parts:
            parts.append(colorize("│", "90"))
        parts.append(" · ".join(quota_tokens))

    full_str = "  ".join(parts) if parts else colorize("[Quota: syncing...]", "90")

    # Responsive width fallback for narrow windows
    if strip_ansi(full_str).__len__() > term_width and term_width > 30:
        compact_parts = []
        if used_pct is not None:
            compact_parts.append(f"Ctx: {int(round(used_pct))}%")
        c_tokens = []
        if isinstance(g_5h, dict) and g_5h.get("remaining_fraction") is not None:
            pct = max(0, min(100, int(round(g_5h["remaining_fraction"] * 100))))
            c_tokens.append(f"5h: {format_percentage(pct)}")
        if isinstance(g_wk, dict) and g_wk.get("remaining_fraction") is not None:
            pct = max(0, min(100, int(round(g_wk["remaining_fraction"] * 100))))
            c_tokens.append(f"Wk: {format_percentage(pct)}")
        if rem_ai is not None:
            c_tokens.append(f"Auto: {rem_str}")
        if c_tokens:
            if compact_parts:
                compact_parts.append(colorize("│", "90"))
            compact_parts.append(" · ".join(c_tokens))
        full_str = "  ".join(compact_parts)

    return full_str

def is_nested_render():
    """
    True when this render was triggered by our own `agy -p /usage` quota fetch.

    agy renders its statusline on startup, including for a headless -p run, so
    every quota sync spawned a nested render of this script. The flag was set by
    all three callers and read by none, so the nested render wrote agy's payload
    straight back over the cache the sync was about to refresh.
    """
    return os.environ.get("STATUSLINE_NO_RECURSE") == "1"

def quota_is_fresher(candidate, incumbent):
    """
    True when `candidate` is a more current reading than `incumbent`.

    Freshness is the reset timestamp: a bucket whose window has not yet rolled
    over describes the window we are actually in. Without this a long-lived agy
    session kept piping the quota it read at startup, which overwrote every
    successful background refresh and pinned the display to a stale window.
    """
    def reset_of(bucket):
        if not isinstance(bucket, dict):
            return None
        raw = bucket.get("reset_time")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            return None

    new_reset, old_reset = reset_of(candidate), reset_of(incumbent)
    if old_reset is None:
        return new_reset is not None or isinstance(candidate, dict)
    if new_reset is None:
        return False
    return new_reset > old_reset

def merge_quota(incoming, cached):
    """Keep the freshest reading per bucket rather than letting either side win wholesale."""
    merged = dict(cached or {})
    for bucket_id, bucket in (incoming or {}).items():
        if bucket_id not in merged or quota_is_fresher(bucket, merged[bucket_id]):
            merged[bucket_id] = bucket
    return merged

def main():
    cached_data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cached_data = json.load(f)
        except Exception:
            pass

    stdin_data = None
    try:
        if not sys.stdin.isatty():
            import select
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                raw = sys.stdin.read()
                if raw and raw.strip():
                    stdin_data = json.loads(raw)
    except Exception:
        pass

    if stdin_data:
        merged_quota = merge_quota(stdin_data.get("quota"), cached_data.get("quota"))
        if merged_quota:
            stdin_data["quota"] = merged_quota
        # A nested render is a side effect of our own quota fetch. Its payload is
        # not newer than what the fetch is about to write, so it must not persist.
        if not is_nested_render():
            try:
                tmp = CACHE_FILE + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(stdin_data, f)
                os.replace(tmp, CACHE_FILE)
            except Exception:
                pass
    else:
        stdin_data = cached_data

    if not stdin_data:
        print(colorize("[Quota: initial run, starting CLI...]", "90"))
        return

    term_width = stdin_data.get("terminal_width", 80)
    output = render_statusline(stdin_data, term_width=term_width)
    print(output)

if __name__ == "__main__":
    main()

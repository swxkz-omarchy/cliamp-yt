#!/usr/bin/env python3
"""Tests for the pure logic in ~/.local/bin/ytplay.

Run: python3 ~/.local/share/ytplay/test_ytplay.py
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import unittest
from pathlib import Path

SCRIPT = Path.home() / ".local/bin/ytplay"


def load_ytplay():
    loader = importlib.machinery.SourceFileLoader("ytplay", str(SCRIPT))
    spec = importlib.util.spec_from_loader("ytplay", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ytplay = load_ytplay()
WATCH = "https://www.youtube.com/watch?v={}"
PLAYLIST = "https://www.youtube.com/playlist?list={}"


class Normalize(unittest.TestCase):
    def kind_url(self, raw):
        return ytplay.normalize(raw)

    def test_playlist_url_drops_tracking_params(self):
        self.assertEqual(
            self.kind_url("https://www.youtube.com/playlist?list=PLabc&si=xyz&pp=1"),
            ("playlist", PLAYLIST.format("PLabc")),
        )

    def test_youtube_music_host_is_canonicalized(self):
        self.assertEqual(
            self.kind_url("https://music.youtube.com/playlist?list=PLabc"),
            ("playlist", PLAYLIST.format("PLabc")),
        )

    def test_short_and_live_links_become_watch_urls(self):
        for path in ("shorts", "live", "embed"):
            with self.subTest(path=path):
                self.assertEqual(
                    self.kind_url(f"https://www.youtube.com/{path}/dQw4w9WgXcQ?feature=share"),
                    ("video", WATCH.format("dQw4w9WgXcQ")),
                )

    def test_youtu_be_timestamp_is_stripped(self):
        self.assertEqual(
            self.kind_url("https://youtu.be/dQw4w9WgXcQ?t=42"),
            ("video", WATCH.format("dQw4w9WgXcQ")),
        )

    def test_watch_with_list_keeps_both(self):
        kind, url = self.kind_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc&si=q")
        self.assertEqual(kind, "playlist")
        self.assertEqual(url, WATCH.format("dQw4w9WgXcQ") + "&list=PLabc")

    def test_bare_playlist_id(self):
        self.assertEqual(self.kind_url("OLAK5uy_kLX9SLT4x0YMDgOEm9kj3a"), ("playlist", PLAYLIST.format("OLAK5uy_kLX9SLT4x0YMDgOEm9kj3a")))

    def test_bare_video_id(self):
        self.assertEqual(self.kind_url("dQw4w9WgXcQ"), ("video", WATCH.format("dQw4w9WgXcQ")))

    def test_url_is_pulled_out_of_surrounding_text(self):
        self.assertEqual(
            self.kind_url("listen to this https://youtu.be/dQw4w9WgXcQ it's good"),
            ("video", WATCH.format("dQw4w9WgXcQ")),
        )

    def test_cliamp_link_is_unwrapped(self):
        self.assertEqual(
            self.kind_url("cliamp://play?url=https%3A%2F%2Fyoutu.be%2FdQw4w9WgXcQ"),
            ("video", WATCH.format("dQw4w9WgXcQ")),
        )

    def test_cliamp_link_without_url_is_rejected(self):
        with self.assertRaises(ytplay.UserError):
            self.kind_url("cliamp://play?provider=ytmusic&q=aphex")

    def test_non_youtube_host_is_rejected(self):
        with self.assertRaises(ytplay.UserError):
            self.kind_url("https://vimeo.com/12345")

    def test_local_path_is_rejected(self):
        with self.assertRaises(ytplay.UserError):
            self.kind_url("/home/me/Music")

    def test_empty_target_is_rejected(self):
        with self.assertRaises(ytplay.UserError):
            self.kind_url("   ")

    def test_malformed_video_id_is_rejected(self):
        with self.assertRaises(ytplay.UserError):
            self.kind_url("https://www.youtube.com/watch?v=short")


class FmtTime(unittest.TestCase):
    def test_formats(self):
        cases = {0: "0s", 45: "45s", 90: "1m 30s", 3600: "1h 00m", 3660: "1h 01m"}
        for seconds, expected in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(ytplay.fmt_time(seconds), expected)

    def test_none_is_zero(self):
        self.assertEqual(ytplay.fmt_time(None), "0s")


class CleanError(unittest.TestCase):
    def test_strips_job_prefix_and_collapses_whitespace(self):
        raw = "job failed (internal_error): operation failed (resolving youtube https://x:\n  boom)"
        self.assertEqual(ytplay.clean_error(raw), "operation failed (resolving youtube https://x: boom)")

    def test_plain_message_is_untouched(self):
        self.assertEqual(ytplay.clean_error("This video is unavailable"), "This video is unavailable")


class FailureHint(unittest.TestCase):
    AGE = "youtube resolve: login required to confirm your age"
    PRIVATE = "youtube resolve: user restricted access to this video"
    GONE = "youtube resolve: cannot playback and download, status: ERROR, reason: This video is unavailable"

    def test_age_gated_points_at_cookies(self):
        hint = ytplay.failure_hint(self.AGE, "video", False)
        self.assertIn("cookies_from", hint)
        self.assertIn("cliamp setup", hint)

    def test_private_points_at_cookies(self):
        self.assertIn("cookies_from", ytplay.failure_hint(self.PRIVATE, "playlist", False))

    def test_configured_cookies_says_restart_instead(self):
        hint = ytplay.failure_hint(self.AGE, "video", True)
        self.assertIn("restart", hint.lower())
        self.assertNotIn("cliamp setup", hint)

    def test_dead_playlist_id_says_check_the_id(self):
        hint = ytplay.failure_hint(self.GONE, "playlist", False)
        self.assertIn("check the id", hint)
        self.assertNotIn("cookies_from", hint)

    def test_unavailable_single_video_gets_no_playlist_hint(self):
        self.assertEqual(ytplay.failure_hint(self.GONE, "video", False), "")

    def test_unrelated_error_gets_no_hint(self):
        self.assertEqual(ytplay.failure_hint("yt-dlp: command not found", "playlist", False), "")

    def test_user_error_carries_hint(self):
        self.assertEqual(ytplay.UserError("boom", "try this").hint, "try this")
        self.assertEqual(ytplay.UserError("boom").hint, "")


class Cli(unittest.TestCase):
    def test_repeat_rejects_unknown_mode(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ytplay.parse_args(["--repeat", "sometimes", WATCH.format("dQw4w9WgXcQ")])

    def test_defaults(self):
        args = ytplay.parse_args([WATCH.format("dQw4w9WgXcQ")])
        self.assertFalse(args.queue)
        self.assertFalse(args.dry_run)
        self.assertIsNone(args.shuffle)
        self.assertIsNone(args.repeat)


if __name__ == "__main__":
    unittest.main(verbosity=2)

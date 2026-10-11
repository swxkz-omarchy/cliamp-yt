#!/usr/bin/env python3
"""ytplay - hand a YouTube playlist, mix, or video to cliamp.

Loads the target into a running cliamp over IPC, or boots the retro player
on it when nothing is running.

  ytplay 'https://www.youtube.com/playlist?list=PL...'   load and play
  ytplay PLbpi6ZahtOH6Blw3RGYpWkSByi_T7Rygb            bare playlist id
  ytplay 'listen to this https://youtu.be/dQw4w9WgXcQ'  pasted text
  ytplay -c                                           from the clipboard
  ytplay <url> --shuffle --repeat all                  queue it shuffled
  ytplay <url> --queue                                append, do not disturb
  ytplay <url> --dry-run                              resolve only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

CLIAMP = shutil.which("cliamp") or "cliamp"
YTDLP = shutil.which("yt-dlp")

WATCH = "https://www.youtube.com/watch?v={}"
PLAYLIST = "https://www.youtube.com/playlist?list={}"

YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "gaming.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
    "www.youtu.be",
}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}
URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]]+")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
LIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{5,}$")
PATH_VIDEO_RE = re.compile(r"^/(?:shorts|live|embed|v|e)/([^/?#]+)")
JOB_ERR_RE = re.compile(r"^(?:job failed|remote operation failed) \([^)]*\):\s*")
TUI_WIDTH_FALLBACK = 80
PREVIEW_TRACKS = 12
REPORT_TRACKS = 5


class UserError(Exception):
    """Anything worth showing the user without a traceback."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


# ---------------------------------------------------------------- terminal


def use_color(stream) -> bool:
    return (
        stream.isatty()
        and os.environ.get("NO_COLOR") is None
        and os.environ.get("TERM") != "dumb"
    )


class Out:
    def __init__(self) -> None:
        self.color = use_color(sys.stdout)
        self.quiet = False

    def _c(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.color else text

    def dim(self, text: str) -> str:
        return self._c("2", text)

    def good(self, text: str) -> str:
        return self._c("1;32", text)

    def bad(self, text: str) -> str:
        return self._c("1;31", text)

    def head(self, text: str) -> str:
        return self._c("1;36", text)

    def say(self, text: str = "") -> None:
        if not self.quiet:
            print(text)

    def note(self, text: str) -> None:
        print(self.dim(text), file=sys.stderr)


out = Out()


def term_width(default: int = TUI_WIDTH_FALLBACK) -> int:
    return shutil.get_terminal_size((default, 24)).columns


def fmt_time(seconds: float) -> str:
    seconds = int(seconds or 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def clean_error(text: str) -> str:
    text = " ".join(str(text).split())
    previous = None
    while previous != text:
        previous = text
        text = JOB_ERR_RE.sub("", text)
    return text


# ----------------------------------------------------------------- targets


def first_url(text: str) -> str | None:
    match = URL_RE.search(text)
    return match.group(0) if match else None


def unwrap_cliamp_link(text: str) -> str:
    if not text.lower().startswith("cliamp://"):
        return text
    parsed = urlparse(text)
    target = parse_qs(parsed.query).get("url", [None])[0]
    if not target:
        raise UserError(
            "cliamp:// link carries no url= parameter "
            "(try cliamp://play?url=<youtube link>)"
        )
    return target


def normalize(raw: str) -> tuple[str, str]:
    """Return (kind, url) for a playlist or a single video."""
    text = raw.strip().strip("<>\"'").replace("\\&", "&")
    text = unwrap_cliamp_link(text.strip())

    url = first_url(text)
    if url is None:
        token = text.split()
        if len(token) == 1 and VIDEO_ID_RE.match(token[0]):
            return "video", WATCH.format(token[0])
        if len(token) == 1 and LIST_ID_RE.match(token[0]):
            return "playlist", PLAYLIST.format(token[0])
        raise UserError(
            "no YouTube link or id found in: " + (text[:70] or "<empty>")
        )

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in YT_HOSTS:
        raise UserError(f"not a YouTube link: {host or url}")

    query = parse_qs(parsed.query)
    video = query.get("v", [None])[0]
    playlist = query.get("list", [None])[0]

    if host in SHORT_HOSTS:
        video = parsed.path.lstrip("/") or video
    else:
        match = PATH_VIDEO_RE.match(parsed.path)
        if match:
            video = match.group(1)

    if video and not VIDEO_ID_RE.match(video):
        raise UserError(f"malformed video id in: {url}")
    if playlist and not LIST_ID_RE.match(playlist):
        raise UserError(f"malformed playlist id in: {url}")

    if playlist and not video:
        return "playlist", PLAYLIST.format(playlist)
    if video and playlist:
        # cliamp expands the list= parameter into the whole playlist.
        return "playlist", f"{WATCH.format(video)}&{urlencode({'list': playlist})}"
    if video:
        return "video", WATCH.format(video)
    raise UserError(f"no video or playlist id in: {url}")


def read_input(args: argparse.Namespace) -> str:
    if args.target:
        return args.target
    if args.clip:
        return read_clipboard()
    raise UserError("give a YouTube link, id, or use -c for the clipboard")


def read_clipboard() -> str:
    candidates = (
        ["wl-paste", "--no-newline"],
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "--clipboard", "--output"],
        ["pbpaste"],
    )
    for command in candidates:
        if not shutil.which(command[0]):
            continue
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    raise UserError("no clipboard tool found (tried wl-paste, xclip, xsel, pbpaste)")


# ------------------------------------------------------------------ player


def cliamp(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        [CLIAMP, *args], capture_output=True, text=True, timeout=timeout
    )


def player_state() -> dict | None:
    """Runtime snapshot of a live cliamp, or None when nothing is running."""
    try:
        result = cliamp("remote", "state", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout).get("snapshot")
    except (json.JSONDecodeError, AttributeError):
        return None


def call(operation: str, params: dict | None = None, timeout: int = 300) -> dict:
    result = cliamp(
        "remote", "call", operation, "--params", json.dumps(params or {}),
        "--wait", timeout=timeout,
    )
    raw = result.stdout.strip()
    if not raw:
        # A failed job reports on stderr and prints no JSON envelope.
        detail = clean_error(result.stderr or result.stdout)
        raise UserError(detail or f"cliamp {operation} failed (exit {result.returncode})")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise UserError(clean_error(raw)) from None

    job = payload.get("job") or {}
    if job.get("state") and job["state"] != "succeeded":
        raise UserError(clean_error(job.get("error") or raw))
    result_body = job.get("result")
    return result_body if isinstance(result_body, dict) else {}


def set_mode(flag: str, value: str) -> None:
    result = cliamp(flag, value, timeout=15)
    if result.returncode != 0:
        raise UserError(
            f"cliamp {flag} {value} failed: "
            f"{clean_error(result.stderr or result.stdout)}"
        )


def cookies_configured() -> bool:
    """True when cliamp already has a yt-dlp cookie source set."""
    try:
        text = (Path.home() / ".config/cliamp/config.toml").read_text()
    except OSError:
        return False
    return any(line.strip().startswith("cookies_from") for line in text.splitlines())


def cookies_hint(configured: bool) -> str:
    if configured:
        return (
            "cookies_from is set in ~/.config/cliamp/config.toml. cliamp reads it "
            "at startup, so restart the player to use it."
        )
    return (
        'private and age-gated playlists need browser cookies. Add to '
        '~/.config/cliamp/config.toml (or run `cliamp setup`):\n'
        "  [ytmusic]\n"
        '  cookies_from = "chrome"   # firefox, chromium, brave, edge, opera, vivaldi\n'
        "then restart the player."
    )


def failure_hint(text: str, kind: str, configured: bool) -> str:
    """Turn cliamp's resolver wording into the one line that actually helps."""
    low = text.lower()
    gated = (
        "login required to confirm your age",
        "sign in to confirm",
        "restricted access",
        "private video",
        "members-only",
        "join this channel",
    )
    if any(marker in low for marker in gated):
        return cookies_hint(configured)
    if kind == "playlist" and "unavailable" in low:
        return (
            "YouTube could not find that playlist: check the id, or whether it is "
            "public, unlisted, or gone."
        )
    return ""


# ------------------------------------------------------------------ report


def report(result: dict, queued_only: bool) -> None:
    tracks = result.get("tracks") or []
    total = int(result.get("total") or len(tracks))
    seconds = sum(float(t.get("duration_secs") or 0) for t in tracks)

    if not out.color:
        state = "queued" if queued_only else "playing"
        out.say(f"ytplay: {total} track(s), {fmt_time(seconds)}, {state} in cliamp")
        return

    state = "queued" if queued_only else "playing"
    head = out.good(f"▸ {total} track{'s' if total != 1 else ''}")
    tail = f"{fmt_time(seconds)}  {out.dim(state + ' in cliamp')}"
    out.say(f"{head}  {tail}")

    listed = tracks[:REPORT_TRACKS]
    number = int(tracks[0].get("index") or 0) if tracks else 0
    for offset, track in enumerate(listed, start=number + 1):
        title = (track.get("title") or "?").strip()
        artist = (track.get("artist") or "").strip()
        line = f"  {offset:>2}. {title}"
        if artist:
            line += out.dim(f"  — {artist}")
        out.say(line[: term_width()])
    remaining = total - len(listed)
    if remaining > 0:
        out.say(out.dim(f"      … {remaining} more"))


# -------------------------------------------------------------------- runs


def dry_run(kind: str, url: str) -> int:
    out.say(f"{out.head('ytplay')} would load {out.dim(kind)}")
    out.say(f"  {url}")
    if not YTDLP:
        out.note("yt-dlp not found on PATH; cannot list the tracks")
        return 0
    try:
        result = subprocess.run(
            [YTDLP, "--flat-playlist", "--no-warnings",
             "--print", "%(title)s\t%(duration)s", url],
            capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        out.note(f"yt-dlp failed: {exc}")
        return 1
    if result.returncode != 0:
        raise UserError(clean_error(result.stderr) or "yt-dlp failed")

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        out.note("yt-dlp returned no entries")
        return 1
    for line in lines[:PREVIEW_TRACKS]:
        title, _, duration = line.partition("\t")
        seconds = float(duration) if duration.strip().isdigit() else 0
        suffix = out.dim(f"  {fmt_time(seconds)}") if seconds else ""
        out.say(f"  {title}{suffix}")
    if len(lines) > PREVIEW_TRACKS:
        out.say(out.dim(f"  … {len(lines) - PREVIEW_TRACKS} more"))
    return 0


def cold_start(kind: str, url: str, args: argparse.Namespace) -> int:
    flags: list[str] = []
    if args.queue:
        flags.append("--no-auto-play")
    if args.shuffle:
        flags.append("--shuffle")
    if args.repeat:
        flags += ["--repeat", args.repeat]
    out.note(out.dim(f"▸ cliamp is not running — starting the player on {kind}"))
    sys.stdout.flush()
    os.execvp(CLIAMP, [CLIAMP, *flags, url])


def warm_start(kind: str, url: str, args: argparse.Namespace, snapshot: dict) -> dict:
    idle_before = snapshot.get("state") in (None, "stopped")
    try:
        result = call("url.load", {"path": url, "play": True})
    except UserError as error:
        raise UserError(
            str(error), failure_hint(str(error), kind, cookies_configured())
        ) from None

    if args.shuffle:
        set_mode("shuffle", args.shuffle)
    if args.repeat:
        set_mode("repeat", args.repeat)

    queued_only = args.queue and idle_before
    if queued_only:
        paused = cliamp("pause", timeout=15)
        if paused.returncode != 0:
            out.note("loaded, but pausing the fresh queue failed: "
                     + (clean_error(paused.stderr or paused.stdout) or "unknown error"))
    report(result, queued_only)
    return result


# -------------------------------------------------------------------- main


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ytplay",
        description="Play any YouTube playlist, mix, or video in cliamp.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  ytplay 'https://music.youtube.com/playlist?list=PL...'\n"
            "  ytplay PLbpi6ZahtOH6Blw3RGYpWkSByi_T7Rygb\n"
            "  ytplay -c --shuffle --repeat all\n"
            "  ytplay 'https://youtu.be/dQw4w9WgXcQ' --queue\n"
        ),
    )
    parser.add_argument("target", nargs="?", help="link, playlist id, or pasted text")
    parser.add_argument("-c", "--clip", action="store_true", help="read the target from the clipboard")
    parser.add_argument("-q", "--queue", action="store_true",
                        help="append without starting playback")
    parser.add_argument("--shuffle", choices=("on", "off"), help="set shuffle mode")
    parser.add_argument("--repeat", choices=("off", "all", "one"), help="set repeat mode")
    parser.add_argument("--dry-run", action="store_true",
                        help="resolve with yt-dlp and print the track list, load nothing")
    parser.add_argument("--json", action="store_true",
                        help="print the resolved tracks as JSON")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out.quiet = args.json
    if not CLIAMP:
        out.note("cliamp is not installed")
        return 1
    if not YTDLP:
        out.note("yt-dlp is not on PATH; cliamp needs it for YouTube")

    kind, url = normalize(read_input(args))

    if args.dry_run:
        return dry_run(kind, url)

    snapshot = player_state()
    if snapshot is None:
        if args.json:
            out.note("cliamp is not running; nothing to hand the target to")
            return 1
        return cold_start(kind, url, args)

    result = warm_start(kind, url, args, snapshot)
    if args.json:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except UserError as error:
        print(f"ytplay: {out.bad(str(error))}", file=sys.stderr)
        if error.hint:
            print(out.dim(error.hint), file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(141)
    except subprocess.TimeoutExpired:
        print(f"ytplay: {out.bad('cliamp timed out')}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)

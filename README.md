# ytplay

Hand any YouTube playlist, mix, or video to [cliamp](https://cliamp.stream).

`ytplay` is a thin shell front end for cliamp v2's IPC API. It normalizes
whatever shape of link you paste, then either loads it into the player you
already have open or boots the retro TUI on it.

## Usage

```sh
ytplay 'https://music.youtube.com/playlist?list=PL...'   # load and play
ytplay PLbpi6ZahtOH6Blw3RGYpWkSByi_T7Rygb            # bare playlist id
ytplay 'check this out https://youtu.be/dQw4w9WgXcQ'   # pasted text
ytplay -c                                              # from the clipboard
```

| Flag | Effect |
|------|--------|
| `-c`, `--clip` | read the target from the clipboard (wl-paste, xclip, xsel, pbpaste) |
| `-q`, `--queue` | append without starting playback |
| `--shuffle on\|off` | set shuffle on the running player |
| `--repeat off\|all\|one` | set repeat on the running player |
| `--dry-run` | resolve with yt-dlp and print the track list; load nothing |
| `--json` | print the resolved tracks as JSON |

Accepted links: `youtube.com`, `music.youtube.com`, `m.` and `gaming.` variants,
`youtu.be`, `youtube-nocookie.com`, `/shorts/`, `/live/`, `/embed/`,
`watch?v=…&list=…`, bare playlist ids, bare 11-character video ids, a
`cliamp://play?url=…` link, or any text containing one of the above.
Tracking parameters (`si`, `pp`, `feature`, `t`, …) are stripped before loading.

## Behaviour

- **Player running** (TUI or `--daemon`): loads over the v2 socket with
  `url.load`, which expands the playlist and starts playback when the player is
  idle. Output is a one-line summary plus the first few tracks; a plain single
  line when stdout is not a terminal.
- **Player not running**: `exec`s `cliamp [flags] <url>`, so the same retro
  player opens on that playlist. `--queue` passes `--no-auto-play`.
- **Failure**: cliamp's own resolver message is printed verbatim, with exit 1.
  When the failure looks gated (age, private, members-only) or the playlist id
  is dead, a second line explains what to do.

## Private and gated playlists

cliamp resolves playlists through yt-dlp, so browser cookies work once they
are configured:

```toml
# ~/.config/cliamp/config.toml
[ytmusic]
cookies_from = "chrome"   # firefox, chromium, brave, edge, opera, vivaldi
```

`cliamp setup` writes the same key interactively. cliamp reads it at startup, so
restart the player (TUI or `--daemon`) afterwards. Caveat from cliamp's own
resolver: a bare single video on `youtube.com`/`youtu.be` goes through its
unauthenticated YouTube client, so a gated *single video* can still fail;
playlist URLs are unaffected.

## Requirements

`cliamp` on `PATH` and `yt-dlp` on `PATH` (cliamp shells out to yt-dlp for
all YouTube playback).

## Tests

```sh
python3 ~/.local/share/ytplay/test_ytplay.py
```

Covers target normalization, error formatting, failure hints, and argument
validation. 27 tests, no dependencies.
## Screenshot
The `screenshot.svg` shows cliamp loading a playlist via `ytplay`: the retro TUI with the title bar (`C L I A M P`), the playlist header (`[Playlist] [Shuffle] [Repeat: Off] [1/19]`), numbered tracks with artists and durations (`1. Yes Theory — ... 16:09`), the separator line, EQ bar (`EQ [Custom] ...`), volume (`VOL ██████████░░░ +0dB`), source (`SRC [Radio] 1/2`), and the keybinding bar (`Space=play ?=help ...`).

# ytplay — build / run / deploy

This repo contains the source (`ytplay.py`), tests, screenshot, demo video,
and documentation. No compiled binary is pushed — the file is Python 3 source.

## Build / install (local)
```sh
cp ytplay.py ~/.local/bin/ytplay
chmod +x ~/.local/bin/ytplay
# or run directly:
python3 ytplay.py 'https://music.youtube.com/playlist?list=PL...'
```

## Requirements
- `cliamp` on PATH (v2.0.1+ with v2 IPC)
- `yt-dlp` on PATH (cliamp uses it for YouTube resolution)
- Python 3.14+ (stdlib only — no external dependencies)
- Optional clipboard tools: `wl-paste`, `xclip`, `xsel`, `pbpaste`

## Run tests
```sh
python3 test/test_ytplay.py
```

## Demo video
`demo/screenrecording-2026-10-11_10-44-17.mp4` (1280×720, ~12s, 866 KB) shows cliamp loading a YouTube playlist via `ytplay`. It captures the full desktop; the TUI is visible with the playlist, EQ, volume bar, and keybinding hints.

## Gated / private playlists
If cliamp reports age-gated or private errors (`login required`, `restricted access`), configure cookies in `~/.config/cliamp/config.toml`:
```toml
[ytmusic]
cookies_from = "chrome"   # firefox, brave, edge, opera, vivaldi, safari
```
Then restart the player (`cliamp` or daemon) — the cookie map is read at startup.

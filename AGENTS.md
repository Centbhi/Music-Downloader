# AGENTS.md — musicDownloader

PyQt5 desktop YouTube Music downloader. No tests, lint, CI, or package manager.

## Run
- App entry: `python gui.py` (visible console) — use for dev/debug.
- Prod launcher `run.bat`: `cd` to repo root, sets `QT_MULTIMEDIA_PREFERRED_PLUGINS=windowsmediafoundation`, runs `pythonw.exe gui.py`.
- `gui.py` also sets that env var itself + `app.setStyle("fusion")` + `style.QSS`; frameless (`FramelessWindowHint`) with custom `TitleBar` (min/max/close, drag-move) + `WindowResizeFilter` (L/R/B edges, app-global). Starts normal via `win.show()` (F11/Esc toggles fullscreen).
- Requires: Python 3.12, `ffmpeg` on PATH, Node.js (yt-dlp `js_runtimes: node`), `pip install -r requirements.txt` (`ytmusicapi` optional — search falls back to yt-dlp).

## Architecture
- `gui.py:MainWindow` — 4 tabs (Download/Library/All Songs/Queue) + `PlayerBar`; owns `QSettings("MusicDownloader","MusicDownloader")` for geometry, splitters, column state, sort, player queue/pos/vol/loop.
- `core.py` — all non-UI logic: search, download, m3u, tags, covers, artist cache. Import it; don't duplicate yt-dlp opts.
- `player.py:PlaybackManager/PlayerBar` — `QMediaPlayer` wrapper, loop modes `none/playlist/current`, custom `SeekBar`/`VolumeSlider`.
- `style.py` — color constants + single `QSS` string. `icons.py:make_icon/make_pixmap()` — Material SVG paths rendered via `QSvgRenderer`; add icons there, don't inline SVG. `SongTable.dropEvent` is overridden for manual insert-moves (Qt overwrites OnItem drops) — keep `rowsReordered` wired to the queue sync.
- `tools/ytp.py` — legacy standalone CLI downloader (hardcoded playlist URLs, Podcast branch). Don't refactor into `core.py` unless asked. Resolves repo root via `Path(__file__).parents[1]` so `python tools/ytp.py` works from any cwd.
- `tools/detector.py` — one-off unavailable-video checker (`python tools/detector.py [url]`). Run directly, not imported.

## Data conventions (do not break)
- Paths created on `core` import: `Playlists/Songs/*.mp3`, `Playlists/Podcasts/`, `Playlists/*.m3u`, `.cache/thumbs/`, `.cache/covers/`, `.cache/artists.json`.
- MP3 names: `%(title)s [%(id).6s].mp3` via `sanitize_filename`; display code strips ` [XXXXXX]` suffix with regex — keep 6-char ID.
- `.m3u` files: `utf-8-sig`, first line `#url=<playlist-url>` when known, entries as `Songs/<name>.mp3` with forward slashes. Helpers: `read_m3u/get_playlist_url/persist_playlist_url/add_song_to_playlist/remove_entry_from_playlist/delete_song_everywhere`.
- `archives.txt` = yt-dlp `download_archive`; `core.download_url()` only sets it when `'list=' in url` (single videos skip it). Playlist refresh relies on archive for new-entries-only.
- yt-dlp baseline in `core.OPTIONS`: `bestaudio→mp3 192` + `FFmpegMetadata` + `EmbedThumbnail -c:v mjpeg`, `remote_components: ejs:github`.

## Gotchas
- Windows-only code in `gui.py:MainWindow`: `ctypes.windll` media hotkeys, `nativeEvent` APPCOMMAND handling. Guard any cross-platform change.
- Threads: `SearchWorker/DownloadWorker/TrackMetaWorker` (`QThread`) — never touch widgets directly; emit signals. Cancel via `{'flag': bool}` dict checked in `progress_hook` raising `DownloadCancelled`.
- `core.open_folder` uses `os.startfile` on `nt` (`xdg-open` elsewhere); `thumbnail_path/extract_cover_path` fail soft returning `None`.
- Git-ignored — never commit: `*.m3u *.mp3 *.jpg *.txt .cache/ __pycache__/`. This includes `archives.txt`, `issuesMusic.txt`, and real user playlists in `Playlists/`.

# Youtube Music Downloader

A PyQt5 desktop app to download YouTube playlists and videos as MP3s, browse your
collection, and manage playlists.

## Requirements

- Python 3.12
- ffmpeg on `PATH` (used for audio extraction / thumbnail embedding)
- Node.js (used by yt-dlp for some extractors)
- Python packages:
  - `PyQt5`
  - `yt-dlp`
  - `requests`
  - `mutagen`
  - `ytmusicapi` (optional — used for search; falls back to yt-dlp search)

  Install with `pip install -r requirements.txt`.

## Usage

Run the app:

```
run.bat
```

(or `python gui.py` to launch with a visible console).

### Pin to taskbar / Start menu

`run.bat` can't be pinned directly (Windows would pin the console host
instead). To get a pinnable entry with the same behavior (no console window,
repo root as working directory, green note icon):

```
powershell -ExecutionPolicy Bypass -File install_shortcut.ps1
```

This creates `Music Downloader` shortcuts in the repo folder, on the Desktop,
and in the Start menu (so it's searchable). Then right-click one and choose
`Pin to taskbar` (or drag it there) — that last step is manual, Windows
blocks scripted pinning. Re-run the script after moving the folder or
reinstalling Python, since shortcut paths are absolute. To change the icon,
edit `tools/make_icon.py` and re-run it.

### Download tab
Paste a YouTube URL (single video or playlist) or search by keyword, then press
Download. Songs are saved to `Playlists\Songs\*.mp3`; playlist downloads are
recorded as `.m3u` files in `Playlists\` (with a `#url=` header so they can be
refreshed later). The download archive in `archives.txt` keeps already-downloaded
videos from being fetched again.

### All Songs tab
Every downloaded song in your library. The search box matches both title and
artist. Click a column header to sort (Song / Artist / Date, ascending or
descending). Double-click a row to play it, or right-click to toggle which
playlists it belongs to (Playlists submenu, on/off per playlist without the
menu closing) or delete it from disk.

### Library tab
Your playlists (`Playlists\*.m3u`). Select one to see its songs in the right
pane. **Refresh** re-downloads the playlist from its stored URL; playlists that
have no URL yet will prompt for one once. Refresh rebuilds the `.m3u` from the
YouTube listing, so songs you added manually are dropped. Use the context menu to create,
remove, or add songs to playlists.

### Player bar
Play / pause, previous / next, volume, and the current track's artwork. Clicking
a song anywhere starts playback.

Column widths and the active sort are remembered per tab across sessions.

## tools/detector.py

Use `python tools/detector.py [playlist-url]` to find videos that have become
unavailable, so you can easily identify entries to remove from a playlist.

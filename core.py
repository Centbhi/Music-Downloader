import hashlib
import json
import os
from urllib.parse import quote

import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename

try:
    from mutagen.easyid3 import EasyID3
except ImportError:
    EasyID3 = None

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC
    _HAS_MUTAGEN_ID3 = True
except ImportError:
    _HAS_MUTAGEN_ID3 = False

try:
    from ytmusicapi import YTMusic
    _HAS_YTAPI = True
except ImportError:
    _HAS_YTAPI = False

PLAYLIST_DIR = "Playlists"
MUSIC_DIR = os.path.join(PLAYLIST_DIR, "Songs")
PODCAST_DIR = os.path.join(PLAYLIST_DIR, "Podcasts")
CACHE_DIR = os.path.join(".cache", "thumbs")
COVER_DIR = os.path.join(".cache", "covers")
for _dir in (PLAYLIST_DIR, MUSIC_DIR, PODCAST_DIR, CACHE_DIR, COVER_DIR):
    os.makedirs(_dir, exist_ok=True)

_yt = None


def _get_ytmusic():
    global _yt
    if _yt is None:
        _yt = YTMusic()
    return _yt


class DownloadCancelled(Exception):
    pass


OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': f'{MUSIC_DIR}/%(title)s [%(id).6s].%(ext)s',
    'writethumbnail': True,
    'postprocessors': [
        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192', },
        {'key': 'FFmpegMetadata', },
        {'key': 'EmbedThumbnail', }
    ],
    'postprocessor_args': {
        'EmbedThumbnail': ['-c:v', 'mjpeg']
    },
    'addmetadata': True,
    'replace_in_metadata': {'artist': {', ': '/'}},
    'download_archive': 'archives.txt',
    'js_runtimes': {
        'node': {}
    },
    'playlistend': None,
    'playlist_items': '1-',
    'extract_flat': False,
    'remote_components': ['ejs:github'],
}

OPTIONS2 = {
    'js_runtimes': {
        'node': {}
    },
    'extract_flat': 'in_playlist',
    'playlistend': None,
    'playlist_items': '1-',
    'remote_components': ['ejs:github'],
}

FLAT_OPTS = {
    'quiet': True,
    'skip_download': True,
    'ignoreerrors': True,
    'extract_flat': 'in_playlist',
    'js_runtimes': {
        'node': {}
    },
}


def _make_hook(progress_cb, cancel_flag):
    def hook(d):
        if cancel_flag is not None and cancel_flag.get('flag'):
            raise DownloadCancelled("Download cancelled")
        if progress_cb:
            progress_cb(d)
    return hook


def search_music(query, limit=10):
    if _HAS_YTAPI:
        return _search_ytmusic(query, limit)
    return _search_ytdlp_fallback(query, limit)


def _search_ytmusic(query, limit):
    results = []
    half = max(5, limit)
    for kind in ('songs', 'videos'):
        try:
            data = _get_ytmusic().search(query, filter=kind, limit=half)
        except Exception:
            continue
        for e in data:
            vid = e.get('videoId')
            if not vid:
                continue
            artists = [a.get('name') for a in (e.get('artists') or [])
                       if isinstance(a, dict)]
            album = e.get('album') or {}
            album_name = album.get('name') if isinstance(album, dict) else None
            thumbs = e.get('thumbnails') or []
            results.append({
                'id': vid,
                'title': e.get('title') or 'Unknown',
                'artist': ', '.join(artists) if artists else None,
                'album': album_name,
                'duration': e.get('duration'),
                'kind': 'track' if kind == 'songs' else 'video',
                'url': f"https://music.youtube.com/watch?v={vid}",
                'thumb_url': thumbs[-1]['url'] if thumbs else None,
            })
        if len(results) >= limit:
            break
    return results[:limit]


def _search_ytdlp_fallback(query, limit):
    results = []
    with YoutubeDL(dict(FLAT_OPTS)) as ydl:
        data = ydl.extract_info(
            f"https://music.youtube.com/search?q={quote(query)}",
            download=False)
    for entry in (data.get('entries') or []):
        if not entry:
            continue
        vid = entry.get('id')
        if not vid:
            continue
        results.append({
            'id': vid,
            'title': entry.get('title', 'Unknown title'),
            'artist': None,
            'album': None,
            'duration': None,
            'kind': 'video',
            'url': f"https://music.youtube.com/watch?v={vid}",
            'thumb_url': None,
        })
        if len(results) >= limit:
            break
    return results


def fetch_image_bytes(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.content


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _prune_cache_dir(directory, max_files):
    """Drop the oldest files once a cache dir exceeds max_files.

    Cached thumbs/covers are keyed by content hash, so a deleted or
    re-tagged song orphans its entries forever; a size cap keeps growth
    bounded. Removed entries simply regenerate on next use.
    """
    try:
        files = [os.path.join(directory, n) for n in os.listdir(directory)]
    except OSError:
        return
    files = [p for p in files if os.path.isfile(p)]
    if len(files) <= max_files:
        return
    files.sort(key=_mtime)
    for path in files[:len(files) - max_files]:
        try:
            os.remove(path)
        except OSError:
            pass


def thumbnail_path(url):
    if not url:
        return None
    key = hashlib.md5(url.encode('utf-8')).hexdigest()
    dest = os.path.join(CACHE_DIR, f"{key}.img")
    if not os.path.exists(dest):
        try:
            data = fetch_image_bytes(url)
            with open(dest, "wb") as f:
                f.write(data)
            _prune_cache_dir(CACHE_DIR, 500)
        except Exception:
            return None
    return dest if os.path.exists(dest) else None


def probe_tags(mp3_path):
    if EasyID3 is None:
        return {}
    try:
        tags = EasyID3(mp3_path)
        result = {}
        for key in ('title', 'artist', 'album'):
            if key in tags:
                val = tags[key]
                result[key] = str(val[0]) if val else ''
        return result
    except Exception:
        return {}


def extract_cover_path(mp3_path):
    key = hashlib.md5(
        f"{os.path.abspath(mp3_path)}{os.path.getmtime(mp3_path)}"
        .encode('utf-8')).hexdigest()
    dest = os.path.join(COVER_DIR, f"{key}.jpg")
    if os.path.exists(dest):
        return dest
    if not _HAS_MUTAGEN_ID3:
        return None
    try:
        audio = MP3(mp3_path, ID3=ID3)
        if audio.tags is None:
            return None
        for tag in audio.tags.values():
            if isinstance(tag, APIC):
                with open(dest, 'wb') as f:
                    f.write(tag.data)
                _prune_cache_dir(COVER_DIR, 300)
                return dest
    except Exception:
        pass
    return None


def download_url(url, progress_cb=None, cancel_flag=None):
    opts = dict(OPTIONS)
    opts['progress_hooks'] = [_make_hook(progress_cb, cancel_flag)]

    is_playlist = 'list=' in url

    if not is_playlist:
        opts.pop('download_archive', None)

    with YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)

    if not is_playlist:
        return None

    with YoutubeDL(dict(OPTIONS2)) as ydl:
        playlists = ydl.extract_info(url, download=False, process=False)
        playlist_name = sanitize_filename(
            playlists.get('title') or 'Playlist')

    playlist_path = os.path.join(PLAYLIST_DIR, f"{playlist_name}.m3u")
    with open(playlist_path, "w", encoding="utf-8-sig") as f:
        f.write(f"#url={url}\n")
        for entry in playlists.get('entries'):
            if not entry:
                continue
            safe_name = sanitize_filename(
                f"{entry['title']} [{entry['id'][:6]}]")
            f.write(f"Songs/{safe_name}.mp3\n")
    return playlist_path


def list_playlists():
    result = []
    podcasts = sorted(os.listdir(PODCAST_DIR))
    if podcasts:
        result.append({'name': 'Podcasts', 'path': None,
                       'entries': [f"Podcasts/{p}" for p in podcasts
                                   if p.lower().endswith('.mp3')]})
    for name in sorted(os.listdir(PLAYLIST_DIR)):
        if name.endswith('.m3u'):
            path = os.path.join(PLAYLIST_DIR, name)
            result.append({'name': name, 'path': path,
                           'entries': read_m3u(path)})
    return result


def playlists_for_song(full_path):
    norm = os.path.normpath(full_path)
    result = []
    for p in list_playlists():
        if not p['path']:
            continue
        for entry in p['entries']:
            entry_full = os.path.join(PLAYLIST_DIR, entry.replace('/', os.sep))
            if os.path.normpath(entry_full) == norm:
                result.append(os.path.splitext(p['name'])[0])
                break
    return result


def read_m3u(path):
    entries = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            entries.append(line)
    return entries


def get_playlist_url(playlist_path):
    try:
        with open(playlist_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line.startswith('#url='):
                    return line[len('#url='):]
                if line and not line.startswith('#'):
                    break
    except OSError:
        pass
    return None


def persist_playlist_url(playlist_path, url):
    lines = []
    if os.path.exists(playlist_path):
        with open(playlist_path, encoding="utf-8-sig") as f:
            lines = f.readlines()
    with open(playlist_path, "w", encoding="utf-8-sig") as f:
        f.write(f"#url={url}\n")
        for line in lines:
            if line.strip().startswith('#'):
                continue
            f.write(line)


def _rewrite_m3u_without(playlist_path, entry_path):
    entries = read_m3u(playlist_path)
    if entry_path not in entries:
        return False
    header = []
    with open(playlist_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                header.append(line)
            else:
                break
    with open(playlist_path, "w", encoding="utf-8-sig") as f:
        for line in header:
            f.write(f"{line}\n")
        for line in entries:
            if line != entry_path:
                f.write(f"{line}\n")
    return True


def remove_entry_from_playlist(playlist_path, entry_path):
    """Remove an entry from an .m3u only; keeps the file on disk."""
    if playlist_path is None:
        return False
    return _rewrite_m3u_without(playlist_path, entry_path)


def delete_song_everywhere(entry_path):
    """Delete the mp3 file and strip its entry from every .m3u.

    Returns the list of affected playlist display names (without .m3u).
    """
    full = os.path.join(PLAYLIST_DIR, entry_path.replace('/', os.sep))
    if os.path.exists(full):
        os.remove(full)
    affected = []
    try:
        names = sorted(os.listdir(PLAYLIST_DIR))
    except OSError:
        return affected
    for name in names:
        if not name.endswith('.m3u'):
            continue
        path = os.path.join(PLAYLIST_DIR, name)
        try:
            if _rewrite_m3u_without(path, entry_path):
                affected.append(os.path.splitext(name)[0])
        except OSError:
            continue
    return affected


def open_folder(path):
    path = os.path.abspath(path)
    if os.name == 'nt':
        os.startfile(path)
    else:
        import subprocess
        subprocess.Popen(['xdg-open', path])


def list_all_songs():
    entries = []
    for sub in ('Songs', 'Podcasts'):
        d = os.path.join(PLAYLIST_DIR, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith('.mp3'):
                continue
            full = os.path.join(d, f)
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                mtime = 0
            entries.append({
                'title': os.path.splitext(f)[0],
                'entry': f"{sub}/{f}",
                'full': full,
                'source': sub,
                'mtime': mtime,
            })
    entries.sort(key=lambda e: e['mtime'], reverse=True)
    return entries


ARTIST_CACHE = os.path.join(".cache", "artists.json")


def _read_artist(path):
    if EasyID3 is None:
        return None
    try:
        tags = EasyID3(path)
        artists = tags.get('artist')
        if artists:
            return str(artists[0]).strip() or None
    except Exception:
        pass
    return None


def get_artists(songs):
    cache = {}
    if os.path.exists(ARTIST_CACHE):
        try:
            with open(ARTIST_CACHE, encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    changed = False
    # Entries for deleted files would otherwise live in the cache forever.
    for key in list(cache):
        if not os.path.exists(key):
            del cache[key]
            changed = True
    result = {}
    for s in songs:
        key = os.path.normpath(s['full'])
        mtime = s.get('mtime') or 0
        entry = cache.get(key)
        if entry and entry.get('mtime') == mtime:
            result[key] = entry.get('artist')
            continue
        artist = _read_artist(key)
        cache[key] = {'mtime': mtime, 'artist': artist}
        result[key] = artist
        changed = True
    if changed:
        try:
            os.makedirs(os.path.dirname(ARTIST_CACHE), exist_ok=True)
            with open(ARTIST_CACHE, 'w', encoding='utf-8') as f:
                json.dump(cache, f)
        except Exception:
            pass
    return result


def add_song_to_playlist(playlist_path, entry_path):
    norm = entry_path.replace('/', os.sep)
    entries = read_m3u(playlist_path) if os.path.exists(playlist_path) else []
    if any(e.replace('/', os.sep) == norm for e in entries):
        return False
    with open(playlist_path, "a", encoding="utf-8-sig") as f:
        f.write(f"{entry_path}\n")
    return True


def create_playlist(name):
    safe = sanitize_filename(name.strip() or 'New Playlist')
    path = os.path.join(PLAYLIST_DIR, f"{safe}.m3u")
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8-sig"):
            pass
    return path

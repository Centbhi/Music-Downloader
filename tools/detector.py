import sys
from yt_dlp import YoutubeDL

DEFAULT_URL = "https://music.youtube.com/playlist?list=PLJRxTuFUlT-fvHDuHasztbeRsc35VsDTL"

ydl_opts = {
    "quiet": True,
    "skip_download": True,
    "ignoreerrors": True
}


def main(url=DEFAULT_URL):
    with YoutubeDL(ydl_opts) as ydl:
        data = ydl.extract_info(url, download=False)

        for i, entry in enumerate(data["entries"], start=1):
            if entry is None:
                print(f"[{i}] Unavailable (deleted/private)")
            else:
                title = entry.get("title", "Unknown title")
                print(f"[{i}] OK:", title)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL)

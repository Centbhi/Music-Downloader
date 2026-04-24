from yt_dlp import YoutubeDL

url = "https://music.youtube.com/playlist?list=PLJRxTuFUlT-fvHDuHasztbeRsc35VsDTL"

ydl_opts = {
    "quiet": True,
    "skip_download": True,
    "ignoreerrors": True
}

with YoutubeDL(ydl_opts) as ydl:
    data = ydl.extract_info(url, download=False)

    for i, entry in enumerate(data["entries"], start=1):
        if entry is None:
            print(f"[{i}] Unavailable (deleted/private)")
        else:
            title = entry.get("title", "Unknown title")
            print(f"[{i}] OK:", title)

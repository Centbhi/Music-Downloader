import os
from yt_dlp import YoutubeDL
from yt_dlp.utils import sanitize_filename

PLAYLIST_DIR = "Playlists"
MUSIC_DIR = os.path.join(PLAYLIST_DIR, "Songs") 
os.makedirs(MUSIC_DIR, exist_ok=True)
os.makedirs(PLAYLIST_DIR, exist_ok=True)

options = {
    'format': 'bestaudio/best',
    'outtmpl': f'{MUSIC_DIR}/%(title)s.%(ext)s',
    'writethumbnail': True,
    'postprocessors': [
        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',},
        {'key': 'FFmpegMetadata',},
        {'key': 'EmbedThumbnail',}
    ],
    'postprocessor_args': {
        'EmbedThumbnail': ['-c:v', 'mjpeg']
    },
    'addmetadata': True,
    'replace_in_metadata': {'artist': {', ': '/'}},
    'download_archive': f'archives.txt',  
    'js_runtimes': {
        'node': {}
    },
    'remote_components': ['ejs:github'],
}

options2 = {
    'js_runtimes': {
        'node': {}
    },
    'remote_components': ['ejs:github']
}

url = input("Enter YouTube or YouTube Music URL: ")
if url=="":
    print("yur")
    url = [
        "https://youtube.com/playlist?list=PLJRxTuFUlT-eNwvPz9b6a38hvZOkSzW5q",#Camp of Joy
        "https://youtube.com/playlist?list=PLJRxTuFUlT-fvHDuHasztbeRsc35VsDTL",#Assorted Top Tier
        "https://youtube.com/playlist?list=PLJRxTuFUlT-eFw0g_vRjjyqSqcImhZhi9",#OPMs
        "https://youtube.com/playlist?list=PLJRxTuFUlT-fHc5wcJR-r02WFjkSxX38s",#NIKI!
        "https://youtube.com/playlist?list=PLJRxTuFUlT-emUXerCPGTKdUOUdcG0Lo5",#BINI
        "https://youtube.com/playlist?list=PLJRxTuFUlT-eGYQe8bivC6aJC95kzF_D7",#Live performances that hit diff
        "https://youtube.com/playlist?list=PLJRxTuFUlT-dPX4JHSryQm15E4Nc6gETu",#jog!
        "https://youtube.com/playlist?list=PLJRxTuFUlT-fGcJkJ8ouy4NQQXBaGDDrH",#I'm God
        "https://youtube.com/playlist?list=PLJRxTuFUlT-dY060lmNcf9-aol_wga1jw",#Camp of Joy Live
        "https://youtube.com/playlist?list=PLJRxTuFUlT-exDduaQO7nBFeRZCkkbBl1" #NIKI Live

    ]
    for playlist_url in url:
        with YoutubeDL(options) as ydl:
            result = ydl.extract_info(playlist_url, download=True)

        with YoutubeDL(options2) as ydl:
            playlists = ydl.extract_info(playlist_url, download=False, process=False)
            playlist_name = playlists['title']
        
        playlist_path = os.path.join(PLAYLIST_DIR, f"{playlist_name}.m3u")

        with open(playlist_path, "w", encoding="utf-8-sig") as f:
                for entry in playlists.get('entries'):
                    safe_title = sanitize_filename(entry['title'])
                    f.write(f"Songs/{safe_title}.mp3\n")
else:
    options.pop('download_archive', None)
    options['outtmpl'] = f'{PLAYLIST_DIR}/Podcasts/%(title)s.%(ext)s'
    with YoutubeDL(options) as ydl:
        result = ydl.extract_info(url, download=True)

# Youtube Music Downloader
A tool to download playlists or specific YouTube videos using YTP

## Requirements
Requires ffmpeg on the device.

## Usage

### For downloading playlists
1. Change playlist URL in `ytp.py` to your playlists
2. Run `python ytp.py`
3. Press enter on the prompt
4. On playlist changes, rerun the steps above to update
5. Song Files will appear in `Playlists>Songs` as an `.mp3`, Playlist files will appear in `Playlists` as an `.m3u`
  
### For downloading a specific video
1. Run `python ytp.py`
2. Paste the link of the video on the prompt
3. The file will appear in `Playlists>Podcasts` as an `.mp3`

### detector.py
Use `detector.py` to detect videos that have become unavailable for easier classification of videos to be removed from a playlist

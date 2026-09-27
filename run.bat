@echo off
cd /d "C:\Users\Cent\Desktop\musicDownloader"
set QT_MULTIMEDIA_PREFERRED_PLUGINS=windowsmediafoundation
start "" "C:\Users\Cent\AppData\Local\Programs\Python\Python312\pythonw.exe" gui.py

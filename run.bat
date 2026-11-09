@echo off
cd /d "%~dp0"
set QT_MULTIMEDIA_PREFERRED_PLUGINS=windowsmediafoundation
start "" pythonw gui.py

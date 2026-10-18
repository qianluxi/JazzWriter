@echo off
rem Double-click launcher for the World Studio GUI (worldview forge).
cd /d "%~dp0"
python world_studio_gui.py
if errorlevel 1 (
  echo.
  echo [World Studio] Failed to start. Make sure Python is installed and Tkinter is available.
  echo                 See docs\WorldStudio_*.docx for the beginner guide.
  pause
)

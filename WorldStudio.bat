@echo off
rem Double-click launcher for the World Studio GUI (worldview forge).
cd /d "%~dp0"
python world_studio_gui.py
if errorlevel 1 (
  echo.
  echo [World Studio] 启动失败。请确认已安装 Python，且 Tkinter 可用（见 docs\WorldStudio_新手引导.docx）。
  pause
)

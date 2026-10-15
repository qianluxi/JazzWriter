@echo off
rem Double-click launcher for the JazzWriter GUI.
cd /d "%~dp0"
python gui.py
if errorlevel 1 pause

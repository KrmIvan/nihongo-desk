@echo off
REM Arranca Nihongo Desk desde el codigo fuente (Windows).
cd /d "%~dp0"
start "" .venv\Scripts\pythonw.exe -m nihongo_desk %*

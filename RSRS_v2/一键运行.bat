@echo off
chcp 65001 >nul
cd /d "%~dp0"
python current_advice.py
pause

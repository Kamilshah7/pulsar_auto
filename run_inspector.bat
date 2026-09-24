@echo off
title Labelbox Deep Inspector
cd /d "%~dp0"
echo =======================================================
echo   Starting Labelbox Deep Inspector...
echo =======================================================
python inspect_labelbox.py
pause

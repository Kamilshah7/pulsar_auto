@echo off
title Pulsar Automation Studio (Pre-Label-Independent Acoustic System)
cd /d "%~dp0"
echo =================================================================
echo   Pulsar Automation Studio (Pre-Label-Independent System)
echo   Multi-Stream Acoustic Engine: Whisper + Wav2Vec2 + ForcedAligner
echo =================================================================
echo.
echo Starting FastAPI Web GUI on http://localhost:7860 ...
echo.
python app.py
pause

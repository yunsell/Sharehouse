@echo off
chcp 65001 >nul
title Webcam Tunnel
cd /d "%~dp0"
"%~dp0..\.venv\Scripts\python.exe" tunnel.py
if errorlevel 1 pause

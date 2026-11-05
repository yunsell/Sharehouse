@echo off
chcp 65001 >nul
title Webcam Server
cd /d "%~dp0"
"%~dp0..\.venv\Scripts\python.exe" main.py
if errorlevel 1 pause

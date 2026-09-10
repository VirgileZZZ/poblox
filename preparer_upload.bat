@echo off
chcp 65001 >nul
title poblox - preparer l'upload PythonAnywhere
cd /d "%~dp0"

set "PY="
rem ---- environnement cree par installation.bat en priorite
if exist "%~dp0.venv\Scripts\python.exe" set "PY="%~dp0.venv\Scripts\python.exe""
if not defined PY (py -3 --version >nul 2>&1 && set "PY=py -3")
if not defined PY (python --version >nul 2>&1 && set "PY=python")
if not defined PY (
  echo.
  echo   Python est introuvable. Installe-le depuis https://www.python.org
  echo   en cochant "Add python.exe to PATH", puis lance installation.bat.
  echo.
  pause
  exit /b 1
)

%PY% -u preparer_upload.py
if errorlevel 1 goto fin
echo   Ouverture du dossier...
start "" explorer "%~dp0pythonanywhere"

:fin
pause

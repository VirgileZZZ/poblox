@echo off
chcp 65001 >nul
title poblox - partage (lien Internet)
cd /d "%~dp0"

rem ---- trouve Python (lanceur "py" en priorite, sinon "python")
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

echo.
echo   poblox - creation d'un lien a envoyer a tes amis...
echo.
rem -u : le lien s'affiche tout de suite (sortie non bufferisee)
%PY% -u tunnel.py

echo.
echo   Lien coupe, serveur arrete.
pause

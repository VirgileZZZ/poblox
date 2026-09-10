@echo off
title poblox - serveur local
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

if /i "%~1"=="reseau" goto reseau

rem ================= mode normal : ce PC uniquement =================
echo.
echo   poblox - http://localhost:5000
echo   (Ctrl+C ou fermer cette fenetre pour arreter)
echo.
echo   Astuce : "lancer.bat reseau" pour jouer aussi depuis ton telephone.
echo.
rem ouvre le navigateur une fois les dictionnaires charges (~6 s)
start /min "" cmd /c timeout /t 6 ^>nul ^& explorer http://localhost:5000
%PY% flask_app.py
goto fin

rem ================= mode reseau : PC + telephone du wifi =================
:reseau
echo.
echo   poblox - accessible depuis le wifi local
echo   (Windows peut demander d'autoriser Python sur le reseau : accepte)
echo.
%PY% -c "import socket,flask_app;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('8.8.8.8',80));ip=s.getsockname()[0];s.close();print('   Sur ce PC  : http://localhost:5000');print('   Sur mobile : http://'+ip+':5000');print();flask_app.app.run(host='0.0.0.0',port=5000)"

:fin
echo.
echo   Serveur arrete.
pause

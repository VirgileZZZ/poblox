@echo off
chcp 65001 >nul
title poblox - installation
cd /d "%~dp0"

echo.
echo   ============================================
echo     POBLOX - installation
echo   ============================================
echo.

rem ---- 1) trouve Python (lanceur "py" en priorite, sinon "python")
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (python --version >nul 2>&1 && set "PY=python")
if not defined PY (
  echo   [X] Python est introuvable.
  echo.
  echo       Installe-le depuis https://www.python.org/downloads/
  echo       en cochant bien "Add python.exe to PATH",
  echo       puis relance ce fichier.
  echo.
  pause
  exit /b 1
)
for /f "tokens=*" %%v in ('%PY% --version 2^>^&1') do echo   [1/3] Python trouve : %%v

rem ---- 2) environnement isole (.venv) : n'abime pas ton Python systeme
echo   [2/3] Creation de l'environnement .venv ...
if exist ".venv\Scripts\python.exe" (
  echo         deja present, on le reutilise.
) else (
  %PY% -m venv .venv
  if errorlevel 1 (
    echo.
    echo   [X] Echec de la creation du .venv.
    echo       Sur certaines installations il faut d'abord :
    echo       %PY% -m pip install --user virtualenv
    echo.
    pause
    exit /b 1
  )
)

rem ---- 3) dependances (Flask)
echo   [3/3] Installation des dependances ...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
  echo.
  echo   [X] Echec de l'installation des dependances.
  echo       Verifie ta connexion Internet et relance ce fichier.
  echo.
  pause
  exit /b 1
)

echo.
echo   ============================================
echo     Installation terminee !
echo   ============================================
echo.
echo     lancer.bat            -^> jouer sur ce PC
echo     lancer.bat reseau     -^> jouer aussi depuis le tel du wifi
echo     partager.bat          -^> creer un lien Internet a envoyer
echo     preparer_upload.bat   -^> preparer la mise en ligne
echo.

choice /c ON /n /m "   Lancer le serveur maintenant ? [O/N] "
if errorlevel 2 goto fin
echo.
call "%~dp0lancer.bat"
exit /b 0

:fin
echo.
echo   A bientot. Double-clique sur lancer.bat quand tu veux jouer.
echo.
pause

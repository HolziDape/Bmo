@echo off
title BMO - Ersteinrichtung
color 0A
echo.
echo  ============================================
echo    BMO Freund - Ersteinrichtung (einmalig!)
echo  ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  FEHLER: Python ist nicht installiert!
    echo.
    echo  Bitte Python installieren:
    echo  1. Geh auf https://www.python.org/downloads/
    echo  2. Lade die neueste Version herunter
    echo  3. WICHTIG: Haken setzen bei "Add Python to PATH"
    echo  4. Dann diese Datei nochmal starten
    echo.
    pause
    exit /b 1
)

echo  Python gefunden!
echo.
echo  Installiere benoetigte Pakete...
echo.

pip install flask flask-cors requests psutil mss Pillow winotify

echo.
echo  ============================================
echo    Fertig! Jetzt starten:
echo    -> START_WEB.bat doppelklicken
echo  ============================================
echo.
pause

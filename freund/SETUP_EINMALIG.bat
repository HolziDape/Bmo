@echo off
title BMO - Ersteinrichtung
color 0A
echo.
echo  ============================================
echo    BMO - Ersteinrichtung (einmalig!)
echo  ============================================
echo.

REM Prüfen ob Python installiert ist
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
echo  (Das kann ein paar Minuten dauern - bitte warten!)
echo.

REM Web-Version Pakete
pip install flask flask-cors requests psutil

REM Desktop-Version Pakete (auskommentiert, nur bei Bedarf)
REM pip install numpy sounddevice openwakeword SpeechRecognition pygame soundfile

echo.
echo  ============================================
echo    Fertig! Du kannst jetzt starten:
echo.
echo    Web-Version:     START_WEB.bat
echo    Desktop-Version: START_DESKTOP.bat
echo  ============================================
echo.
pause

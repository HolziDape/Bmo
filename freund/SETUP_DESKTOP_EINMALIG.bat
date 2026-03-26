@echo off
title BMO Desktop - Ersteinrichtung
color 0A
echo.
echo  ============================================
echo    BMO Desktop - Ersteinrichtung (einmalig!)
echo  ============================================
echo.
echo  Installiere Pakete fuer die Desktop-Version...
echo  (Kann 5-10 Minuten dauern - bitte warten!)
echo.

pip install flask flask-cors requests psutil
pip install numpy sounddevice SpeechRecognition pygame soundfile
pip install openwakeword

echo.
echo  ============================================
echo    Fertig! Starte mit: START_DESKTOP.bat
echo  ============================================
echo.
pause

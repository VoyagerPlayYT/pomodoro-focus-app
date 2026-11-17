@echo off
chcp 65001 > nul
title Smart Study and Pomodoro Focus App
echo ========================================================
echo   Smart Study and Pomodoro Focus App
echo ========================================================
echo [INFO] Запуск таймера продуктивности на http://localhost:8007 ...
start http://localhost:8007
python -m uvicorn main:app --host 0.0.0.0 --port 8007
pause

@echo off
title BotX 24/7 Liquidity Sweep & WhatsApp Alert Engine
echo ============================================================
echo   Starting BotX WhatsApp Bridge Server (Port 8090)...
echo ============================================================
start "BotX WhatsApp Server" /min cmd /c "cd /d c:\Botx && node whatsapp_service\server.js"
timeout /t 3 /nobreak >nul

echo ============================================================
echo   Starting 24/7 Liquidity Sweep Strategy Scanner...
echo ============================================================
cd /d c:\Botx
.\.venv\Scripts\python.exe run_liquidity_sweep_bot.py --interval 60
pause

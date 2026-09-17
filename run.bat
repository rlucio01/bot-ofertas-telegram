@echo off
cd /d "%~dp0"
title Bot de Ofertas Telegram
:loop
uv run python -m ofertas run
echo.
echo O bot parou (codigo %errorlevel%). Reiniciando em 15 segundos... (feche a janela para sair)
timeout /t 15 >nul
goto loop

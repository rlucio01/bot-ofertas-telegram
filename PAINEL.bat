@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Bot de Ofertas - Painel de Controle

echo.
echo   ============================================
echo     BOT DE OFERTAS - PAINEL DE CONTROLE
echo   ============================================
echo.

REM 1) Garante que o uv esta instalado
where uv >nul 2>nul
if errorlevel 1 (
  echo   O 'uv' nao esta instalado. Instalando agora...
  winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
  echo.
  echo   ------------------------------------------------------------
  echo   uv instalado! FECHE esta janela e abra o PAINEL.bat de novo.
  echo   ------------------------------------------------------------
  pause
  exit /b
)

REM 2) Instala/atualiza as dependencias (rapido depois da primeira vez)
echo   Preparando o ambiente (pode demorar na primeira vez)...
uv sync
if errorlevel 1 goto erro

REM 3) Abre o painel no navegador
echo.
echo   Abrindo o painel no navegador...
echo   (deixe esta janela aberta enquanto usar o painel)
echo.
uv run python -m ofertas painel
goto fim

:erro
echo.
echo   ============================================================
echo   Algo deu errado ao preparar o ambiente.
echo.
echo   Se apareceu "Failed to spawn: python" ou algo sobre
echo   "Controle de Aplicativo", e o Smart App Control do Windows.
echo   Veja como desligar no arquivo README (secao "Problemas comuns").
echo   ============================================================
echo.

:fim
echo.
echo   Painel encerrado. Pressione uma tecla para sair.
pause >nul

#!/bin/sh
set -e

# Garante a existência da pasta data e permissões
mkdir -p /app/data /app/data/ml_profile

MODE="${APP_MODE:-$1}"

if [ "$MODE" = "painel" ]; then
    echo "=========================================================="
    echo "Iniciando Bot de Ofertas em Modo PAINEL WEB (porta 8481)"
    echo "=========================================================="
    export PAINEL_HOST="${PAINEL_HOST:-0.0.0.0}"
    export PAINEL_PORT="${PAINEL_PORT:-8481}"
    export AUTO_START_BOT="${AUTO_START_BOT:-true}"
    export NO_BROWSER="true"
    exec python -m ofertas painel
elif [ "$MODE" = "run" ] || [ -z "$MODE" ]; then
    echo "=========================================================="
    echo "Iniciando Bot de Ofertas em Modo BOT DAEMON 24x7"
    echo "=========================================================="
    exec python -m ofertas run
else
    # Permite executar comandos arbitrários, ex: python -m ofertas check
    exec "$@"
fi

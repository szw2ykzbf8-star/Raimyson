#!/bin/bash
# Inicia o bot Telegram em background e o Streamlit em foreground.
# Usado pelo Railway (e qualquer PaaS com suporte a bash).
set -e

echo "[start.sh] Iniciando FinTrack Bot em background..."
python bot.py &

echo "[start.sh] Iniciando Streamlit na porta $PORT..."
exec python -m streamlit run main.py \
    --server.port="$PORT" \
    --server.address=0.0.0.0 \
    --server.headless=true

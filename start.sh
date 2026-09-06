#!/bin/bash
# Inicia o bot Telegram em background (com reinício automático) e o Streamlit em foreground.
set -e

_bot_loop() {
    while true; do
        echo "[start.sh] Iniciando bot..."
        python bot.py || true
        echo "[start.sh] Bot encerrou — reiniciando em 5s..."
        sleep 5
    done
}

_bot_loop &

echo "[start.sh] Iniciando Streamlit na porta $PORT..."
exec python -m streamlit run main.py \
    --server.port="$PORT" \
    --server.address=0.0.0.0 \
    --server.headless=true

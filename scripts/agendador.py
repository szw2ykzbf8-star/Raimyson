"""
Agendador de tarefas do FinTrack.
Roda em background junto com o bot e o Streamlit (via start.sh).

Tarefas:
  - 05:00 BRT (08:00 UTC) → backup diário enviado ao Telegram
"""
import os
import subprocess
import sys
import time

import schedule

# Garante que o diretório raiz do projeto esteja no path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def _run_backup():
    print("[agendador] Disparando backup diário...", flush=True)
    subprocess.run([sys.executable, "scripts/backup_diario.py"])


# 05:00 BRT = 08:00 UTC
schedule.every().day.at("08:00").do(_run_backup)

print("[agendador] Iniciado — backup diário às 05:00 BRT (08:00 UTC)", flush=True)

while True:
    schedule.run_pending()
    time.sleep(60)

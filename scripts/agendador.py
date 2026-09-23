"""
Agendador de tarefas do FinTrack.
Roda em background junto com o bot e o Streamlit (via start.sh).

Tarefas:
  - 05:00 BRT (08:00 UTC) → backup diário no Google Drive
  - 05:05 BRT (08:05 UTC) → atualização automática da taxa CDI (BCB)
  - 06:05 BRT (09:05 UTC) → relatório PDF mensal (apenas no dia 1)
  - 08:30 BRT (11:30 UTC) → alertas de vencimento (fixas e cartões)
"""
import os
import subprocess
import sys
import time
from datetime import date

import schedule

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def _run(script: str, label: str):
    print(f"[agendador] Disparando {label}...", flush=True)
    subprocess.run([sys.executable, script])


def _run_backup():
    _run("scripts/backup_diario.py", "backup diário")


def _run_cdi():
    _run("scripts/cdi_updater.py", "atualização CDI")


def _run_alertas():
    _run("scripts/alertas_vencimento.py", "alertas de vencimento")


def _run_relatorio():
    if date.today().day == 1:
        _run("scripts/relatorio_mensal.py", "relatório mensal")
    else:
        print("[agendador] Relatório mensal: não é dia 1 — pulando.", flush=True)


# 08:00 UTC = 05:00 BRT
schedule.every().day.at("08:00").do(_run_backup)

# 08:05 UTC = 05:05 BRT
schedule.every().day.at("08:05").do(_run_cdi)

# 09:05 UTC = 06:05 BRT — apenas executa no dia 1
schedule.every().day.at("09:05").do(_run_relatorio)

# 11:30 UTC = 08:30 BRT
schedule.every().day.at("11:30").do(_run_alertas)

print(
    "[agendador] Iniciado:\n"
    "  05:00 BRT → backup diário\n"
    "  05:05 BRT → atualização CDI\n"
    "  06:05 BRT → relatório mensal (dia 1)\n"
    "  08:30 BRT → alertas de vencimento",
    flush=True,
)

while True:
    schedule.run_pending()
    time.sleep(60)

"""
Backup diário do FinTrack — exporta todas as abas do Google Sheets
e envia o JSON para o Telegram como arquivo.

Executado pelo agendador.py às 05:00 BRT (08:00 UTC).
Pode ser rodado manualmente: python scripts/backup_diario.py
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import gspread
import requests
from google.oauth2.service_account import Credentials
from src.config import (
    GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON,
    SPREADSHEET_ID, SHEETS, CFG_CHAVES_SENSIVEIS,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_BRT    = timezone(timedelta(hours=-3))


def _get_client():
    if GOOGLE_CREDENTIALS_JSON:
        info  = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES)
    return gspread.authorize(creds)


def _enviar_telegram(conteudo: bytes, nome_arquivo: str, legenda: str) -> tuple[bool, str]:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não configurado"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": legenda, "parse_mode": "HTML"},
            files={"document": (nome_arquivo, conteudo, "application/json")},
            timeout=30,
        )
        if resp.status_code == 200:
            return True, ""
        return False, f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)


def main():
    agora        = datetime.now(_BRT)
    timestamp    = agora.strftime("%Y-%m-%d_%H-%M")
    nome_arquivo = f"fintrack_backup_{timestamp}.json"

    print(f"[backup] Iniciando às {agora.strftime('%d/%m/%Y %H:%M')} BRT...")

    try:
        sp = _get_client().open_by_key(SPREADSHEET_ID)
    except Exception as e:
        print(f"[backup] ERRO ao conectar ao Sheets: {e}")
        sys.exit(1)

    backup = {}
    for key, sheet_name in SHEETS.items():
        try:
            records = sp.worksheet(sheet_name).get_all_records()
            if key == "config":
                records = [r for r in records if r.get("chave") not in CFG_CHAVES_SENSIVEIS]
            backup[key] = records
            print(f"[backup] ✓ {sheet_name}: {len(records)} registros")
        except gspread.exceptions.WorksheetNotFound:
            backup[key] = []
            print(f"[backup] ⚠ {sheet_name}: aba não encontrada (ignorada)")
        except Exception as e:
            backup[key] = []
            print(f"[backup] ✗ {sheet_name}: {e}")

    total         = sum(len(v) for v in backup.values())
    backup_bytes  = json.dumps(backup, ensure_ascii=False, indent=2).encode("utf-8")

    legenda = (
        f"💾 <b>FinTrack — Backup Diário</b>\n"
        f"📅 {agora.strftime('%d/%m/%Y às %H:%M')} BRT\n"
        f"📊 {total} registros exportados\n"
        f"🔒 PINs e tokens NÃO incluídos"
    )

    ok, err = _enviar_telegram(backup_bytes, nome_arquivo, legenda)
    if ok:
        print(f"[backup] ✅ Enviado via Telegram: {nome_arquivo}")
    else:
        print(f"[backup] ❌ Falha no Telegram: {err}")
        # Salva localmente como fallback
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write(json.dumps(backup, ensure_ascii=False, indent=2))
        print(f"[backup] 💾 Salvo localmente: {nome_arquivo}")


if __name__ == "__main__":
    main()

"""
Backup diário do FinTrack — exporta todas as abas do Google Sheets
e salva o JSON no Google Drive (pasta configurada via BACKUP_DRIVE_FOLDER_ID).

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
import google.auth.transport.requests as g_requests
from src.config import (
    GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON,
    SPREADSHEET_ID, SHEETS, CFG_CHAVES_SENSIVEIS,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
_BRT             = timezone(timedelta(hours=-3))
_DRIVE_FOLDER_ID = os.getenv("BACKUP_DRIVE_FOLDER_ID", "")


def _get_creds():
    if GOOGLE_CREDENTIALS_JSON:
        info  = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES)
    return creds


def _upload_drive(creds, conteudo: bytes, nome_arquivo: str) -> tuple[bool, str]:
    """Faz upload do arquivo para a pasta do Google Drive via REST API."""
    creds.refresh(g_requests.Request())
    token = creds.token

    metadata = {"name": nome_arquivo}
    if _DRIVE_FOLDER_ID:
        metadata["parents"] = [_DRIVE_FOLDER_ID]

    resp = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers={"Authorization": f"Bearer {token}"},
        files={
            "metadata": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
            "file":     (nome_arquivo, conteudo, "application/json"),
        },
        timeout=60,
    )
    if resp.status_code in (200, 201):
        file_id = resp.json().get("id", "")
        return True, file_id
    return False, f"HTTP {resp.status_code}: {resp.text}"


def _enviar_telegram_fallback(conteudo: bytes, nome_arquivo: str, motivo: str) -> None:
    """Envia via Telegram apenas se o Drive falhar e o Telegram estiver configurado."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    legenda = (
        f"⚠️ <b>Backup via Telegram (fallback)</b>\n"
        f"Drive indisponível: {motivo}\n"
        f"📎 {nome_arquivo}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": legenda, "parse_mode": "HTML"},
            files={"document": (nome_arquivo, conteudo, "application/json")},
            timeout=30,
        )
    except Exception as e:
        print(f"[backup] Telegram fallback também falhou: {e}")


def main():
    agora        = datetime.now(_BRT)
    timestamp    = agora.strftime("%Y-%m-%d_%H-%M")
    nome_arquivo = f"fintrack_backup_{timestamp}.json"

    print(f"[backup] Iniciando às {agora.strftime('%d/%m/%Y %H:%M')} BRT...", flush=True)

    try:
        creds = _get_creds()
        sp    = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
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

    total        = sum(len(v) for v in backup.values())
    backup_bytes = json.dumps(backup, ensure_ascii=False, indent=2).encode("utf-8")

    print(f"[backup] Total: {total} registros — {len(backup_bytes)/1024:.1f} KB")

    if not _DRIVE_FOLDER_ID:
        print("[backup] ⚠ BACKUP_DRIVE_FOLDER_ID não configurado — pulando upload para Drive")
        _enviar_telegram_fallback(backup_bytes, nome_arquivo, "BACKUP_DRIVE_FOLDER_ID não definido")
        return

    ok, resultado = _upload_drive(creds, backup_bytes, nome_arquivo)
    if ok:
        print(f"[backup] ✅ Salvo no Google Drive: {nome_arquivo} (id={resultado})")
    else:
        print(f"[backup] ❌ Falha no Drive: {resultado}")
        _enviar_telegram_fallback(backup_bytes, nome_arquivo, resultado)


if __name__ == "__main__":
    main()

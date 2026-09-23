"""
Busca a taxa CDI/Selic atual na API do Banco Central do Brasil
e atualiza a config 'cdi_anual' no Google Sheets automaticamente.

API: api.bcb.gov.br — Série 12 (CDI diário, % ao dia)
Taxa anual = ((1 + cdi_dia/100)^252 - 1) * 100
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests
import gspread
from google.oauth2.service_account import Credentials
from src.config import (
    GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_BCB_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados/ultimos/1?formato=json"


def _get_sp():
    if GOOGLE_CREDENTIALS_JSON:
        info  = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


def _set_config(sp, chave: str, valor: str):
    ws   = sp.worksheet("config")
    rows = ws.get_all_records()
    for i, row in enumerate(rows, start=2):
        if str(row.get("chave", "")) == chave:
            ws.update_cell(i, 2, valor)
            return
    ws.append_row([chave, valor])


def main():
    print("[cdi] Consultando API do Banco Central...", flush=True)
    try:
        resp = requests.get(_BCB_URL, timeout=15)
        data = resp.json()
        cdi_dia = float(data[0]["valor"])
        data_ref = data[0]["data"]
    except Exception as e:
        print(f"[cdi] Falha ao buscar CDI: {e}")
        return

    cdi_anual = round(((1 + cdi_dia / 100) ** 252 - 1) * 100, 4)
    print(f"[cdi] CDI diário em {data_ref}: {cdi_dia:.6f}% → anual: {cdi_anual:.2f}%")

    try:
        sp = _get_sp()
        _set_config(sp, "cdi_anual", str(cdi_anual))
        print(f"[cdi] ✅ cdi_anual atualizado para {cdi_anual:.2f}%")
    except Exception as e:
        print(f"[cdi] Falha ao salvar no Sheets: {e}")


if __name__ == "__main__":
    main()

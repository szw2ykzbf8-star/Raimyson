"""
Verifica contas fixas e cartões com vencimento nos próximos dias
e envia alerta consolidado via Telegram.

Executado diariamente pelo agendador (11:30 BRT / 14:30 UTC).
"""
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests
import gspread
from google.oauth2.service_account import Credentials
from src.config import (
    GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SHEETS,
)

_SCOPES   = ["https://www.googleapis.com/auth/spreadsheets"]
_DIAS_AVISO = 3


def _get_sp():
    if GOOGLE_CREDENTIALS_JSON:
        info  = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


def _get_rows(sp, sheet_name: str) -> list[dict]:
    try:
        return sp.worksheet(sheet_name).get_all_records()
    except Exception:
        return []


def _send(mensagem: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[alertas] Telegram não configurado — mensagem:\n{mensagem}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[alertas] Falha ao enviar Telegram: {e}")


def main():
    hoje    = date.today()
    limite  = hoje + timedelta(days=_DIAS_AVISO)
    alertas = []

    try:
        sp = _get_sp()
    except Exception as e:
        print(f"[alertas] Erro ao conectar: {e}")
        return

    # ── Contas Fixas ────────────────────────────────────────────────────
    for row in _get_rows(sp, SHEETS["fixas"]):
        if str(row.get("ativo", "")).lower() != "true":
            continue
        try:
            dia_venc = int(row.get("dia_vencimento") or 0)
        except (ValueError, TypeError):
            continue
        if not dia_venc:
            continue

        # Determina a data de vencimento deste mês (ou próximo mês se já passou)
        try:
            data_venc = date(hoje.year, hoje.month, dia_venc)
        except ValueError:
            continue
        if data_venc < hoje:
            # Vencimento já passou neste mês — próximo mês
            mes_prox = hoje.month % 12 + 1
            ano_prox = hoje.year + (1 if mes_prox == 1 else 0)
            try:
                data_venc = date(ano_prox, mes_prox, dia_venc)
            except ValueError:
                continue

        dias_faltam = (data_venc - hoje).days
        if 0 <= dias_faltam <= _DIAS_AVISO:
            valor = float(row.get("valor_referencia") or 0)
            nome  = row.get("nome", "—")
            emoji = "🔴" if dias_faltam == 0 else ("⚠️" if dias_faltam <= 1 else "📅")
            txt   = f"Hoje" if dias_faltam == 0 else f"em {dias_faltam} dia(s)"
            alertas.append(f"{emoji} <b>{nome}</b> — R$ {valor:,.2f} — vence <b>{txt}</b> (dia {dia_venc})")

    # ── Cartões de Crédito ───────────────────────────────────────────────
    for row in _get_rows(sp, SHEETS["cartoes"]):
        if str(row.get("ativo", "")).lower() != "true":
            continue
        try:
            dia_venc = int(row.get("dia_vencimento") or 0)
        except (ValueError, TypeError):
            continue
        if not dia_venc:
            continue

        try:
            data_venc = date(hoje.year, hoje.month, dia_venc)
        except ValueError:
            continue
        if data_venc < hoje:
            mes_prox = hoje.month % 12 + 1
            ano_prox = hoje.year + (1 if mes_prox == 1 else 0)
            try:
                data_venc = date(ano_prox, mes_prox, dia_venc)
            except ValueError:
                continue

        dias_faltam = (data_venc - hoje).days
        if 0 <= dias_faltam <= _DIAS_AVISO:
            nome  = row.get("nome", "—")
            emoji = "🔴" if dias_faltam == 0 else ("⚠️" if dias_faltam <= 1 else "💳")
            txt   = "Hoje" if dias_faltam == 0 else f"em {dias_faltam} dia(s)"
            alertas.append(f"{emoji} <b>Fatura {nome}</b> — vence <b>{txt}</b> (dia {dia_venc})")

    # ── Enviar ──────────────────────────────────────────────────────────
    if not alertas:
        print(f"[alertas] Nenhum vencimento nos próximos {_DIAS_AVISO} dias.")
        return

    linhas   = "\n".join(alertas)
    mensagem = (
        f"🔔 <b>FinTrack — Alertas de Vencimento</b>\n\n"
        f"{linhas}\n\n"
        f"<i>Acesse o app para pagar: /link</i>"
    )
    _send(mensagem)
    print(f"[alertas] ✅ {len(alertas)} alerta(s) enviado(s) via Telegram.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
FinTrack Telegram Bot — polling loop independente do Streamlit.

Comandos suportados:
  /gasto <valor> <cat> <descrição> <forma> [conta] [Nx]
  /entrada <valor> <fonte> [conta]
  /saldo
  /resumo
  /ajuda

Formas de pagamento: pix · db (débito) · cr (crédito) · din (dinheiro)
Categorias:         ali · trans · mor · sau · laz · edu · vest · com · div · inv · out
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

import requests
import gspread
from google.oauth2.service_account import Credentials

# ─── Configuração ─────────────────────────────────────────────────────────────

TOKEN       = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID     = str(os.getenv("TELEGRAM_CHAT_ID", ""))
CREDS_PATH  = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
CREDS_JSON  = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
SHEET_ID    = os.getenv("SPREADSHEET_ID", "")
SCOPES      = ["https://www.googleapis.com/auth/spreadsheets"]

# Abreviações de categoria → nome completo (igual às categorias do app)
CAT_ABBREV = {
    "ali":   "Alimentação",
    "trans": "Transporte",
    "mor":   "Moradia",
    "sau":   "Saúde",
    "laz":   "Lazer",
    "edu":   "Educação",
    "vest":  "Vestuário",
    "com":   "Comunicação",
    "div":   "Dívidas",
    "inv":   "Investimentos",
    "out":   "Outros",
}

# Abreviações de forma de pagamento → nome completo
FORMAS = {
    "pix": "Pix",
    "db":  "Débito",
    "din": "Dinheiro",
    "cr":  "Crédito",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fintrack-bot")

# ─── Conexão com Google Sheets ────────────────────────────────────────────────

_gc_client = None
_spread    = None


def _get_gc():
    global _gc_client
    if _gc_client is None:
        if CREDS_JSON:
            info  = json.loads(CREDS_JSON)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
        _gc_client = gspread.authorize(creds)
    return _gc_client


def _ws(tab: str) -> gspread.Worksheet:
    global _spread
    try:
        if _spread is None:
            _spread = _get_gc().open_by_key(SHEET_ID)
        return _spread.worksheet(tab)
    except Exception:
        # Reconecta em caso de timeout ou token expirado
        _spread = None
        _spread = _get_gc().open_by_key(SHEET_ID)
        return _spread.worksheet(tab)


def _get_all(tab: str) -> list[dict]:
    return _ws(tab).get_all_records(numericise_ignore=["all"])


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


def _mes_atual() -> str:
    return datetime.now().strftime("%Y-%m")


# ─── Telegram ─────────────────────────────────────────────────────────────────


def _tg(method: str, _req_timeout: int = 15, **kwargs) -> dict:
    url  = f"https://api.telegram.org/bot{TOKEN}/{method}"
    resp = requests.post(url, json=kwargs, timeout=_req_timeout)
    return resp.json()


def send(text: str, chat_id: str = None) -> None:
    dest = chat_id or CHAT_ID
    if not dest or not TOKEN:
        return
    _tg("sendMessage", chat_id=dest, text=text, parse_mode="HTML")


# ─── Formatação ───────────────────────────────────────────────────────────────


def _fmt(v: float) -> str:
    """Formata valor em reais: 1234.5 → R$ 1.234,50"""
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ─── Parsers de comando ───────────────────────────────────────────────────────


def _parse_gasto(parts: list[str]) -> dict | str:
    """
    Formato: <valor> <cat> <descrição...> <forma> [conta] [Nx]
    Retorna dict com os campos ou string de erro.
    """
    if len(parts) < 3:
        return (
            "Formato:\n"
            "<code>/gasto valor cat descrição forma [conta] [Nx]</code>\n\n"
            "Ex: <code>/gasto 45.50 ali mercado pix</code>\n"
            "Ex: <code>/gasto 600 vest tênis cr nubank 3x</code>"
        )

    # valor
    try:
        valor = float(parts[0].replace(",", "."))
    except ValueError:
        return f"❌ Valor inválido: <code>{parts[0]}</code>"

    if valor <= 0:
        return "❌ O valor deve ser maior que zero."

    # categoria
    cat_key   = parts[1].lower()
    categoria = CAT_ABBREV.get(cat_key)
    if not categoria:
        cats = " · ".join(f"<code>{k}</code>={v}" for k, v in CAT_ABBREV.items())
        return f"❌ Categoria '<code>{cat_key}</code>' desconhecida.\n\nOpções:\n{cats}"

    remaining = parts[2:]

    # parcelas — último token no formato "Nx" ou "nx"
    parcelas = 1
    if remaining:
        last = remaining[-1].lower()
        if last.endswith("x") and last[:-1].isdigit():
            parcelas  = int(last[:-1])
            remaining = remaining[:-1]
            if parcelas < 1:
                return "❌ Número de parcelas deve ser maior que zero."

    # forma de pagamento — busca da direita para a esquerda
    forma_key = None
    forma_idx = None
    for i in range(len(remaining) - 1, -1, -1):
        if remaining[i].lower() in FORMAS:
            forma_key = remaining[i].lower()
            forma_idx = i
            break

    if forma_key is None:
        formas = " · ".join(f"<code>{k}</code>={v}" for k, v in FORMAS.items())
        return f"❌ Forma de pagamento não encontrada.\n\nOpções: {formas}"

    forma = FORMAS[forma_key]
    desc  = " ".join(remaining[:forma_idx]).strip()
    conta = " ".join(remaining[forma_idx + 1:]).strip()

    if not desc:
        return "❌ Informe uma descrição para o gasto."

    return {
        "valor":     valor,
        "categoria": categoria,
        "descricao": desc,
        "forma":     forma,
        "conta":     conta,
        "parcelas":  parcelas,
    }


def _parse_entrada(parts: list[str]) -> dict | str:
    """
    Formato: <valor> <fonte> [conta]
    """
    if len(parts) < 2:
        return (
            "Formato:\n"
            "<code>/entrada valor fonte [conta]</code>\n\n"
            "Ex: <code>/entrada 3000 Salário nubank</code>"
        )

    try:
        valor = float(parts[0].replace(",", "."))
    except ValueError:
        return f"❌ Valor inválido: <code>{parts[0]}</code>"

    if valor <= 0:
        return "❌ O valor deve ser maior que zero."

    fonte = parts[1]
    conta = " ".join(parts[2:]).strip()

    return {"valor": valor, "fonte": fonte, "conta": conta}


# ─── Handlers de comando ──────────────────────────────────────────────────────


def cmd_gasto(parts: list[str]) -> str:
    parsed = _parse_gasto(parts)
    if isinstance(parsed, str):
        return parsed

    valor     = parsed["valor"]
    categoria = parsed["categoria"]
    desc      = parsed["descricao"]
    forma     = parsed["forma"]
    conta     = parsed["conta"] or "—"
    parcelas  = parsed["parcelas"]
    hoje      = datetime.now().strftime("%Y-%m-%d")
    mes       = datetime.now().strftime("%Y-%m")

    valor_parcela = round(valor / parcelas, 2)
    id_grupo = _new_id()
    ws = _ws("gastos")

    for i in range(1, parcelas + 1):
        ws.append_row([
            _new_id(), id_grupo, hoje, hoje, mes,
            str(i), str(parcelas),
            str(valor_parcela), str(valor),
            categoria, forma, conta, desc, _now(),
        ])

    if parcelas > 1:
        return (
            f"✅ <b>Gasto registrado</b>\n\n"
            f"💸 {_fmt(valor)} em {parcelas}x de {_fmt(valor_parcela)}\n"
            f"📂 {categoria}\n"
            f"💳 {forma} — {conta}\n"
            f"📝 {desc}"
        )
    return (
        f"✅ <b>Gasto registrado</b>\n\n"
        f"💸 {_fmt(valor)}\n"
        f"📂 {categoria}\n"
        f"💳 {forma} — {conta}\n"
        f"📝 {desc}"
    )


def cmd_entrada(parts: list[str]) -> str:
    parsed = _parse_entrada(parts)
    if isinstance(parsed, str):
        return parsed

    valor = parsed["valor"]
    fonte = parsed["fonte"]
    conta = parsed["conta"] or "—"
    hoje  = datetime.now().strftime("%Y-%m-%d")

    ws  = _ws("entradas")
    rid = _new_id()
    ws.append_row([rid, hoje, str(valor), fonte, conta, "", _now()])

    return (
        f"✅ <b>Entrada registrada</b>\n\n"
        f"💰 {_fmt(valor)}\n"
        f"📌 {fonte}\n"
        f"🏦 {conta}"
    )


def cmd_saldo(_: list[str]) -> str:
    mes = _mes_atual()

    entradas_rows = _get_all("entradas")
    gastos_rows   = _get_all("gastos")

    total_ent = sum(
        float(r.get("valor", 0) or 0)
        for r in entradas_rows
        if str(r.get("data", "")).startswith(mes)
    )
    total_gas = sum(
        float(r.get("valor_parcela", 0) or 0)
        for r in gastos_rows
        if str(r.get("mes_referencia", "")).startswith(mes)
    )
    saldo = total_ent - total_gas
    emoji = "✅" if saldo >= 0 else "❌"

    return (
        f"📊 <b>Saldo — {mes}</b>\n\n"
        f"💰 Entradas: {_fmt(total_ent)}\n"
        f"💸 Gastos:   {_fmt(total_gas)}\n"
        f"📈 Saldo:    {_fmt(saldo)} {emoji}"
    )


def cmd_resumo(_: list[str]) -> str:
    mes         = _mes_atual()
    gastos_rows = _get_all("gastos")

    por_cat: dict[str, float] = {}
    for r in gastos_rows:
        if str(r.get("mes_referencia", "")).startswith(mes):
            cat         = r.get("categoria", "Outros")
            por_cat[cat] = por_cat.get(cat, 0) + float(r.get("valor_parcela", 0) or 0)

    if not por_cat:
        return f"📋 Sem gastos registrados em {mes}."

    total  = sum(por_cat.values())
    linhas = [f"📋 <b>Resumo — {mes}</b>\n"]
    for cat, val in sorted(por_cat.items(), key=lambda x: -x[1]):
        pct = int(val / total * 100)
        linhas.append(f"  {cat}: {_fmt(val)} ({pct}%)")
    linhas.append(f"\n💸 <b>Total: {_fmt(total)}</b>")
    return "\n".join(linhas)


def cmd_ajuda(_: list[str]) -> str:
    cats  = " · ".join(f"<code>{k}</code>" for k in CAT_ABBREV)
    formas = " · ".join(
        f"<code>{k}</code>={v}" for k, v in FORMAS.items()
    )
    return (
        "🤖 <b>FinTrack Bot — Comandos</b>\n\n"
        "<b>💸 Registrar gasto:</b>\n"
        "<code>/gasto valor cat descrição forma [conta] [Nx]</code>\n"
        "  <code>/gasto 45.50 ali mercado pix</code>\n"
        "  <code>/gasto 80 trans uber db nubank</code>\n"
        "  <code>/gasto 600 vest tênis cr nubank 3x</code>\n\n"
        f"<b>Categorias:</b> {cats}\n\n"
        f"<b>Formas de pagamento:</b> {formas}\n\n"
        "<b>💰 Registrar entrada:</b>\n"
        "<code>/entrada valor fonte [conta]</code>\n"
        "  <code>/entrada 3000 Salário nubank</code>\n\n"
        "<b>📊 Consultas:</b>\n"
        "<code>/saldo</code>  — saldo do mês atual\n"
        "<code>/resumo</code> — gastos por categoria"
    )


COMMANDS: dict[str, callable] = {
    "/gasto":   cmd_gasto,
    "/entrada": cmd_entrada,
    "/saldo":   cmd_saldo,
    "/resumo":  cmd_resumo,
    "/ajuda":   cmd_ajuda,
    "/help":    cmd_ajuda,
    "/start":   cmd_ajuda,
}

# ─── Loop principal ───────────────────────────────────────────────────────────


def handle_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    # Verifica autorização pelo chat_id
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if CHAT_ID and chat_id != CHAT_ID:
        log.warning("Mensagem de chat_id não autorizado: %s", chat_id)
        return

    text = (msg.get("text") or "").strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd   = parts[0].split("@")[0].lower()  # remove @BotName se presente
    args  = parts[1:]

    handler = COMMANDS.get(cmd)
    if handler is None:
        return

    log.info("Comando recebido: %s %s", cmd, args)
    try:
        reply = handler(args)
    except Exception as exc:
        log.exception("Erro ao processar %s", cmd)
        reply = f"❌ Erro interno ao processar o comando.\n<code>{exc}</code>"

    send(reply, chat_id=chat_id)


def run() -> None:
    if not TOKEN:
        log.error("TELEGRAM_TOKEN não configurado — bot não iniciado.")
        return
    if not SHEET_ID:
        log.error("SPREADSHEET_ID não configurado — bot não iniciado.")
        return

    log.info("FinTrack Bot iniciado. Polling...")
    offset = 0
    while True:
        try:
            data = _tg(
                "getUpdates",
                _req_timeout=25,
                offset=offset,
                timeout=20,
                allowed_updates=["message"],
            )
            for upd in data.get("result", []):
                handle_update(upd)
                offset = upd["update_id"] + 1
        except Exception as exc:
            log.warning("Erro no polling: %s — aguardando 5s...", exc)
            time.sleep(5)


if __name__ == "__main__":
    run()

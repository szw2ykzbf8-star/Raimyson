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
Categorias:         dinâmicas — use /ajuda para ver as disponíveis
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

import requests
import gspread
from google.oauth2.service_account import Credentials

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None

# ─── Configuração ─────────────────────────────────────────────────────────────

TOKEN           = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID         = str(os.getenv("TELEGRAM_CHAT_ID", ""))
CREDS_PATH      = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
CREDS_JSON      = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
SHEET_ID        = os.getenv("SPREADSHEET_ID", "")
APP_URL         = os.getenv("APP_URL", "")
ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
SCOPES      = ["https://www.googleapis.com/auth/spreadsheets"]

# Abreviações fixas (base) — retrocompatibilidade com comandos já usados
_CAT_BASE = {
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

CAT_ABBREV: dict[str, str] = dict(_CAT_BASE)
_cat_refresh_ts: float = 0.0
_CAT_TTL = 300  # segundos


def _norm(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if unicodedata.category(c) != "Mn"
    )


def _build_abbrev(nomes: list[str]) -> dict[str, str]:
    result  = dict(_CAT_BASE)
    covered = set(result.values())
    for cat in sorted(nomes):
        if cat in covered:
            continue
        base = _norm(cat)
        for n in range(3, len(base) + 1):
            key = base[:n]
            if key not in result:
                result[key] = cat
                covered.add(cat)
                break
    return result


def _refresh_cats(force: bool = False) -> None:
    global CAT_ABBREV, _cat_refresh_ts
    if not force and time.time() - _cat_refresh_ts < _CAT_TTL:
        return
    try:
        rows  = _get_all("categorias")
        nomes = [r["nome"] for r in rows if str(r.get("ativo", "")).lower() == "true" and r.get("nome")]
        CAT_ABBREV = _build_abbrev(nomes)
        _cat_refresh_ts = time.time()
        log.info("Categorias atualizadas: %d categorias", len(nomes))
    except Exception as exc:
        log.warning("Não foi possível atualizar categorias: %s", exc)

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
        cat_norm = _norm(cat_key)
        for nome in CAT_ABBREV.values():
            if _norm(nome) == cat_norm:
                categoria = nome
                break
    if not categoria and len(cat_key) >= 3:
        cat_norm = _norm(cat_key)
        for nome in CAT_ABBREV.values():
            if _norm(nome).startswith(cat_norm):
                categoria = nome
                break
    if not categoria:
        cats = "\n".join(f"  <code>{k}</code> = {v}" for k, v in sorted(CAT_ABBREV.items(), key=lambda x: x[1]))
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
    conta_raw = parsed["conta"]
    conta     = conta_raw or _get_config("bot_conta_padrao", "") or "—"
    parcelas  = parsed["parcelas"]
    hoje      = datetime.now().strftime("%Y-%m-%d")
    mes       = datetime.now().strftime("%Y-%m")

    viagem_ativa = _get_viagem_ativa_bot()
    viagem_id    = str(viagem_ativa["id"]) if viagem_ativa else ""
    if viagem_ativa:
        categoria = "Viagem"

    valor_parcela = round(valor / parcelas, 2)
    id_grupo = _new_id()
    ws = _ws("gastos")

    for i in range(1, parcelas + 1):
        ws.append_row([
            _new_id(), id_grupo, hoje, hoje, mes,
            str(i), str(parcelas),
            str(valor_parcela), str(valor),
            categoria, forma, conta, desc, _now(), viagem_id, "",
        ])

    viagem_tag = f"\n✈️ Viagem: {viagem_ativa.get('nome', '')}" if viagem_ativa else ""
    if parcelas > 1:
        return (
            f"✅ <b>Gasto registrado</b>\n\n"
            f"💸 {_fmt(valor)} em {parcelas}x de {_fmt(valor_parcela)}\n"
            f"📂 {categoria}\n"
            f"💳 {forma} — {conta}\n"
            f"📝 {desc}{viagem_tag}"
        )
    return (
        f"✅ <b>Gasto registrado</b>\n\n"
        f"💸 {_fmt(valor)}\n"
        f"📂 {categoria}\n"
        f"💳 {forma} — {conta}\n"
        f"📝 {desc}{viagem_tag}"
    )


def cmd_entrada(parts: list[str]) -> str:
    parsed = _parse_entrada(parts)
    if isinstance(parsed, str):
        return parsed

    valor = parsed["valor"]
    fonte = parsed["fonte"]
    conta = parsed["conta"] or _get_config("bot_conta_padrao", "") or "—"
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


# ─── Horário de Brasília ──────────────────────────────────────────────────────


def _br_now() -> datetime:
    return datetime.utcnow() - timedelta(hours=3)


# ─── Resumo diário automático ─────────────────────────────────────────────────

_last_daily_date: str = ""


def _build_daily_summary() -> str:
    agora     = _br_now()
    hoje_str  = agora.strftime("%Y-%m-%d")
    mes       = agora.strftime("%Y-%m")

    entradas_rows = _get_all("entradas")
    gastos_rows   = _get_all("gastos")

    gastos_hoje = [r for r in gastos_rows if str(r.get("data", "")).startswith(hoje_str)]
    total_hoje  = sum(float(r.get("valor_parcela", 0) or 0) for r in gastos_hoje)

    total_ent_mes = sum(
        float(r.get("valor", 0) or 0)
        for r in entradas_rows
        if str(r.get("data", "")).startswith(mes)
    )
    total_gas_mes = sum(
        float(r.get("valor_parcela", 0) or 0)
        for r in gastos_rows
        if str(r.get("mes_referencia", "")).startswith(mes)
    )
    saldo_mes   = total_ent_mes - total_gas_mes
    emoji_saldo = "✅" if saldo_mes >= 0 else "⚠️"

    cats_hoje: dict[str, float] = {}
    for r in gastos_hoje:
        cat = r.get("categoria", "Outros")
        cats_hoje[cat] = cats_hoje.get(cat, 0) + float(r.get("valor_parcela", 0) or 0)

    linhas = [f"🌙 <b>Resumo do Dia — {agora.strftime('%d/%m/%Y')}</b>\n"]
    if total_hoje > 0:
        linhas.append(f"💸 <b>Gastos hoje:</b> {_fmt(total_hoje)}")
        for cat, val in sorted(cats_hoje.items(), key=lambda x: -x[1]):
            linhas.append(f"  └ {cat}: {_fmt(val)}")
    else:
        linhas.append("💸 Nenhum gasto registrado hoje.")

    linhas.append(f"\n📊 <b>Mês {mes}:</b>")
    linhas.append(f"  💰 Receitas: {_fmt(total_ent_mes)}")
    linhas.append(f"  💸 Despesas: {_fmt(total_gas_mes)}")
    linhas.append(f"  {emoji_saldo} Saldo: {_fmt(saldo_mes)}")
    return "\n".join(linhas)


def _daily_summary_loop() -> None:
    global _last_daily_date
    while True:
        try:
            agora    = _br_now()
            hoje_str = agora.strftime("%Y-%m-%d")
            if agora.hour == 20 and agora.minute < 5 and _last_daily_date != hoje_str:
                if CHAT_ID and TOKEN:
                    send(_build_daily_summary())
                    _last_daily_date = hoje_str
                    log.info("Resumo diário enviado.")
        except Exception as exc:
            log.warning("Erro no resumo diário: %s", exc)
        time.sleep(60)


# ─── NLP via Claude ───────────────────────────────────────────────────────────

_ac_client = None


def _get_ac():
    global _ac_client
    if _ac_client is None and _anthropic and ANTHROPIC_KEY:
        _ac_client = _anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    return _ac_client


def _get_nlp_system() -> str:
    _refresh_cats()
    cats_list = ", ".join(sorted(set(CAT_ABBREV.values())))
    return (
        "Você é um assistente de finanças pessoais. O usuário vai enviar uma mensagem descrevendo "
        "uma transação em português informal. Extraia as informações e responda APENAS com um JSON "
        "válido, sem markdown, sem explicações, somente o objeto JSON.\n\n"
        "Campos obrigatórios:\n"
        "{\n"
        '  "tipo": "gasto" | "entrada" | "desconhecido",\n'
        '  "valor": número float (ex: 45.50),\n'
        f'  "categoria": uma de: {cats_list},\n'
        '  "descricao": string curta do item (ex: "uber", "mercado", "salário"),\n'
        '  "forma": "Pix" | "Débito" | "Crédito" | "Dinheiro"  (infira pelo contexto; padrão = Pix),\n'
        '  "conta": string com banco/cartão se mencionado, senão "",\n'
        '  "parcelas": inteiro (1 se não mencionado),\n'
        '  "fonte": string (só para tipo=entrada, ex: "Salário", "Freelance"; senão "")\n'
        "}\n\n"
        "Regras:\n"
        "- Se for menção de pagamento com cartão/crédito, forma = \"Crédito\"\n"
        "- Se for menção de débito/conta, forma = \"Débito\"\n"
        "- Se citar \"pix\" explicitamente, forma = \"Pix\"\n"
        "- Dinheiro apenas se explicitamente citado\n"
        "- Para tipo=desconhecido, preencha os outros campos com valores padrão (valor=0)"
    )


def _parse_nlp(text: str) -> dict | None:
    ac = _get_ac()
    if not ac:
        return None
    try:
        resp = ac.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=_get_nlp_system(),
            messages=[{"role": "user", "content": text}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        log.warning("NLP parse error: %s", exc)
        return None


def handle_natural_language(text: str, chat_id: str) -> None:
    ac = _get_ac()
    if not ac:
        send(
            "⚠️ Interpretação em linguagem natural não configurada.\n\n"
            "Use os comandos diretos:\n"
            "<code>/gasto 45 ali mercado pix</code>\n"
            "<code>/entrada 3000 Salário nubank</code>\n"
            "<code>/ajuda</code> para ver todos.",
            chat_id=chat_id,
        )
        return

    result = _parse_nlp(text)

    if result is None:
        send(
            "❌ Não consegui interpretar. Tente:\n"
            "• <i>\"gastei 45 no mercado\"</i>\n"
            "• <i>\"paguei 80 de uber no débito\"</i>\n"
            "• <i>\"recebi 3000 de salário\"</i>\n\n"
            "Ou use <code>/ajuda</code>.",
            chat_id=chat_id,
        )
        return

    tipo = result.get("tipo", "desconhecido")

    if tipo not in ("gasto", "entrada"):
        send(
            "ℹ️ Não identifiquei uma transação nessa mensagem.\n\n"
            "Exemplos que funcionam:\n"
            "• <i>\"gastei 45 no mercado\"</i>\n"
            "• <i>\"paguei 80 de uber no crédito\"</i>\n"
            "• <i>\"recebi 3000 de salário\"</i>",
            chat_id=chat_id,
        )
        return

    valor = float(result.get("valor", 0) or 0)
    if valor <= 0:
        send("❌ Não consegui identificar o valor. Tente ser mais específico (ex: <i>\"gastei 45 no mercado\"</i>).", chat_id=chat_id)
        return

    hoje = datetime.now().strftime("%Y-%m-%d")
    mes  = datetime.now().strftime("%Y-%m")

    if tipo == "gasto":
        categoria = result.get("categoria", "Outros") or "Outros"
        descricao = result.get("descricao", "sem descrição") or "sem descrição"
        forma     = result.get("forma", "Pix") or "Pix"
        conta     = result.get("conta", "") or _get_config("bot_conta_padrao", "") or "—"
        parcelas  = max(1, int(result.get("parcelas", 1) or 1))

        viagem_ativa = _get_viagem_ativa_bot()
        viagem_id    = str(viagem_ativa["id"]) if viagem_ativa else ""
        if viagem_ativa:
            categoria = "Viagem"

        valor_parcela = round(valor / parcelas, 2)
        id_grupo      = _new_id()
        ws            = _ws("gastos")

        for i in range(1, parcelas + 1):
            ws.append_row([
                _new_id(), id_grupo, hoje, hoje, mes,
                str(i), str(parcelas),
                str(valor_parcela), str(valor),
                categoria, forma, conta, descricao, _now(), viagem_id, "",
            ])

        prc_txt    = f" em {parcelas}x de {_fmt(valor_parcela)}" if parcelas > 1 else ""
        viagem_tag = f"\n✈️ Viagem: {viagem_ativa.get('nome', '')}" if viagem_ativa else ""
        send(
            f"✅ <b>Gasto registrado</b>\n\n"
            f"💸 {_fmt(valor)}{prc_txt}\n"
            f"📂 {categoria}\n"
            f"💳 {forma} — {conta}\n"
            f"📝 {descricao}{viagem_tag}",
            chat_id=chat_id,
        )

    elif tipo == "entrada":
        fonte = result.get("fonte", "") or result.get("descricao", "Outros") or "Outros"
        conta = result.get("conta", "") or _get_config("bot_conta_padrao", "") or "—"
        ws    = _ws("entradas")
        rid   = _new_id()
        ws.append_row([rid, hoje, str(valor), fonte, conta, "", _now()])

        send(
            f"✅ <b>Entrada registrada</b>\n\n"
            f"💰 {_fmt(valor)}\n"
            f"📌 {fonte}\n"
            f"🏦 {conta}",
            chat_id=chat_id,
        )


# ─── Viagens ─────────────────────────────────────────────────────────────────


def _get_config(key: str, default: str = "") -> str:
    try:
        rows = _get_all("config")
        for r in rows:
            if str(r.get("chave", "")) == key:
                return str(r.get("valor", default))
    except Exception:
        pass
    return default


def _get_viagem_ativa_bot() -> dict | None:
    from datetime import date
    hoje = date.today().isoformat()
    try:
        rows = _get_all("viagens")
        for r in rows:
            if str(r.get("status", "")).lower() == "ativo":
                d_ini = str(r.get("data_inicio", ""))
                d_fim = str(r.get("data_fim", ""))
                if d_ini and d_fim and d_ini <= hoje <= d_fim:
                    return r
    except Exception:
        pass
    return None


def _parse_viagem_criar(parts: list[str]) -> dict | str:
    import re
    DATE_RE = re.compile(r'^\d{1,2}/\d{1,2}(?:/\d{2,4})?$')

    date_indices = [i for i, p in enumerate(parts) if DATE_RE.match(p)]
    if len(date_indices) < 2:
        return (
            "Formato:\n"
            "<code>/viagem criar Nome Destino DD/MM DD/MM orçamento</code>\n\n"
            "Ex: <code>/viagem criar Buenos Aires 15/10 22/10 5000</code>"
        )

    i1, i2 = date_indices[0], date_indices[1]
    nome_destino = parts[:i1]
    resto = parts[i2 + 1:]

    if not nome_destino:
        return "❌ Informe o nome/destino da viagem."
    if not resto:
        return "❌ Informe o orçamento após as datas."
    try:
        orcamento = float(resto[0].replace(",", "."))
    except ValueError:
        return f"❌ Orçamento inválido: <code>{resto[0]}</code>"

    nome    = nome_destino[0]
    destino = " ".join(nome_destino[1:]) if len(nome_destino) > 1 else nome_destino[0]

    def _parse_date(s: str) -> str | None:
        bits = s.split("/")
        try:
            d, mo = int(bits[0]), int(bits[1])
            y = int(bits[2]) if len(bits) == 3 else datetime.now().year
            if y < 100:
                y += 2000
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except Exception:
            return None

    d_ini = _parse_date(parts[i1])
    d_fim = _parse_date(parts[i2])

    if not d_ini:
        return f"❌ Data de início inválida: <code>{parts[i1]}</code>. Use DD/MM ou DD/MM/AAAA."
    if not d_fim:
        return f"❌ Data de fim inválida: <code>{parts[i2]}</code>. Use DD/MM ou DD/MM/AAAA."
    if d_fim < d_ini:
        return "❌ A data de fim deve ser posterior à de início."

    return {
        "nome": nome,
        "destino": destino,
        "data_inicio": d_ini,
        "data_fim": d_fim,
        "orcamento": orcamento,
    }


def cmd_viagem(parts: list[str]) -> str:
    sub = parts[0].lower() if parts else "status"

    if sub == "status":
        viagem = _get_viagem_ativa_bot()
        if not viagem:
            return "✈️ Nenhuma viagem ativa no momento.\n\nUse <code>/viagem criar</code> para iniciar uma."
        vid       = str(viagem.get("id", ""))
        nome      = viagem.get("nome", "")
        dest      = viagem.get("destino", "")
        d_ini_v   = viagem.get("data_inicio", "")
        d_fim_v   = viagem.get("data_fim", "")
        orc       = float(viagem.get("orcamento", 0) or 0)
        gastos_rows = _get_all("gastos")
        total_gasto = sum(
            float(r.get("valor_parcela", 0) or 0)
            for r in gastos_rows
            if str(r.get("viagem_id", "")) == vid
        )
        saldo = orc - total_gasto
        pct   = total_gasto / orc * 100 if orc > 0 else 0
        return (
            f"✈️ <b>Viagem ativa: {nome}</b>\n\n"
            f"📍 Destino: {dest}\n"
            f"📅 {d_ini_v} → {d_fim_v}\n\n"
            f"💰 Orçamento: {_fmt(orc)}\n"
            f"💸 Gasto:     {_fmt(total_gasto)} ({pct:.1f}%)\n"
            f"💚 Saldo:     {_fmt(saldo)}"
        )

    elif sub == "criar":
        parsed = _parse_viagem_criar(parts[1:])
        if isinstance(parsed, str):
            return parsed
        viagem_atual = _get_viagem_ativa_bot()
        if viagem_atual:
            return (
                f"⚠️ Já existe uma viagem ativa: <b>{viagem_atual.get('nome', '')}</b>.\n"
                "Encerre a atual antes de criar uma nova.\n"
                "Use: <code>/viagem encerrar</code>"
            )
        rid = _new_id()
        ws  = _ws("viagens")
        ws.append_row([
            rid,
            parsed["nome"],
            parsed["destino"],
            parsed["data_inicio"],
            parsed["data_fim"],
            str(parsed["orcamento"]),
            "ativo",
            _now(),
        ])
        return (
            f"✈️ <b>Viagem criada!</b>\n\n"
            f"📍 {parsed['nome']} → {parsed['destino']}\n"
            f"📅 {parsed['data_inicio']} → {parsed['data_fim']}\n"
            f"💰 Orçamento: {_fmt(parsed['orcamento'])}\n\n"
            "Todos os gastos durante o período serão automaticamente marcados como <b>Viagem</b>."
        )

    elif sub == "encerrar":
        viagem = _get_viagem_ativa_bot()
        if not viagem:
            return "✈️ Nenhuma viagem ativa para encerrar."
        vid  = str(viagem.get("id", ""))
        nome = viagem.get("nome", "")
        orc  = float(viagem.get("orcamento", 0) or 0)
        ws   = _ws("viagens")
        all_rows = ws.get_all_values()
        headers  = all_rows[0] if all_rows else []
        try:
            id_col     = headers.index("id") + 1
            status_col = headers.index("status") + 1
        except ValueError:
            return "❌ Erro ao localizar colunas da planilha de viagens."
        for row_idx, row in enumerate(all_rows[1:], start=2):
            if len(row) >= id_col and row[id_col - 1] == vid:
                ws.update_cell(row_idx, status_col, "encerrada")
                break
        gastos_rows = _get_all("gastos")
        total_gasto = sum(
            float(r.get("valor_parcela", 0) or 0)
            for r in gastos_rows
            if str(r.get("viagem_id", "")) == vid
        )
        return (
            f"🏁 <b>Viagem encerrada: {nome}</b>\n\n"
            f"💸 Total gasto: {_fmt(total_gasto)}\n"
            f"💰 Orçamento era: {_fmt(orc)}"
        )

    else:
        return (
            "✈️ <b>Comandos de Viagem:</b>\n\n"
            "<code>/viagem status</code> — ver viagem ativa\n"
            "<code>/viagem criar Nome Destino DD/MM DD/MM orçamento</code>\n"
            "<code>/viagem encerrar</code> — encerrar viagem ativa\n\n"
            "Ex: <code>/viagem criar Buenos Aires 15/10 22/10 5000</code>"
        )


def cmd_link(_: list[str]) -> str:
    if APP_URL:
        return (
            "🔗 <b>Link de acesso ao FinTrack:</b>\n\n"
            f"<a href='{APP_URL}'>{APP_URL}</a>"
        )
    return (
        "⚠️ URL do app não configurada.\n"
        "Adicione a variável <code>APP_URL</code> nas configurações do Railway "
        "com o endereço público do seu app (ex: <code>https://seu-app.up.railway.app</code>)."
    )


def cmd_ajuda(_: list[str]) -> str:
    _refresh_cats(force=True)
    cats_lines = "\n".join(
        f"  <code>{k}</code> = {v}"
        for k, v in sorted(CAT_ABBREV.items(), key=lambda x: x[1])
    )
    formas = " · ".join(f"<code>{k}</code>={v}" for k, v in FORMAS.items())
    return (
        "🤖 <b>FinTrack Bot — Comandos</b>\n\n"
        "<b>💸 Registrar gasto:</b>\n"
        "<code>/gasto valor cat descrição forma [conta] [Nx]</code>\n"
        "  <code>/gasto 45.50 ali mercado pix</code>\n"
        "  <code>/gasto 80 trans uber db nubank</code>\n"
        "  <code>/gasto 600 vest tênis cr nubank 3x</code>\n\n"
        f"<b>Categorias disponíveis:</b>\n{cats_lines}\n\n"
        f"<b>Formas de pagamento:</b> {formas}\n\n"
        "<b>💰 Registrar entrada:</b>\n"
        "<code>/entrada valor fonte [conta]</code>\n"
        "  <code>/entrada 3000 Salário nubank</code>\n\n"
        "<b>📊 Consultas:</b>\n"
        "<code>/saldo</code>  — saldo do mês atual\n"
        "<code>/resumo</code> — gastos por categoria\n\n"
        "<b>🔗 Acesso:</b>\n"
        "<code>/link</code> — link de acesso ao app\n\n"
        "<b>✈️ Viagens:</b>\n"
        "<code>/viagem status</code>  — viagem ativa e saldo\n"
        "<code>/viagem criar Nome Dest DD/MM DD/MM orçamento</code>\n"
        "<code>/viagem encerrar</code> — encerra viagem ativa\n"
        "  <i>Gastos durante a viagem são marcados automaticamente como Viagem.</i>\n\n"
        "<b>💬 Linguagem natural:</b>\n"
        "Envie qualquer mensagem sem <code>/</code> e o bot interpreta automaticamente:\n"
        "  <i>\"gastei 45 no mercado\"</i>\n"
        "  <i>\"paguei 200 de luz no débito\"</i>\n"
        "  <i>\"recebi 3000 de salário\"</i>"
    )


COMMANDS: dict[str, callable] = {
    "/gasto":   cmd_gasto,
    "/entrada": cmd_entrada,
    "/saldo":   cmd_saldo,
    "/resumo":  cmd_resumo,
    "/viagem":  cmd_viagem,
    "/link":    cmd_link,
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
    log.info("Mensagem recebida de chat_id=%s (CHAT_ID configurado=%s)", chat_id, CHAT_ID or "(não definido)")
    if CHAT_ID and chat_id != CHAT_ID:
        log.warning("chat_id %s não autorizado — ignorando.", chat_id)
        send(f"⚠️ Bot recebeu mensagem de chat_id <code>{chat_id}</code> mas TELEGRAM_CHAT_ID={CHAT_ID}. Atualize a variável de ambiente.", chat_id=chat_id)
        return

    text = (msg.get("text") or "").strip()
    if not text:
        return

    if not text.startswith("/"):
        log.info("Mensagem livre (NLP): %.60s", text)
        try:
            handle_natural_language(text, chat_id)
        except Exception as exc:
            log.exception("Erro no NLP")
            send(f"❌ Erro ao processar mensagem.\n<code>{exc}</code>", chat_id=chat_id)
        return

    parts = text.split()
    cmd   = parts[0].split("@")[0].lower()
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

    log.info("FinTrack Bot iniciado. Verificando token...")
    me = _tg("getMe")
    if not me.get("ok"):
        log.error("Token inválido: %s", me)
        return
    log.info("Bot autenticado: @%s", me["result"].get("username"))

    _refresh_cats(force=True)

    t = threading.Thread(target=_daily_summary_loop, daemon=True, name="daily-summary")
    t.start()
    log.info("Agendador de resumo diário iniciado (envia às 20h horário de Brasília).")

    nlp_status = "✅ NLP ativo" if (_anthropic and ANTHROPIC_KEY) else "⚠️ NLP desativado (ANTHROPIC_API_KEY não configurado)"
    send(f"✅ FinTrack Bot iniciado e pronto para receber comandos!\n{nlp_status}")

    log.info("Polling...")
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
            if not data.get("ok"):
                log.error("getUpdates erro: %s", data)
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                handle_update(upd)
                offset = upd["update_id"] + 1
        except Exception as exc:
            log.warning("Erro no polling: %s — aguardando 5s...", exc)
            time.sleep(5)


if __name__ == "__main__":
    run()

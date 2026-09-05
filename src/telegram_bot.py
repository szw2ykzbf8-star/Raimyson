import requests
from src.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"


def enviar_mensagem(texto: str, chat_id: str = None) -> bool:
    cid = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not cid:
        return False
    try:
        resp = requests.post(
            _url("sendMessage"),
            json={"chat_id": cid, "text": texto, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def enviar_codigo_desbloqueio(codigo: str) -> bool:
    texto = (
        "🔐 <b>FinTrack — Código de Desbloqueio</b>\n\n"
        f"Código: <code>{codigo}</code>\n\n"
        "⏱️ Válido por 60 segundos.\n"
        "Não compartilhe este código com ninguém."
    )
    return enviar_mensagem(texto)


def enviar_alerta_categoria(categoria: str, gasto: float, limite: float) -> bool:
    pct = int((gasto / limite) * 100)
    emoji = "🚨" if gasto >= limite else "⚠️"
    texto = (
        f"{emoji} <b>FinTrack — Alerta de Categoria</b>\n\n"
        f"Categoria: <b>{categoria}</b>\n"
        f"Gasto: R$ {gasto:,.2f} ({pct}% do limite)\n"
        f"Limite: R$ {limite:,.2f}"
    )
    return enviar_mensagem(texto)


def enviar_alerta_fatura(cartao: str, valor: float, vencimento: str) -> bool:
    texto = (
        f"💳 <b>FinTrack — Fatura Próxima</b>\n\n"
        f"Cartão: <b>{cartao}</b>\n"
        f"Valor: R$ {valor:,.2f}\n"
        f"Vencimento: {vencimento}"
    )
    return enviar_mensagem(texto)


def enviar_resumo_mensal(mes: str, entradas: float, saidas: float, saldo: float) -> bool:
    emoji = "✅" if saldo >= 0 else "❌"
    texto = (
        f"📊 <b>FinTrack — Resumo {mes}</b>\n\n"
        f"Entradas: R$ {entradas:,.2f}\n"
        f"Saídas:   R$ {saidas:,.2f}\n"
        f"Saldo:    R$ {saldo:,.2f} {emoji}"
    )
    return enviar_mensagem(texto)


def get_chat_id_bot() -> str | None:
    """Retorna o chat_id da última mensagem recebida pelo bot (para setup inicial)."""
    if not TELEGRAM_TOKEN:
        return None
    try:
        resp = requests.get(_url("getUpdates"), timeout=10)
        data = resp.json()
        updates = data.get("result", [])
        if updates:
            return str(updates[-1]["message"]["chat"]["id"])
    except Exception:
        pass
    return None

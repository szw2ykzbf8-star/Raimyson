import time
import secrets
import bcrypt
import streamlit as st
from src import sheets as sh
from src.config import MAX_TENTATIVAS_PIN, CODIGO_EXPIRACAO_SEG, INATIVIDADE_PADRAO_MIN

# ─── Tipos de PIN ────────────────────────────────────────────────────────────

PIN_ABERTURA = "pin_abertura"
PIN_EXCLUSAO = "pin_exclusao"

LOCK_ABERTURA = "BLOQUEADO_ABERTURA"
LOCK_EXCLUSAO = "BLOQUEADO_EXCLUSAO"
DESBLOQUEADO = "DESBLOQUEADO"

# ─── Hashing ─────────────────────────────────────────────────────────────────


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode(), hashed.encode())
    except Exception:
        return False


# ─── Primeiro acesso ─────────────────────────────────────────────────────────


def is_primeiro_acesso() -> bool:
    return sh.get_config("primeiro_acesso", "True") == "True"


def configurar_pins(pin_abertura: str, pin_exclusao: str):
    sh.set_config(PIN_ABERTURA, hash_pin(pin_abertura))
    sh.set_config(PIN_EXCLUSAO, hash_pin(pin_exclusao))
    sh.set_config("tentativas_abertura", "0")
    sh.set_config("tentativas_exclusao", "0")
    sh.set_config("bloqueio_estado", DESBLOQUEADO)
    sh.set_config("codigo_desbloqueio", "")
    sh.set_config("codigo_timestamp", "")
    sh.set_config("inatividade_minutos", str(INATIVIDADE_PADRAO_MIN))
    sh.set_config("primeiro_acesso", "False")


# ─── Estado de bloqueio (persistido no Sheets) ────────────────────────────────


def get_estado_bloqueio() -> str:
    return sh.get_config("bloqueio_estado", DESBLOQUEADO)


def get_tentativas(tipo: str) -> int:
    chave = "tentativas_abertura" if tipo == PIN_ABERTURA else "tentativas_exclusao"
    return int(sh.get_config(chave, "0"))


def set_tentativas(tipo: str, n: int):
    chave = "tentativas_abertura" if tipo == PIN_ABERTURA else "tentativas_exclusao"
    sh.set_config(chave, str(n))


def bloquear(tipo: str):
    estado = LOCK_ABERTURA if tipo == PIN_ABERTURA else LOCK_EXCLUSAO
    sh.set_config("bloqueio_estado", estado)


def desbloquear():
    sh.set_config("bloqueio_estado", DESBLOQUEADO)
    sh.set_config("tentativas_abertura", "0")
    sh.set_config("tentativas_exclusao", "0")
    sh.set_config("codigo_desbloqueio", "")
    sh.set_config("codigo_timestamp", "")
    if "authenticated" in st.session_state:
        del st.session_state["authenticated"]


# ─── Autenticação de sessão ───────────────────────────────────────────────────


def update_activity():
    st.session_state["last_activity"] = time.time()


def check_inatividade() -> bool:
    """Retorna True se inatividade expirou (deve bloquear)."""
    if not st.session_state.get("authenticated", False):
        return False
    last = st.session_state.get("last_activity", time.time())
    timeout = int(sh.get_config("inatividade_minutos", str(INATIVIDADE_PADRAO_MIN))) * 60
    return (time.time() - last) > timeout


def is_authenticated() -> bool:
    estado = get_estado_bloqueio()
    if estado != DESBLOQUEADO:
        return False
    if check_inatividade():
        st.session_state["authenticated"] = False
        return False
    return st.session_state.get("authenticated", False)


def autenticar(pin: str) -> tuple[bool, str]:
    """
    Retorna (sucesso, mensagem).
    Gerencia tentativas e bloqueio automaticamente.
    """
    estado = get_estado_bloqueio()
    if estado == LOCK_ABERTURA:
        return False, "bloqueado"

    hashed = sh.get_config(PIN_ABERTURA, "")
    if not hashed:
        return False, "PIN não configurado."

    if verify_pin(pin, hashed):
        sh.set_config("tentativas_abertura", "0")
        st.session_state["authenticated"] = True
        update_activity()
        return True, "ok"
    else:
        tentativas = get_tentativas(PIN_ABERTURA) + 1
        set_tentativas(PIN_ABERTURA, tentativas)
        restantes = MAX_TENTATIVAS_PIN - tentativas
        if tentativas >= MAX_TENTATIVAS_PIN:
            bloquear(PIN_ABERTURA)
            return False, "bloqueado"
        return False, f"PIN incorreto. {restantes} tentativa(s) restante(s)."


def verificar_pin_exclusao(pin: str) -> tuple[bool, str]:
    estado = get_estado_bloqueio()
    if estado == LOCK_EXCLUSAO:
        return False, "bloqueado"

    hashed = sh.get_config(PIN_EXCLUSAO, "")
    if verify_pin(pin, hashed):
        sh.set_config("tentativas_exclusao", "0")
        return True, "ok"
    else:
        tentativas = get_tentativas(PIN_EXCLUSAO) + 1
        set_tentativas(PIN_EXCLUSAO, tentativas)
        restantes = MAX_TENTATIVAS_PIN - tentativas
        if tentativas >= MAX_TENTATIVAS_PIN:
            bloquear(PIN_EXCLUSAO)
            st.session_state["authenticated"] = False
            return False, "bloqueado"
        return False, f"PIN de exclusão incorreto. {restantes} tentativa(s) restante(s)."


# ─── Código de desbloqueio (Telegram 2FA) ────────────────────────────────────


def gerar_codigo() -> str:
    codigo = str(secrets.randbelow(900000) + 100000)
    sh.set_config("codigo_desbloqueio", hash_pin(codigo))
    sh.set_config("codigo_timestamp", str(time.time()))
    return codigo


def verificar_codigo(codigo: str) -> tuple[bool, str]:
    hashed = sh.get_config("codigo_desbloqueio", "")
    ts_str = sh.get_config("codigo_timestamp", "0")

    if not hashed:
        return False, "Nenhum código ativo."

    if (time.time() - float(ts_str)) > CODIGO_EXPIRACAO_SEG:
        sh.set_config("codigo_desbloqueio", "")
        return False, "Código expirado. Solicite um novo."

    if verify_pin(codigo, hashed):
        desbloquear()
        return True, "ok"
    return False, "Código incorreto."


# ─── Guard para páginas ───────────────────────────────────────────────────────


def require_auth():
    """Chame no topo de cada página. Para a renderização se não autenticado."""
    if not is_authenticated():
        st.error("🔒 Sessão encerrada. Volte à página inicial para fazer login.")
        st.stop()
    update_activity()

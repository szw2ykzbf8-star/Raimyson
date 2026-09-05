import hmac as _hmac
import hashlib
import time
import secrets
import bcrypt
import streamlit as st
from src import sheets as sh
from src.config import (
    MAX_TENTATIVAS_PIN, CODIGO_EXPIRACAO_SEG, INATIVIDADE_PADRAO_MIN,
    CODIGO_COOLDOWN_SEG, MAX_TENTATIVAS_CODIGO, PIN_PEPPER, HMAC_KEY,
    CFG_PRIMEIRO_ACESSO, CFG_PIN_ABERTURA, CFG_PIN_EXCLUSAO,
    CFG_TENTATIVAS_ABERTURA, CFG_TENTATIVAS_EXCLUSAO, CFG_BLOQUEIO_ESTADO,
    CFG_CODIGO_DESBLOQUEIO, CFG_CODIGO_TIMESTAMP, CFG_CODIGO_TENTATIVAS,
    CFG_INATIVIDADE_MIN,
)

# ─── Aliases públicos (usados por outros módulos) ─────────────────────────────

PIN_ABERTURA = CFG_PIN_ABERTURA
PIN_EXCLUSAO = CFG_PIN_EXCLUSAO

LOCK_ABERTURA = "BLOQUEADO_ABERTURA"
LOCK_EXCLUSAO = "BLOQUEADO_EXCLUSAO"
DESBLOQUEADO  = "DESBLOQUEADO"

_ESTADOS_VALIDOS = {DESBLOQUEADO, LOCK_ABERTURA, LOCK_EXCLUSAO}

# ─── HMAC do estado de bloqueio ───────────────────────────────────────────────


def _sign_estado(state: str) -> str:
    if not HMAC_KEY:
        return state
    sig = _hmac.new(HMAC_KEY.encode(), state.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{state}:{sig}"


def _verify_estado(stored: str) -> str:
    if ":" not in stored:
        # Valor sem assinatura (legado ou sem HMAC_KEY)
        return stored if stored in _ESTADOS_VALIDOS else LOCK_ABERTURA
    state, sig = stored.rsplit(":", 1)
    if state not in _ESTADOS_VALIDOS:
        return LOCK_ABERTURA
    if not HMAC_KEY:
        return state
    expected = _hmac.new(HMAC_KEY.encode(), state.encode(), hashlib.sha256).hexdigest()[:16]
    if _hmac.compare_digest(sig, expected):
        return state
    return LOCK_ABERTURA  # assinatura inválida → fail secure


# ─── Hashing de PIN com pepper ────────────────────────────────────────────────


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw((pin + PIN_PEPPER).encode(), bcrypt.gensalt()).decode()


def verify_pin(pin: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw((pin + PIN_PEPPER).encode(), hashed.encode())
    except Exception:
        return False


# ─── Primeiro acesso ─────────────────────────────────────────────────────────


def is_primeiro_acesso() -> bool:
    """
    Retorna True somente se o flag está True E nenhum PIN foi configurado.
    Impede bypass via edição direta do Sheets (flag=True sem apagar os hashes).
    """
    pin_a = sh.get_config(CFG_PIN_ABERTURA, "")
    pin_e = sh.get_config(CFG_PIN_EXCLUSAO, "")
    if pin_a and pin_e:
        return False
    return sh.get_config(CFG_PRIMEIRO_ACESSO, "True") == "True"


def configurar_pins(pin_abertura: str, pin_exclusao: str):
    sh.set_config(CFG_PIN_ABERTURA,          hash_pin(pin_abertura))
    sh.set_config(CFG_PIN_EXCLUSAO,          hash_pin(pin_exclusao))
    sh.set_config(CFG_TENTATIVAS_ABERTURA,   "0")
    sh.set_config(CFG_TENTATIVAS_EXCLUSAO,   "0")
    sh.set_config(CFG_BLOQUEIO_ESTADO,       _sign_estado(DESBLOQUEADO))
    sh.set_config(CFG_CODIGO_DESBLOQUEIO,    "")
    sh.set_config(CFG_CODIGO_TIMESTAMP,      "")
    sh.set_config(CFG_CODIGO_TENTATIVAS,     "0")
    sh.set_config(CFG_INATIVIDADE_MIN,       str(INATIVIDADE_PADRAO_MIN))
    sh.set_config(CFG_PRIMEIRO_ACESSO,       "False")


# ─── Estado de bloqueio ───────────────────────────────────────────────────────


def get_estado_bloqueio() -> str:
    raw = sh.get_config(CFG_BLOQUEIO_ESTADO, DESBLOQUEADO)
    return _verify_estado(raw)


def get_tentativas(tipo: str) -> int:
    chave = CFG_TENTATIVAS_ABERTURA if tipo == PIN_ABERTURA else CFG_TENTATIVAS_EXCLUSAO
    return int(sh.get_config(chave, "0"))


def set_tentativas(tipo: str, n: int):
    chave = CFG_TENTATIVAS_ABERTURA if tipo == PIN_ABERTURA else CFG_TENTATIVAS_EXCLUSAO
    sh.set_config(chave, str(n))


def bloquear(tipo: str):
    estado = LOCK_ABERTURA if tipo == PIN_ABERTURA else LOCK_EXCLUSAO
    sh.set_config(CFG_BLOQUEIO_ESTADO, _sign_estado(estado))


def desbloquear():
    sh.set_config(CFG_BLOQUEIO_ESTADO,       _sign_estado(DESBLOQUEADO))
    sh.set_config(CFG_TENTATIVAS_ABERTURA,   "0")
    sh.set_config(CFG_TENTATIVAS_EXCLUSAO,   "0")
    sh.set_config(CFG_CODIGO_DESBLOQUEIO,    "")
    sh.set_config(CFG_CODIGO_TIMESTAMP,      "")
    sh.set_config(CFG_CODIGO_TENTATIVAS,     "0")
    for key in ("authenticated", "admin_autenticado"):
        st.session_state.pop(key, None)


# ─── Autenticação de sessão ───────────────────────────────────────────────────


def update_activity():
    st.session_state["last_activity"] = time.time()


def check_inatividade() -> bool:
    if not st.session_state.get("authenticated", False):
        return False
    last   = st.session_state.get("last_activity", time.time())
    timeout = int(sh.get_config(CFG_INATIVIDADE_MIN, str(INATIVIDADE_PADRAO_MIN))) * 60
    return (time.time() - last) > timeout


def is_authenticated() -> bool:
    estado = get_estado_bloqueio()
    if estado != DESBLOQUEADO:
        return False
    if check_inatividade():
        st.session_state["authenticated"] = False
        st.session_state.pop("admin_autenticado", None)
        return False
    return st.session_state.get("authenticated", False)


def autenticar(pin: str) -> tuple[bool, str]:
    estado = get_estado_bloqueio()
    if estado == LOCK_ABERTURA:
        return False, "bloqueado"

    hashed = sh.get_config(PIN_ABERTURA, "")
    if not hashed:
        return False, "PIN não configurado."

    if verify_pin(pin, hashed):
        sh.set_config(CFG_TENTATIVAS_ABERTURA, "0")
        st.session_state["authenticated"] = True
        update_activity()
        return True, "ok"

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
        sh.set_config(CFG_TENTATIVAS_EXCLUSAO, "0")
        return True, "ok"

    tentativas = get_tentativas(PIN_EXCLUSAO) + 1
    set_tentativas(PIN_EXCLUSAO, tentativas)
    restantes = MAX_TENTATIVAS_PIN - tentativas
    if tentativas >= MAX_TENTATIVAS_PIN:
        bloquear(PIN_EXCLUSAO)
        st.session_state["authenticated"] = False
        return False, "bloqueado"
    return False, f"PIN de exclusão incorreto. {restantes} tentativa(s) restante(s)."


# ─── Código de desbloqueio (Telegram 2FA) ────────────────────────────────────


def gerar_codigo() -> tuple[str, str]:
    """
    Gera e armazena um código de desbloqueio.
    Retorna (codigo, erro) — erro é vazio em caso de sucesso.
    Impõe cooldown para evitar spam de códigos.
    """
    ts_str  = sh.get_config(CFG_CODIGO_TIMESTAMP, "0")
    elapsed = time.time() - float(ts_str or "0")
    if elapsed < CODIGO_COOLDOWN_SEG:
        espera = int(CODIGO_COOLDOWN_SEG - elapsed)
        return "", f"Aguarde {espera}s antes de solicitar um novo código."

    codigo = str(secrets.randbelow(900000) + 100000)
    sh.set_config(CFG_CODIGO_DESBLOQUEIO, hash_pin(codigo))
    sh.set_config(CFG_CODIGO_TIMESTAMP,   str(time.time()))
    sh.set_config(CFG_CODIGO_TENTATIVAS,  "0")
    return codigo, ""


def verificar_codigo(codigo: str) -> tuple[bool, str]:
    hashed    = sh.get_config(CFG_CODIGO_DESBLOQUEIO, "")
    ts_str    = sh.get_config(CFG_CODIGO_TIMESTAMP, "0")
    tentativas = int(sh.get_config(CFG_CODIGO_TENTATIVAS, "0"))

    if not hashed:
        return False, "Nenhum código ativo."

    if (time.time() - float(ts_str)) > CODIGO_EXPIRACAO_SEG:
        sh.set_config(CFG_CODIGO_DESBLOQUEIO, "")
        return False, "Código expirado. Solicite um novo."

    if tentativas >= MAX_TENTATIVAS_CODIGO:
        sh.set_config(CFG_CODIGO_DESBLOQUEIO, "")
        return False, "Muitas tentativas. Solicite um novo código."

    if verify_pin(codigo, hashed):
        desbloquear()
        return True, "ok"

    sh.set_config(CFG_CODIGO_TENTATIVAS, str(tentativas + 1))
    restantes = MAX_TENTATIVAS_CODIGO - tentativas - 1
    return False, f"Código incorreto. {restantes} tentativa(s) restante(s)."


# ─── Guard para páginas ───────────────────────────────────────────────────────


def require_auth():
    if not is_authenticated():
        st.error("🔒 Sessão encerrada. Volte à página inicial para fazer login.")
        st.stop()
    update_activity()

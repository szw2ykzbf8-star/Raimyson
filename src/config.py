import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
SPREADSHEET_ID          = os.getenv("SPREADSHEET_ID", "")
TELEGRAM_TOKEN          = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID", "")
PIN_PEPPER              = os.getenv("PIN_PEPPER", "")
HMAC_KEY                = os.getenv("HMAC_KEY", "")

# ─── Nomes das abas ───────────────────────────────────────────────────────────

SHEETS = {
    "config":        "config",
    "categorias":    "categorias",
    "fontes":        "fontes_renda",
    "contas":        "contas_bancarias",
    "cartoes":       "cartoes",
    "fixas":         "contas_fixas",
    "dividas":       "dividas",
    "pgtos_divida":  "pagamentos_divida",
    "investimentos": "investimentos",
    "entradas":      "entradas",
    "gastos":        "gastos",
    "transferencias":"transferencias",
}

# ─── Chaves da aba config (centralizadas para evitar erros de digitação) ──────

CFG_PRIMEIRO_ACESSO       = "primeiro_acesso"
CFG_PIN_ABERTURA          = "pin_abertura"
CFG_PIN_EXCLUSAO          = "pin_exclusao"
CFG_TENTATIVAS_ABERTURA   = "tentativas_abertura"
CFG_TENTATIVAS_EXCLUSAO   = "tentativas_exclusao"
CFG_BLOQUEIO_ESTADO       = "bloqueio_estado"
CFG_CODIGO_DESBLOQUEIO    = "codigo_desbloqueio"
CFG_CODIGO_TIMESTAMP      = "codigo_timestamp"
CFG_CODIGO_TENTATIVAS     = "codigo_tentativas"
CFG_INATIVIDADE_MIN       = "inatividade_minutos"
CFG_META_ECONOMIA         = "meta_economia"
CFG_ALERTAS_CATEGORIAS    = "alertas_categorias"

# Chaves que NUNCA devem ser exportadas em backups
CFG_CHAVES_SENSIVEIS = {
    CFG_PIN_ABERTURA,
    CFG_PIN_EXCLUSAO,
    CFG_CODIGO_DESBLOQUEIO,
    CFG_CODIGO_TIMESTAMP,
    CFG_CODIGO_TENTATIVAS,
    CFG_BLOQUEIO_ESTADO,
}

# ─── Defaults de aplicação ────────────────────────────────────────────────────

CATEGORIAS_PADRAO = [
    ("Moradia",       "🏠"),
    ("Alimentação",   "🍔"),
    ("Transporte",    "🚗"),
    ("Saúde",         "💊"),
    ("Lazer",         "🎮"),
    ("Educação",      "📚"),
    ("Vestuário",     "👕"),
    ("Comunicação",   "📱"),
    ("Dívidas",       "💳"),
    ("Investimentos", "📈"),
    ("Outros",        "📦"),
]

FONTES_PADRAO = [
    "Salário",
    "Ajuda de Custo",
    "Canal",
    "Rendimento de Conta",
    "Retirada de Investimento",
    "Ajuda Familiar",
    "Sobras (Cooperativa)",
    "Outros",
]

FORMAS_PAGAMENTO     = ["Dinheiro", "Pix", "Débito", "Crédito"]
INATIVIDADE_PADRAO_MIN = 30
MAX_TENTATIVAS_PIN   = 3
CODIGO_EXPIRACAO_SEG = 60
CODIGO_COOLDOWN_SEG  = 60   # intervalo mínimo entre pedidos de código
MAX_TENTATIVAS_CODIGO = 5   # tentativas erradas antes de invalidar o código

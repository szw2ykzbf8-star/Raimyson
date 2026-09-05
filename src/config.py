import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SHEETS = {
    "config": "config",
    "categorias": "categorias",
    "fontes": "fontes_renda",
    "contas": "contas_bancarias",
    "cartoes": "cartoes",
    "fixas": "contas_fixas",
    "dividas": "dividas",
    "pgtos_divida": "pagamentos_divida",
    "investimentos": "investimentos",
    "entradas": "entradas",
    "gastos": "gastos",
    "transferencias": "transferencias",
}

CATEGORIAS_PADRAO = [
    ("Moradia", "🏠"),
    ("Alimentação", "🍔"),
    ("Transporte", "🚗"),
    ("Saúde", "💊"),
    ("Lazer", "🎮"),
    ("Educação", "📚"),
    ("Vestuário", "👕"),
    ("Comunicação", "📱"),
    ("Dívidas", "💳"),
    ("Investimentos", "📈"),
    ("Outros", "📦"),
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

FORMAS_PAGAMENTO = ["Dinheiro", "Pix", "Débito", "Crédito"]

INATIVIDADE_PADRAO_MIN = 30
MAX_TENTATIVAS_PIN = 3
CODIGO_EXPIRACAO_SEG = 60

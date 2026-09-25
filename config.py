import os

BASE_URL = os.environ.get("APP_BASE_URL", "https://compras-hhoteis.up.railway.app")

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "h-hoteis-compras-ab8bb9c498fc.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/forms.body",
]

# Nome da planilha principal no Google Drive
SPREADSHEET_NAME = "H-Hoteis-Compras"

# Abas da planilha
SHEETS = {
    "produtos":     "Produtos",
    "fornecedores": "Fornecedores",
    "unidades":     "Unidades",
    "usuarios":     "Usuarios",
    "pedidos":      "Pedidos",
    "itens_pedido": "ItensPedido",
    "cotacoes":     "Cotacoes",
    "respostas":    "RespostasFornecedores",
    "compras":      "Compras",
    "itens_compra": "ItensCompra",
    "orcamentos":   "Orcamentos",
    "historico_precos":  "HistoricoPrecos",
    "unidades_medida":   "UnidadesMedida",
    "itens_recebimento": "ItensRecebimento",
    "nfe_mapeamento":    "NfeMapeamento",
    "cotacao_tokens":    "CotacaoTokens",
}

# Unidades cadastradas
UNIDADES = ["Gold", "Roma", "Cancun", "Miami"]

# Tipos de embalagem para cotação
TIPOS_EMBALAGEM = ["Unidade/Pacote avulso", "Kg", "Litro", "Fardo/Caixa"]

SERVICE_ACCOUNT_EMAIL = "compras-h-hoteis@h-hoteis-compras.iam.gserviceaccount.com"

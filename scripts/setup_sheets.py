"""
setup_sheets.py — Execução única para criar a planilha FinTrack no Google Sheets.

Uso:
    python scripts/setup_sheets.py

Pré-requisitos:
    - pip install gspread google-auth
    - credentials.json (Service Account) no diretório raiz
    - Compartilhar o Google Drive com o e-mail da service account (ou usar
      a opção --create para criar automaticamente via Google Drive API)

O script cria a planilha (ou usa SPREADSHEET_ID do .env se já existir),
adiciona todas as abas com os cabeçalhos corretos e popula categorias/fontes
padrão. Anote o ID da planilha gerada e cole no seu .env.
"""

import sys
import os
import uuid
from datetime import datetime

# Garante que src/ seja importável mesmo rodando de scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from google.oauth2.service_account import Credentials
import gspread

# ─── Configuração ────────────────────────────────────────────────────────────

CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")
SPREADSHEET_ID   = os.environ.get("SPREADSHEET_ID", "")  # vazio = cria nova
SPREADSHEET_NAME = "FinTrack"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Categorias e fontes padrão (espelha src/config.py)
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

# Cabeçalhos de cada aba (ordem deve corresponder ao que sheets.py espera)
SHEETS_HEADERS = {
    "config": ["chave", "valor"],
    "categorias": ["id", "nome", "icone", "ativo", "criado_em"],
    "fontes_renda": ["id", "nome", "ativo", "criado_em"],
    "contas_bancarias": ["id", "nome", "tipo", "saldo_inicial", "ativo", "criado_em"],
    "cartoes": ["id", "nome", "dia_fechamento", "dia_vencimento", "ativo", "criado_em"],
    "contas_fixas": [
        "id", "nome", "valor_referencia", "categoria", "forma_pagamento",
        "conta_cartao", "dia_vencimento", "ativo", "mes_inicio", "mes_fim", "criado_em",
    ],
    "dividas": [
        "id", "nome", "valor_original", "valor_parcela", "num_parcelas",
        "num_parcelas_pagas", "data_inicio", "forma_pagamento", "conta_cartao",
        "fonte_ajuda", "ativo", "criado_em",
    ],
    "pagamentos_divida": [
        "id", "divida_id", "data", "valor_pago", "is_antecipacao",
        "num_antecipadas", "economia", "descricao", "criado_em",
    ],
    "investimentos": [
        "id", "nome", "tipo", "data_aplicacao", "valor_aplicado",
        "taxa_tipo", "taxa_valor", "data_vencimento",
        "valor_retirado", "data_retirada", "status", "criado_em", "conta_origem",
    ],
    "criptos": [
        "id", "moeda", "simbolo", "quantidade", "preco_compra_brl",
        "data_compra", "exchange", "conta_origem",
        "preco_venda_brl", "data_venda", "status", "criado_em",
    ],
    "entradas": ["id", "data", "valor", "fonte", "conta", "descricao", "criado_em"],
    "gastos": [
        "id", "id_grupo", "data_compra", "data_fatura", "mes_referencia",
        "parcela_num", "total_parcelas", "valor_parcela", "valor_total",
        "categoria", "forma_pagamento", "conta_cartao", "descricao", "criado_em",
    ],
    "transferencias": [
        "id", "data", "valor", "conta_origem", "conta_destino", "descricao", "criado_em",
    ],
    "pagamentos_contas": [
        "id", "tipo", "referencia_id", "nome", "mes_referencia",
        "valor", "conta_debito", "data_pagamento", "criado_em",
    ],
}

# Valores iniciais da aba config
CONFIG_INICIAL = [
    ("primeiro_acesso",         "True"),
    ("pin_abertura",            ""),
    ("pin_exclusao",            ""),
    ("tentativas_abertura",     "0"),
    ("tentativas_exclusao",     "0"),
    ("bloqueio_estado",         "DESBLOQUEADO"),
    ("codigo_desbloqueio",      ""),
    ("codigo_timestamp",        "0"),
    ("codigo_tentativas",       "0"),
    ("inatividade_minutos",     "30"),
    ("meta_economia",           "0"),
    ("alertas_categorias",      "{}"),
]

# ─── Funções auxiliares ───────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _ensure_sheet(spreadsheet, name: str, headers: list) -> gspread.Worksheet:
    """Cria a aba se não existir e garante que a linha de cabeçalho está correta."""
    try:
        ws = spreadsheet.worksheet(name)
        print(f"  ✓ Aba '{name}' já existe — verificando cabeçalhos...")
        existing = ws.row_values(1)
        if existing != headers:
            ws.delete_rows(1)
            ws.insert_row(headers, 1)
            print(f"    ↺ Cabeçalhos atualizados.")
        return ws
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
        ws.append_row(headers)
        print(f"  + Aba '{name}' criada.")
        return ws

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  FinTrack — Setup da Planilha Google Sheets")
    print("=" * 60)

    # Autenticação
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"\n[ERRO] Arquivo de credenciais não encontrado: {CREDENTIALS_PATH}")
        print("Baixe o JSON da sua Service Account no Google Cloud Console")
        print("e coloque-o no diretório raiz do projeto.")
        sys.exit(1)

    print(f"\n→ Autenticando com: {CREDENTIALS_PATH}")
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    print("  ✓ Autenticado.")

    # Abrir ou criar planilha
    if SPREADSHEET_ID:
        print(f"\n→ Abrindo planilha existente: {SPREADSHEET_ID}")
        try:
            spreadsheet = gc.open_by_key(SPREADSHEET_ID)
            print(f"  ✓ Planilha encontrada: '{spreadsheet.title}'")
        except Exception as e:
            print(f"  [ERRO] Não foi possível abrir a planilha: {e}")
            sys.exit(1)
    else:
        print(f"\n→ Criando nova planilha '{SPREADSHEET_NAME}'...")
        spreadsheet = gc.create(SPREADSHEET_NAME)
        print(f"  ✓ Planilha criada!")
        print(f"\n{'='*60}")
        print(f"  SPREADSHEET_ID = {spreadsheet.id}")
        print(f"  Copie esse ID para o seu .env!")
        print(f"{'='*60}\n")
        # Compartilha apenas com a service account (já tem acesso por ser a criadora).
        # NÃO torna público — dados financeiros devem ser privados.

    # Criar/verificar todas as abas
    print("\n→ Configurando abas...")
    worksheets = {}
    for sheet_name, headers in SHEETS_HEADERS.items():
        worksheets[sheet_name] = _ensure_sheet(spreadsheet, sheet_name, headers)

    # Remover a Sheet1 padrão se existir e não for uma das nossas
    try:
        sheet1 = spreadsheet.worksheet("Sheet1")
        if sheet1.title not in SHEETS_HEADERS:
            spreadsheet.del_worksheet(sheet1)
            print("  - Aba 'Sheet1' padrão removida.")
    except gspread.exceptions.WorksheetNotFound:
        pass

    # Preencher config inicial (apenas se aba estiver vazia)
    print("\n→ Configurando valores iniciais (config)...")
    ws_config = worksheets["config"]
    existing_config = ws_config.get_all_records(numericise_ignore=["all"])
    existing_keys = {r["chave"] for r in existing_config}
    rows_to_add = []
    for chave, valor in CONFIG_INICIAL:
        if chave not in existing_keys:
            rows_to_add.append([chave, valor])
    if rows_to_add:
        ws_config.append_rows(rows_to_add)
        print(f"  ✓ {len(rows_to_add)} configurações inseridas.")
    else:
        print("  ✓ Config já populada — nenhuma alteração.")

    # Preencher categorias padrão
    print("\n→ Configurando categorias padrão...")
    ws_cat = worksheets["categorias"]
    existing_cats = ws_cat.get_all_records(numericise_ignore=["all"])
    existing_nomes = {r["nome"] for r in existing_cats}
    cat_rows = []
    for nome, icone in CATEGORIAS_PADRAO:
        if nome not in existing_nomes:
            cat_rows.append([_new_id(), nome, icone, "True", _now()])
    if cat_rows:
        ws_cat.append_rows(cat_rows)
        print(f"  ✓ {len(cat_rows)} categorias inseridas.")
    else:
        print("  ✓ Categorias já populadas — nenhuma alteração.")

    # Preencher fontes de renda padrão
    print("\n→ Configurando fontes de renda padrão...")
    ws_fontes = worksheets["fontes_renda"]
    existing_fontes = ws_fontes.get_all_records(numericise_ignore=["all"])
    existing_fontes_nomes = {r["nome"] for r in existing_fontes}
    fonte_rows = []
    for nome in FONTES_PADRAO:
        if nome not in existing_fontes_nomes:
            fonte_rows.append([_new_id(), nome, "True", _now()])
    if fonte_rows:
        ws_fontes.append_rows(fonte_rows)
        print(f"  ✓ {len(fonte_rows)} fontes inseridas.")
    else:
        print("  ✓ Fontes já populadas — nenhuma alteração.")

    # Resumo final
    print("\n" + "=" * 60)
    print("  Setup concluído com sucesso!")
    print(f"  URL da planilha:")
    print(f"  https://docs.google.com/spreadsheets/d/{spreadsheet.id}")
    if not SPREADSHEET_ID:
        print(f"\n  Adicione ao .env:")
        print(f"  SPREADSHEET_ID={spreadsheet.id}")
    print("=" * 60)


if __name__ == "__main__":
    main()

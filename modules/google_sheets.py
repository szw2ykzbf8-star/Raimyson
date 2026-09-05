import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
from config import CREDENTIALS_FILE, SCOPES, SPREADSHEET_NAME, SHEETS


@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource
def get_spreadsheet():
    client = get_client()
    try:
        sh = client.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = client.create(SPREADSHEET_NAME)
        _inicializar_abas(sh)
        return sh
    _garantir_abas(sh)
    return sh


def get_sheet(nome_chave: str):
    sh = get_spreadsheet()
    nome_aba = SHEETS[nome_chave]
    try:
        return sh.worksheet(nome_aba)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=nome_aba, rows=1000, cols=30)
        ws.update([_cabecalhos().get(nome_aba, [])])
        return ws


def ler_df(nome_chave: str) -> pd.DataFrame:
    ws = get_sheet(nome_chave)
    data = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
    return pd.DataFrame(data)


def escrever_df(nome_chave: str, df: pd.DataFrame):
    ws = get_sheet(nome_chave)
    ws.clear()
    ws.update([df.columns.tolist()] + df.values.tolist())


def append_linha(nome_chave: str, linha: list):
    ws = get_sheet(nome_chave)
    ws.append_row(linha)


def atualizar_celula(nome_chave: str, row: int, col: int, valor):
    ws = get_sheet(nome_chave)
    ws.update_cell(row, col, valor)


def _cabecalhos():
    return {
        "Produtos": ["id", "descricao", "apresentacao", "unidade_base", "qtd_base_por_apresentacao", "observacao", "ativo", "data_cadastro"],
        "Fornecedores": ["id", "razao_social", "cnpj", "nome_contato", "telefone", "ativo", "data_cadastro"],
        "Unidades": ["id", "nome", "cnpj", "ativo"],
        "Usuarios": ["id", "nome", "login", "senha_hash", "perfil", "unidades_acesso", "ativo"],
        "Pedidos": ["id", "unidade", "status", "criado_por", "data_criacao", "data_bloqueio"],
        "ItensPedido": ["id", "pedido_id", "produto_id", "quantidade"],
        "Cotacoes": ["id", "data_criacao", "prazo_limite", "status", "criado_por"],
        "RespostasFornecedores": ["id", "cotacao_id", "fornecedor_id", "produto_id", "preco", "tipo_embalagem", "qtd_por_embalagem", "observacao", "data_resposta"],
        "Compras": ["id", "cotacao_id", "fornecedor_id", "data_compra", "valor_total", "pedido_gerado"],
        "ItensCompra": ["id", "compra_id", "produto_id", "quantidade", "preco_unitario", "preco_normalizado", "fator"],
        "Orcamentos": ["id", "unidade", "mes", "ano", "valor"],
        "HistoricoPrecos": ["id", "produto_id", "fornecedor_id", "cotacao_id", "preco", "tipo_embalagem", "qtd_por_embalagem", "preco_normalizado", "ganhou", "data"],
        "UnidadesMedida": ["id", "nome", "ativo"],
    }


def _inicializar_abas(sh):
    cabecalhos = _cabecalhos()
    aba_padrao = sh.sheet1
    primeira_chave = list(cabecalhos.keys())[0]
    aba_padrao.update_title(primeira_chave)
    aba_padrao.update([cabecalhos[primeira_chave]])

    for nome, cols in list(cabecalhos.items())[1:]:
        ws = sh.add_worksheet(title=nome, rows=1000, cols=len(cols) + 5)
        ws.update([cols])


_UNIDADES_MEDIDA_PADRAO = [
    [1, "kg",      True],
    [2, "litro",   True],
    [3, "unidade", True],
    [4, "metro",   True],
]


def _garantir_abas(sh):
    """Ensure all tabs exist with proper headers; handles schema migrations safely."""
    cabecalhos = _cabecalhos()
    abas_existentes = {ws.title: ws for ws in sh.worksheets()}

    for nome, cols in cabecalhos.items():
        if nome not in abas_existentes:
            ws = sh.add_worksheet(title=nome, rows=1000, cols=len(cols) + 5)
            ws.update([cols])
            if nome == "UnidadesMedida":
                ws.append_rows(_UNIDADES_MEDIDA_PADRAO)
        else:
            ws = abas_existentes[nome]
            primeira_linha = ws.row_values(1)
            if primeira_linha != cols:
                # Wrong or missing headers. If there's data in row 2+, insert above it.
                # If the tab is empty/header-only, just overwrite row 1 (schema migration).
                tem_dados = bool(ws.row_values(2))
                if tem_dados:
                    ws.insert_row(cols, index=1)
                else:
                    ws.update([cols])

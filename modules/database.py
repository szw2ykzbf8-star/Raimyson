import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

COLUMNS = {
    "produtos":          ["id", "descricao", "apresentacao", "unidade_base", "qtd_base_por_apresentacao", "observacao", "ativo", "data_cadastro", "codigo"],
    "fornecedores":      ["id", "razao_social", "cnpj", "nome_contato", "telefone", "ativo", "data_cadastro", "nome_fantasia", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado", "pedido_minimo"],
    "unidades":          ["id", "nome", "nome_fantasia", "cnpj", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado", "ativo"],
    "usuarios":          ["id", "nome", "login", "senha_hash", "perfil", "unidades_acesso", "ativo", "trocar_senha", "permissoes"],
    "pedidos":           ["id", "unidade", "status", "criado_por", "data_criacao", "data_bloqueio", "cotacao_id"],
    "itens_pedido":      ["id", "pedido_id", "produto_id", "quantidade"],
    "cotacoes":          ["id", "data_criacao", "prazo_limite", "status", "criado_por", "nome"],
    "respostas":         ["id", "cotacao_id", "fornecedor_id", "produto_id", "preco", "tipo_embalagem", "qtd_por_embalagem", "observacao", "data_resposta"],
    "compras":           ["id", "cotacao_id", "fornecedor_id", "data_compra", "valor_total", "pedido_gerado", "nfe_chave", "nfe_numero", "status_recebimento", "unidade"],
    "itens_compra":      ["id", "compra_id", "produto_id", "quantidade", "preco_unitario", "preco_normalizado", "fator"],
    "orcamentos":        ["id", "unidade", "mes", "ano", "valor"],
    "historico_precos":  ["id", "produto_id", "fornecedor_id", "cotacao_id", "preco", "tipo_embalagem", "qtd_por_embalagem", "preco_normalizado", "ganhou", "data"],
    "unidades_medida":   ["id", "nome", "descricao", "ativo"],
    "itens_recebimento": ["id", "compra_id", "produto_id", "qtd_pedida", "qtd_recebida"],
    "nfe_mapeamento":    ["id", "fornecedor_id", "nfe_cprod", "produto_id"],
    "cotacao_tokens":    ["id", "cotacao_id", "fornecedor_id", "token"],
}

_SEED_UNIDADES_MEDIDA = [
    ["1", "kg", "Kilograma", "True"],
    ["2", "lt", "Litro",     "True"],
    ["3", "un", "Unidade",   "True"],
    ["4", "mt", "Metro",     "True"],
]


@st.cache_resource
def get_engine():
    url = os.environ["DATABASE_URL"]
    # Force psycopg2 dialect (SQLAlchemy 2.x defaults to psycopg v3 otherwise)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    _criar_tabelas(engine)
    return engine


def _criar_tabelas(engine):
    with engine.begin() as conn:
        for tabela, cols in COLUMNS.items():
            col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
            conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{tabela}" ({col_defs})'))
    # Migrate: add nome column to cotacoes if missing
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE \"cotacoes\" ADD COLUMN IF NOT EXISTS \"nome\" TEXT DEFAULT ''"))

    # Seed unidades_medida when empty
    with engine.begin() as conn:
        r = conn.execute(text('SELECT COUNT(*) FROM "unidades_medida"'))
        if r.scalar() == 0:
            cols_str = ", ".join(f'"{c}"' for c in COLUMNS["unidades_medida"])
            for row in _SEED_UNIDADES_MEDIDA:
                placeholders = ", ".join(f":p{i}" for i in range(len(row)))
                params = {f"p{i}": v for i, v in enumerate(row)}
                conn.execute(text(f'INSERT INTO "unidades_medida" ({cols_str}) VALUES ({placeholders})'), params)


@st.cache_data(ttl=120)
def ler_df(nome_chave: str) -> pd.DataFrame:
    engine = get_engine()
    cols = COLUMNS.get(nome_chave, [])
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT * FROM "{nome_chave}"'))
        rows = result.fetchall()
        col_names = list(result.keys())
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows, columns=col_names)
    for col in df.columns:
        if str(df[col].dtype).startswith("string"):
            df[col] = df[col].astype(object)
    return df


def escrever_df(nome_chave: str, df: pd.DataFrame):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM "{nome_chave}"'))
        if not df.empty:
            cols = df.columns.tolist()
            col_str = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(f":p{i}" for i in range(len(cols)))
            stmt = text(f'INSERT INTO "{nome_chave}" ({col_str}) VALUES ({placeholders})')
            rows_data = [
                {f"p{i}": str(v) if v is not None and str(v) != "nan" else ""
                 for i, v in enumerate(row)}
                for row in df.values.tolist()
            ]
            conn.execute(stmt, rows_data)


def append_linha(nome_chave: str, linha: list):
    engine = get_engine()
    cols = COLUMNS[nome_chave][:len(linha)]
    col_str = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(f":p{i}" for i in range(len(linha)))
    params = {f"p{i}": str(v) if v is not None else "" for i, v in enumerate(linha)}
    with engine.begin() as conn:
        conn.execute(text(f'INSERT INTO "{nome_chave}" ({col_str}) VALUES ({placeholders})'), params)


def atualizar_celula(nome_chave: str, row: int, col: int, valor):
    pass  # row/col addressing not used in PostgreSQL mode


class TableProxy:
    def __init__(self, nome_chave: str):
        self.nome_chave = nome_chave

    def append_rows(self, linhas: list):
        if not linhas:
            return
        engine = get_engine()
        n = len(linhas[0])
        cols = COLUMNS[self.nome_chave][:n]
        col_str = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(f":p{i}" for i in range(n))
        stmt = text(f'INSERT INTO "{self.nome_chave}" ({col_str}) VALUES ({placeholders})')
        rows_data = [
            {f"p{i}": str(v) if v is not None else "" for i, v in enumerate(row)}
            for row in linhas
        ]
        with engine.begin() as conn:
            conn.execute(stmt, rows_data)


def get_sheet(nome_chave: str) -> TableProxy:
    return TableProxy(nome_chave)

import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

COLUMNS = {
    "produtos":          ["id", "descricao", "apresentacao", "unidade_base", "qtd_base_por_apresentacao", "observacao", "ativo", "data_cadastro", "codigo", "compra_direta", "categoria"],
    "categorias":        ["id", "nome"],
    "fornecedores":      ["id", "razao_social", "cnpj", "nome_contato", "telefone", "ativo", "data_cadastro", "nome_fantasia", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado", "pedido_minimo"],
    "unidades":          ["id", "nome", "nome_fantasia", "cnpj", "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado", "ativo"],
    "usuarios":          ["id", "nome", "login", "senha_hash", "perfil", "unidades_acesso", "ativo", "trocar_senha", "permissoes"],
    "pedidos":           ["id", "unidade", "status", "criado_por", "data_criacao", "data_bloqueio", "cotacao_id", "editado_por", "data_edicao"],
    "itens_pedido":      ["id", "pedido_id", "produto_id", "quantidade", "qtd_original"],
    "cotacoes":          ["id", "data_criacao", "prazo_limite", "status", "criado_por", "nome"],
    "respostas":         ["id", "cotacao_id", "fornecedor_id", "produto_id", "preco", "tipo_embalagem", "qtd_por_embalagem", "observacao", "marca", "data_resposta"],
    "compras":           ["id", "cotacao_id", "fornecedor_id", "data_compra", "valor_total", "pedido_gerado", "nfe_chave", "nfe_numero", "status_recebimento", "unidade"],
    "itens_compra":      ["id", "compra_id", "produto_id", "quantidade", "preco_unitario", "preco_normalizado", "fator"],
    "orcamentos":        ["id", "unidade", "mes", "ano", "valor"],
    "historico_precos":  ["id", "produto_id", "fornecedor_id", "cotacao_id", "preco", "tipo_embalagem", "qtd_por_embalagem", "preco_normalizado", "ganhou", "data"],
    "unidades_medida":   ["id", "nome", "descricao", "ativo"],
    "itens_recebimento": ["id", "compra_id", "produto_id", "qtd_pedida", "qtd_recebida"],
    "nfe_mapeamento":    ["id", "fornecedor_id", "nfe_cprod", "produto_id"],
    "cotacao_tokens":    ["id", "cotacao_id", "fornecedor_id", "token"],
    "compras_diretas":   ["id", "cotacao_id", "produto_id", "unidade", "quantidade", "comprado"],
    "rascunhos":         ["token", "dados_json", "salvo_em"],
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
    # Migrations
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE \"cotacoes\" ADD COLUMN IF NOT EXISTS \"nome\" TEXT DEFAULT ''"))
        conn.execute(text("ALTER TABLE \"respostas\" ADD COLUMN IF NOT EXISTS \"marca\" TEXT DEFAULT ''"))
        conn.execute(text("ALTER TABLE \"produtos\" ADD COLUMN IF NOT EXISTS \"compra_direta\" TEXT DEFAULT 'False'"))
        conn.execute(text("ALTER TABLE \"produtos\" ADD COLUMN IF NOT EXISTS \"categoria\" TEXT DEFAULT ''"))
        conn.execute(text("ALTER TABLE \"pedidos\" ADD COLUMN IF NOT EXISTS \"editado_por\" TEXT DEFAULT ''"))
        conn.execute(text("ALTER TABLE \"pedidos\" ADD COLUMN IF NOT EXISTS \"data_edicao\" TEXT DEFAULT ''"))
        conn.execute(text("ALTER TABLE \"cotacoes\" ADD COLUMN IF NOT EXISTS \"observacoes_compra\" TEXT DEFAULT ''"))
        conn.execute(text("ALTER TABLE \"itens_pedido\" ADD COLUMN IF NOT EXISTS \"qtd_original\" TEXT DEFAULT ''"))

    # Seed unidades_medida when empty
    with engine.begin() as conn:
        r = conn.execute(text('SELECT COUNT(*) FROM "unidades_medida"'))
        if r.scalar() == 0:
            cols_str = ", ".join(f'"{c}"' for c in COLUMNS["unidades_medida"])
            for row in _SEED_UNIDADES_MEDIDA:
                placeholders = ", ".join(f":p{i}" for i in range(len(row)))
                params = {f"p{i}": v for i, v in enumerate(row)}
                conn.execute(text(f'INSERT INTO "unidades_medida" ({cols_str}) VALUES ({placeholders})'), params)

    # Seed categorias when empty
    with engine.begin() as conn:
        r = conn.execute(text('SELECT COUNT(*) FROM "categorias"'))
        if r.scalar() == 0:
            from config import CATEGORIAS_PRODUTOS as _CATS
            for idx, nome in enumerate(_CATS, start=1):
                conn.execute(
                    text('INSERT INTO "categorias" ("id", "nome") VALUES (:id, :nome)'),
                    {"id": str(idx), "nome": nome},
                )


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


def atualizar_linha(nome_chave: str, id_valor: str, campos: dict):
    """UPDATE single row by id — much faster than escrever_df for single edits."""
    engine = get_engine()
    set_clause = ", ".join(f'"{c}" = :v{i}' for i, c in enumerate(campos))
    params = {f"v{i}": str(v) if v is not None else "" for i, v in enumerate(campos.values())}
    params["_id"] = str(id_valor)
    with engine.begin() as conn:
        conn.execute(
            text(f'UPDATE "{nome_chave}" SET {set_clause} WHERE "id" = :_id'),
            params,
        )


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
        # Build single multi-row INSERT to avoid N round-trips via executemany
        params = {}
        value_groups = []
        for row_i, row in enumerate(linhas):
            placeholders = ", ".join(f":r{row_i}c{col_i}" for col_i in range(n))
            value_groups.append(f"({placeholders})")
            for col_i, v in enumerate(row):
                params[f"r{row_i}c{col_i}"] = str(v) if v is not None else ""
        sql = f'INSERT INTO "{self.nome_chave}" ({col_str}) VALUES {", ".join(value_groups)}'
        with engine.begin() as conn:
            conn.execute(text(sql), params)


def get_sheet(nome_chave: str) -> TableProxy:
    return TableProxy(nome_chave)

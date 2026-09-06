import json
import uuid
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from src.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID, SHEETS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


@st.cache_resource
def get_client():
    if GOOGLE_CREDENTIALS_JSON:
        info  = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet():
    return get_client().open_by_key(SPREADSHEET_ID)


def _sheet(name: str):
    return get_spreadsheet().worksheet(name)


def ensure_sheet(name: str, headers: list) -> None:
    """Cria a aba com cabeçalhos se ela não existir. Idempotente."""
    sp = get_spreadsheet()
    try:
        sp.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        ws = sp.add_worksheet(title=name, rows=1000, cols=len(headers))
        ws.append_row(headers)
        invalidate_by_name(name)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def _find_row(ws: gspread.Worksheet, value: str, col: int = 1) -> int:
    """Retorna o número de linha (1-indexado) onde value aparece na coluna col.
    Lança ValueError se não encontrado. Sempre consulta o Sheets em tempo real,
    evitando o uso de índices de cache que podem estar desatualizados."""
    cell = ws.find(value, in_column=col)
    if cell is None:
        raise ValueError(f"Valor '{value}' não encontrado na coluna {col}")
    return cell.row


# ─── Cache por sessão ────────────────────────────────────────────────────────


def _cache_key(name: str) -> str:
    return f"_sheet_cache_{name}"


def get_df(sheet_key: str, force: bool = False) -> pd.DataFrame:
    name = SHEETS[sheet_key]
    key  = _cache_key(name)
    if force or key not in st.session_state:
        ws   = _sheet(name)
        data = ws.get_all_records(numericise_ignore=["all"])
        st.session_state[key] = pd.DataFrame(data) if data else pd.DataFrame()
    return st.session_state[key]


def invalidate(sheet_key: str):
    name = SHEETS[sheet_key]
    st.session_state.pop(_cache_key(name), None)


def invalidate_by_name(name: str):
    st.session_state.pop(_cache_key(name), None)


# ─── Config ──────────────────────────────────────────────────────────────────


def get_config(chave: str, default=None):
    df = get_df("config")
    if df.empty:
        return default
    row = df[df["chave"] == chave]
    return row["valor"].iloc[0] if not row.empty else default


def set_config(chave: str, valor: str):
    ws = _sheet(SHEETS["config"])
    try:
        row_num = _find_row(ws, chave, col=1)
        ws.update_cell(row_num, 2, valor)
    except ValueError:
        ws.append_row([chave, valor])
    invalidate("config")


# ─── Categorias ──────────────────────────────────────────────────────────────


def get_categorias(apenas_ativas: bool = True) -> pd.DataFrame:
    df = get_df("categorias")
    if df.empty:
        return df
    if apenas_ativas:
        df = df[df["ativo"] == "True"]
    return df


def add_categoria(nome: str, icone: str = "📦") -> str:
    ws  = _sheet(SHEETS["categorias"])
    rid = new_id()
    ws.append_row([rid, nome, icone, "True", _now()])
    invalidate("categorias")
    return rid


def delete_categoria(rid: str):
    ws      = _sheet(SHEETS["categorias"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 4, "False")
    invalidate("categorias")


# ─── Fontes de Renda ─────────────────────────────────────────────────────────


def get_fontes(apenas_ativas: bool = True) -> pd.DataFrame:
    df = get_df("fontes")
    if df.empty:
        return df
    if apenas_ativas:
        df = df[df["ativo"] == "True"]
    return df


def add_fonte(nome: str) -> str:
    ws  = _sheet(SHEETS["fontes"])
    rid = new_id()
    ws.append_row([rid, nome, "True", _now()])
    invalidate("fontes")
    return rid


def delete_fonte(rid: str):
    ws      = _sheet(SHEETS["fontes"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 3, "False")
    invalidate("fontes")


# ─── Contas Bancárias ────────────────────────────────────────────────────────


def get_contas(apenas_ativas: bool = True) -> pd.DataFrame:
    df = get_df("contas")
    if df.empty:
        return df
    if apenas_ativas:
        df = df[df["ativo"] == "True"]
    return df


def add_conta(nome: str, tipo: str, saldo_inicial: float = 0.0) -> str:
    ws  = _sheet(SHEETS["contas"])
    rid = new_id()
    ws.append_row([rid, nome, tipo, str(saldo_inicial), "True", _now()])
    invalidate("contas")
    return rid


def delete_conta(rid: str):
    ws      = _sheet(SHEETS["contas"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 5, "False")
    invalidate("contas")


# ─── Cartões ─────────────────────────────────────────────────────────────────


def get_cartoes(apenas_ativos: bool = True) -> pd.DataFrame:
    df = get_df("cartoes")
    if df.empty:
        return df
    if apenas_ativos:
        df = df[df["ativo"] == "True"]
    return df


def add_cartao(nome: str, dia_fechamento: int, dia_vencimento: int) -> str:
    ws  = _sheet(SHEETS["cartoes"])
    rid = new_id()
    ws.append_row([rid, nome, str(dia_fechamento), str(dia_vencimento), "True", _now()])
    invalidate("cartoes")
    return rid


def delete_cartao(rid: str):
    ws      = _sheet(SHEETS["cartoes"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 5, "False")
    invalidate("cartoes")


# ─── Contas Fixas ────────────────────────────────────────────────────────────


def get_fixas(apenas_ativas: bool = True) -> pd.DataFrame:
    df = get_df("fixas")
    if df.empty:
        return df
    if apenas_ativas:
        df = df[df["ativo"] == "True"]
    return df


def add_fixa(nome: str, valor_ref: float, categoria: str, forma_pgto: str,
             conta_cartao: str, dia_venc: int, mes_inicio: str) -> str:
    ws  = _sheet(SHEETS["fixas"])
    rid = new_id()
    ws.append_row([rid, nome, str(valor_ref), categoria, forma_pgto,
                   conta_cartao, str(dia_venc), "True", mes_inicio, "", _now()])
    invalidate("fixas")
    return rid


def delete_fixa(rid: str):
    ws      = _sheet(SHEETS["fixas"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 8, "False")
    invalidate("fixas")


def update_fixa_valor(rid: str, novo_valor: float):
    ws      = _sheet(SHEETS["fixas"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 3, str(novo_valor))
    invalidate("fixas")


# ─── Dívidas ─────────────────────────────────────────────────────────────────


def get_dividas(apenas_ativas: bool = True) -> pd.DataFrame:
    df = get_df("dividas")
    if df.empty:
        return df
    if apenas_ativas:
        df = df[df["ativo"] == "True"]
    return df


def add_divida(nome: str, valor_original: float, valor_parcela: float,
               num_parcelas: int, data_inicio: str, forma_pgto: str,
               conta_cartao: str, fonte_ajuda: str) -> str:
    ws  = _sheet(SHEETS["dividas"])
    rid = new_id()
    ws.append_row([rid, nome, str(valor_original), str(valor_parcela),
                   str(num_parcelas), "0", data_inicio, forma_pgto,
                   conta_cartao, fonte_ajuda, "True", _now()])
    invalidate("dividas")
    return rid


def registrar_pagamento_divida(divida_id: str, valor_pago: float,
                                data: str, is_antecipacao: bool,
                                num_antecipadas: int, economia: float,
                                descricao: str = "") -> str:
    ws  = _sheet(SHEETS["pgtos_divida"])
    rid = new_id()
    ws.append_row([rid, divida_id, data, str(valor_pago),
                   str(is_antecipacao), str(num_antecipadas),
                   str(economia), descricao, _now()])
    # Incrementa num_parcelas_pagas buscando a linha em tempo real
    ws_d      = _sheet(SHEETS["dividas"])
    row_num_d = _find_row(ws_d, divida_id)
    pagas_str = ws_d.cell(row_num_d, 6).value or "0"
    pagas     = int(pagas_str)
    novas_pagas = pagas + (num_antecipadas if is_antecipacao else 1)
    ws_d.update_cell(row_num_d, 6, str(novas_pagas))
    invalidate("dividas")
    invalidate("pgtos_divida")
    return rid


def get_pgtos_divida(divida_id: str = None) -> pd.DataFrame:
    df = get_df("pgtos_divida")
    if df.empty:
        return df
    if divida_id:
        df = df[df["divida_id"] == divida_id]
    return df


def delete_divida(rid: str):
    ws      = _sheet(SHEETS["dividas"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 11, "False")
    invalidate("dividas")


# ─── Investimentos ───────────────────────────────────────────────────────────


def get_investimentos(status: str = None) -> pd.DataFrame:
    df = get_df("investimentos")
    if df.empty:
        return df
    if status:
        df = df[df["status"] == status]
    return df


def add_investimento(nome: str, tipo: str, data_aplicacao: str,
                     valor_aplicado: float, taxa_tipo: str,
                     taxa_valor: float, data_vencimento: str,
                     conta_origem: str = "") -> str:
    ws  = _sheet(SHEETS["investimentos"])
    rid = new_id()
    ws.append_row([rid, nome, tipo, data_aplicacao, str(valor_aplicado),
                   taxa_tipo, str(taxa_valor), data_vencimento,
                   "", "", "ATIVO", _now(), conta_origem])
    invalidate("investimentos")
    return rid


def retirar_investimento(rid: str, valor_retirado: float, data_retirada: str):
    ws      = _sheet(SHEETS["investimentos"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 9,  str(valor_retirado))
    ws.update_cell(row_num, 10, data_retirada)
    ws.update_cell(row_num, 11, "RETIRADO")
    invalidate("investimentos")


def delete_investimento(rid: str):
    ws      = _sheet(SHEETS["investimentos"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 11, "EXCLUIDO")
    invalidate("investimentos")


# ─── Criptos ─────────────────────────────────────────────────────────────────


def get_criptos(status: str = None) -> pd.DataFrame:
    df = get_df("criptos")
    if df.empty:
        return df
    if status:
        df = df[df["status"] == status]
    return df


def add_cripto(moeda: str, simbolo: str, quantidade: float, preco_compra_brl: float,
               data_compra: str, exchange: str, conta_origem: str) -> str:
    ws  = _sheet(SHEETS["criptos"])
    rid = new_id()
    ws.append_row([rid, moeda, simbolo, str(quantidade), str(preco_compra_brl),
                   data_compra, exchange, conta_origem, "", "", "ATIVO", _now()])
    invalidate("criptos")
    return rid


def vender_cripto(rid: str, preco_venda_brl: float, data_venda: str):
    ws      = _sheet(SHEETS["criptos"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 9,  str(preco_venda_brl))
    ws.update_cell(row_num, 10, data_venda)
    ws.update_cell(row_num, 11, "VENDIDO")
    invalidate("criptos")


def delete_cripto(rid: str):
    ws      = _sheet(SHEETS["criptos"])
    row_num = _find_row(ws, rid)
    ws.update_cell(row_num, 11, "EXCLUIDO")
    invalidate("criptos")


# ─── Entradas ────────────────────────────────────────────────────────────────


def get_entradas(mes: str = None) -> pd.DataFrame:
    df = get_df("entradas")
    if df.empty:
        return df
    if mes:
        df = df[df["data"].str.startswith(mes)]
    return df


def add_entrada(data: str, valor: float, fonte: str,
                conta: str, descricao: str = "") -> str:
    ws  = _sheet(SHEETS["entradas"])
    rid = new_id()
    ws.append_row([rid, data, str(valor), fonte, conta, descricao, _now()])
    invalidate("entradas")
    return rid


def delete_entrada(rid: str):
    ws      = _sheet(SHEETS["entradas"])
    row_num = _find_row(ws, rid)
    ws.delete_rows(row_num)
    invalidate("entradas")


# ─── Gastos ──────────────────────────────────────────────────────────────────


def get_gastos(mes: str = None) -> pd.DataFrame:
    df = get_df("gastos")
    if df.empty:
        return df
    if mes:
        df = df[df["mes_referencia"] == mes]
    return df


def add_gasto(data_compra: str, data_fatura: str, mes_ref: str,
              parcela_num: int, total_parcelas: int, valor_parcela: float,
              valor_total: float, categoria: str, forma_pgto: str,
              conta_cartao: str, descricao: str = "",
              id_grupo: str = None) -> str:
    ws  = _sheet(SHEETS["gastos"])
    rid = new_id()
    gid = id_grupo or rid
    ws.append_row([rid, gid, data_compra, data_fatura, mes_ref,
                   str(parcela_num), str(total_parcelas),
                   str(valor_parcela), str(valor_total),
                   categoria, forma_pgto, conta_cartao, descricao, _now()])
    invalidate("gastos")
    return rid


def delete_gasto(rid: str):
    ws      = _sheet(SHEETS["gastos"])
    row_num = _find_row(ws, rid)
    ws.delete_rows(row_num)
    invalidate("gastos")


def delete_gasto_grupo(id_grupo: str):
    ws = _sheet(SHEETS["gastos"])
    # Força leitura fresca para ter row numbers corretos
    df = get_df("gastos", force=True)
    rows = df[df["id_grupo"] == id_grupo].index.tolist()
    # Busca o número real de linha de cada parcela e deleta de baixo para cima
    row_nums = []
    for idx in rows:
        rid = df.loc[idx, "id"]
        try:
            row_nums.append(_find_row(ws, rid))
        except ValueError:
            pass
    for rn in sorted(row_nums, reverse=True):
        ws.delete_rows(rn)
    invalidate("gastos")


# ─── Pagamentos de Contas e Faturas ──────────────────────────────────────────


def get_pagamentos_contas(mes: str = None) -> pd.DataFrame:
    df = get_df("pgtos_contas")
    if df.empty:
        return df
    if mes:
        df = df[df["mes_referencia"] == mes]
    return df


def add_pagamento_conta(tipo: str, referencia_id: str, nome: str, mes: str,
                        valor: float, conta_debito: str, data_pagamento: str) -> str:
    ws  = _sheet(SHEETS["pgtos_contas"])
    rid = new_id()
    ws.append_row([rid, tipo, referencia_id, nome, mes,
                   str(valor), conta_debito, data_pagamento, _now()])
    invalidate("pgtos_contas")
    return rid


def delete_pagamento_conta(rid: str):
    ws      = _sheet(SHEETS["pgtos_contas"])
    row_num = _find_row(ws, rid)
    ws.delete_rows(row_num)
    invalidate("pgtos_contas")


# ─── Transferências ──────────────────────────────────────────────────────────


def get_transferencias(mes: str = None) -> pd.DataFrame:
    df = get_df("transferencias")
    if df.empty:
        return df
    if mes:
        df = df[df["data"].str.startswith(mes)]
    return df


def add_transferencia(data: str, valor: float, conta_origem: str,
                      conta_destino: str, descricao: str = "") -> str:
    ws  = _sheet(SHEETS["transferencias"])
    rid = new_id()
    ws.append_row([rid, data, str(valor), conta_origem, conta_destino, descricao, _now()])
    invalidate("transferencias")
    return rid


def delete_transferencia(rid: str):
    ws      = _sheet(SHEETS["transferencias"])
    row_num = _find_row(ws, rid)
    ws.delete_rows(row_num)
    invalidate("transferencias")

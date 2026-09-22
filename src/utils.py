import calendar
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd


# ─── Dias úteis (CDI/CDB) ────────────────────────────────────────────────────

def _pascoa(ano: int) -> date:
    """Algoritmo Meeus/Jones/Butcher para calcular a data da Páscoa."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def _feriados_br(ano: int) -> frozenset:
    """Feriados nacionais brasileiros para o ano, incluindo Carnaval e Corpus Christi."""
    fixos = {
        date(ano, 1, 1), date(ano, 4, 21), date(ano, 5, 1),
        date(ano, 9, 7), date(ano, 10, 12), date(ano, 11, 2),
        date(ano, 11, 15), date(ano, 12, 25),
    }
    pascoa = _pascoa(ano)
    moveis = {
        pascoa - timedelta(days=48),  # Segunda de Carnaval
        pascoa - timedelta(days=47),  # Terça de Carnaval
        pascoa - timedelta(days=2),   # Sexta-Feira Santa
        pascoa + timedelta(days=60),  # Corpus Christi
    }
    return frozenset(fixos | moveis)


def _proximo_dia_util(d: date) -> date:
    """Retorna d se for dia útil; caso contrário, avança até o próximo dia útil."""
    feriados = _feriados_br(d.year)
    while d.weekday() >= 5 or d in feriados:
        d += timedelta(days=1)
        if d.year != (d - timedelta(days=1)).year:
            feriados = _feriados_br(d.year)
    return d


def _contar_dias_uteis(ini: date, fim: date) -> int:
    """Conta dias úteis em [ini, fim) — ini inclusive, fim exclusive."""
    if fim <= ini:
        return 0
    count = 0
    d = ini
    feriados = _feriados_br(d.year)
    while d < fim:
        if d.weekday() < 5 and d not in feriados:
            count += 1
        d += timedelta(days=1)
        if d < fim and d.year != (d - timedelta(days=1)).year:
            feriados = _feriados_br(d.year)
    return count


# ─── Datas ───────────────────────────────────────────────────────────────────


def mes_atual() -> str:
    return date.today().strftime("%Y-%m")


def mes_str(ano: int, mes: int) -> str:
    return f"{ano:04d}-{mes:02d}"


def proximo_mes(mes: str) -> str:
    d = date(int(mes[:4]), int(mes[5:7]), 1)
    d2 = d + relativedelta(months=1)
    return mes_str(d2.year, d2.month)


def mes_anterior(mes: str) -> str:
    d = date(int(mes[:4]), int(mes[5:7]), 1)
    d2 = d - relativedelta(months=1)
    return mes_str(d2.year, d2.month)


def formatar_mes(mes: str) -> str:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{meses[int(mes[5:7]) - 1]} {mes[:4]}"


def ultimos_meses(n: int) -> list[str]:
    resultado = []
    atual = mes_atual()
    for _ in range(n):
        resultado.insert(0, atual)
        atual = mes_anterior(atual)
    return resultado


# ─── Cartão: ciclo e data de fatura ──────────────────────────────────────────


def calcular_data_fatura(data_compra: date, dia_fechamento: int, dia_vencimento: int) -> date:
    """
    Retorna a data de vencimento da fatura em que a compra cai.
    Regra: ciclo começa no dia_fechamento. Compra no dia_fechamento ou depois
    vai para o próximo ciclo.
    """
    compra_dia = data_compra.day

    if compra_dia >= dia_fechamento:
        base = date(data_compra.year, data_compra.month, 1) + relativedelta(months=1)
    else:
        base = date(data_compra.year, data_compra.month, 1)
    ultimo_fec = calendar.monthrange(base.year, base.month)[1]
    fechamento = base.replace(day=min(dia_fechamento, ultimo_fec))

    # Se dia_vencimento > dia_fechamento, vence no mesmo mês do fechamento
    # (ex: fecha dia 1, vence dia 11 → Sep 1 fecha, Sep 11 vence)
    # Caso contrário, vence no mês seguinte
    # (ex: fecha dia 25, vence dia 5 → Sep 25 fecha, Out 5 vence)
    if dia_vencimento > dia_fechamento:
        venc_base = fechamento
    else:
        venc_base = fechamento + relativedelta(months=1)
    ultimo_venc = calendar.monthrange(venc_base.year, venc_base.month)[1]
    vencimento = venc_base.replace(day=min(dia_vencimento, ultimo_venc))
    return vencimento


def gerar_parcelas(data_compra_str: str, valor_total: float, num_parcelas: int,
                   dia_fechamento: int, dia_vencimento: int) -> list[dict]:
    """Gera lista de parcelas com suas datas de fatura."""
    from math import ceil
    dc = date.fromisoformat(data_compra_str)
    valor_parcela = round(valor_total / num_parcelas, 2)
    # Ajuste de centavos na última parcela
    valor_ultima = round(valor_total - valor_parcela * (num_parcelas - 1), 2)

    parcelas = []
    data_fatura_base = calcular_data_fatura(dc, dia_fechamento, dia_vencimento)

    for i in range(num_parcelas):
        data_fat = data_fatura_base + relativedelta(months=i)
        val = valor_parcela if i < num_parcelas - 1 else valor_ultima
        parcelas.append({
            "parcela_num": i + 1,
            "total_parcelas": num_parcelas,
            "data_fatura": data_fat.isoformat(),
            "mes_referencia": mes_str(data_fat.year, data_fat.month),
            "valor_parcela": val,
            "valor_total": valor_total,
        })
    return parcelas


# ─── Saldo de conta bancária ─────────────────────────────────────────────────


def calcular_saldo_conta_breakdown(conta_nome: str, entradas_df: pd.DataFrame,
                                    gastos_df: pd.DataFrame, transferencias_df: pd.DataFrame,
                                    contas_df: pd.DataFrame,
                                    investimentos_df: pd.DataFrame = None,
                                    pagamentos_df: pd.DataFrame = None,
                                    criptos_df: pd.DataFrame = None) -> dict:
    """Retorna dicionário com todos os componentes do saldo."""
    saldo_inicial = 0.0
    if not contas_df.empty:
        row = contas_df[contas_df["nome"] == conta_nome]
        if not row.empty:
            saldo_inicial = float(row.iloc[0]["saldo_inicial"])

    entradas = 0.0
    if not entradas_df.empty and "conta" in entradas_df.columns:
        mask = entradas_df["conta"] == conta_nome
        entradas = entradas_df[mask]["valor"].astype(float).sum()

    saidas_debito = 0.0
    n_gastos = 0
    if not gastos_df.empty and "conta_cartao" in gastos_df.columns:
        mask = (gastos_df["conta_cartao"] == conta_nome) & \
               (gastos_df["forma_pagamento"].isin(
                   ["Pix", "Débito", "Débito (Cartão)", "Débito em Conta", "Dinheiro", "Boleto"]
               ))
        saidas_debito = gastos_df[mask]["valor_parcela"].astype(float).sum()
        n_gastos = int(mask.sum())

    saidas_transf = 0.0
    entradas_transf = 0.0
    if not transferencias_df.empty:
        mask_out = transferencias_df["conta_origem"] == conta_nome
        mask_in  = transferencias_df["conta_destino"] == conta_nome
        saidas_transf   = transferencias_df[mask_out]["valor"].astype(float).sum()
        entradas_transf = transferencias_df[mask_in]["valor"].astype(float).sum()

    saidas_invest = 0.0
    if investimentos_df is not None and not investimentos_df.empty:
        if "conta_origem" in investimentos_df.columns and "status" in investimentos_df.columns:
            mask_inv = (investimentos_df["conta_origem"] == conta_nome) & \
                       (investimentos_df["status"] == "ATIVO")
            saidas_invest = investimentos_df[mask_inv]["valor_aplicado"].astype(float).sum()

    saidas_pgto = 0.0
    if pagamentos_df is not None and not pagamentos_df.empty and "conta_debito" in pagamentos_df.columns:
        # Apenas faturas de cartão: pagamentos de conta_fixa já impactam via gasto criado
        mask_pgto = (pagamentos_df["conta_debito"] == conta_nome) & \
                    (pagamentos_df["tipo"] == "fatura_cartao")
        saidas_pgto = pagamentos_df[mask_pgto]["valor"].astype(float).sum()

    saidas_cripto = 0.0
    if criptos_df is not None and not criptos_df.empty and "conta_origem" in criptos_df.columns:
        mask_cr = (criptos_df["conta_origem"] == conta_nome) & \
                  (criptos_df["status"] == "ATIVO")
        saidas_cripto = criptos_df[mask_cr]["preco_compra_brl"].astype(float).sum()

    total = (saldo_inicial + entradas + entradas_transf
             - saidas_debito - saidas_transf - saidas_invest - saidas_pgto - saidas_cripto)

    return {
        "saldo_inicial":   saldo_inicial,
        "entradas":        entradas,
        "entradas_transf": entradas_transf,
        "saidas_debito":   saidas_debito,
        "n_gastos":        n_gastos,
        "saidas_transf":   saidas_transf,
        "saidas_invest":   saidas_invest,
        "saidas_pgto":     saidas_pgto,
        "saidas_cripto":   saidas_cripto,
        "total":           total,
    }


def calcular_saldo_conta(conta_nome: str, entradas_df: pd.DataFrame,
                          gastos_df: pd.DataFrame, transferencias_df: pd.DataFrame,
                          contas_df: pd.DataFrame,
                          investimentos_df: pd.DataFrame = None,
                          pagamentos_df: pd.DataFrame = None,
                          criptos_df: pd.DataFrame = None) -> float:
    return calcular_saldo_conta_breakdown(
        conta_nome, entradas_df, gastos_df, transferencias_df, contas_df,
        investimentos_df, pagamentos_df, criptos_df
    )["total"]


# ─── Cálculos de investimento ────────────────────────────────────────────────


def calcular_rendimento(valor_aplicado: float, taxa_tipo: str,
                         taxa_valor: float, data_aplicacao_str: str,
                         data_referencia_str: str = None,
                         cdi_anual: float = 10.75) -> dict:
    """
    taxa_tipo: 'MENSAL' | 'ANUAL' | 'CDI'

    CDI: cálculo preciso por dias úteis com D+1 e feriados nacionais.
      - data_aplicacao é a data da operação; o rendimento começa no próximo
        dia útil (D+1), como nas instituições financeiras brasileiras.
      - taxa_valor = percentual do CDI (ex: 103 = 103% do CDI)
      - cdi_anual = taxa CDI anual em % (padrão 10.75)
      - Fórmula diária: CDI_diario = (1 + cdi_anual/100)^(1/252) - 1
                        taxa_efetiva = CDI_diario * taxa_valor/100
                        VF = VA * (1 + taxa_efetiva)^n_dias_uteis

    MENSAL/ANUAL: cálculo por meses completos (sem alteração).
    """
    da = date.fromisoformat(data_aplicacao_str)
    dr = date.fromisoformat(data_referencia_str) if data_referencia_str else date.today()

    if taxa_tipo == "CDI":
        # D+1: rendimento começa no próximo dia útil após a aplicação
        data_inicio = _proximo_dia_util(da + timedelta(days=1))
        n_du = _contar_dias_uteis(data_inicio, dr)

        # Taxa CDI diária e aplicação do percentual contratado
        cdi_diario = (1 + cdi_anual / 100) ** (1 / 252) - 1
        taxa_diaria = cdi_diario * (taxa_valor / 100)

        valor_final = valor_aplicado * ((1 + taxa_diaria) ** n_du)
        rendimento  = valor_final - valor_aplicado
        meses       = round(n_du / 21, 1)

        return {
            "meses": meses,
            "dias_uteis": n_du,
            "taxa_mensal": round((1 + taxa_diaria) ** 21 - 1, 6),
            "valor_final": round(valor_final, 2),
            "rendimento": round(rendimento, 2),
            "rentabilidade_pct": round((rendimento / valor_aplicado) * 100, 4) if valor_aplicado else 0,
        }

    # MENSAL / ANUAL — mantém cálculo por meses
    meses = max(0, (dr.year - da.year) * 12 + (dr.month - da.month))
    if taxa_tipo == "MENSAL":
        taxa_m = taxa_valor / 100
    else:  # ANUAL
        taxa_m = (1 + taxa_valor / 100) ** (1 / 12) - 1

    valor_final = valor_aplicado * ((1 + taxa_m) ** meses)
    rendimento  = valor_final - valor_aplicado

    return {
        "meses": meses,
        "dias_uteis": None,
        "taxa_mensal": taxa_m,
        "valor_final": round(valor_final, 2),
        "rendimento": round(rendimento, 2),
        "rentabilidade_pct": round((rendimento / valor_aplicado) * 100, 4) if valor_aplicado else 0,
    }


_TIPOS_ISENTOS_IR = {"LCI", "LCA", "Poupança"}


def calcular_ir(tipo: str, rendimento_bruto: float, data_aplicacao_str: str,
                data_referencia_str: str = None) -> dict:
    """
    Calcula IR sobre rendimento de renda fixa pela tabela regressiva.
    Usa dias corridos (calendário), não úteis.

    Alíquotas:
      ≤ 180 dias  → 22,5%
      ≤ 360 dias  → 20,0%
      ≤ 720 dias  → 17,5%
      > 720 dias  → 15,0%

    LCI, LCA e Poupança são isentos.
    """
    if tipo in _TIPOS_ISENTOS_IR or rendimento_bruto <= 0:
        return {
            "isento": True,
            "aliquota": 0.0,
            "valor_ir": 0.0,
            "rendimento_liquido": round(rendimento_bruto, 2),
        }

    da = date.fromisoformat(data_aplicacao_str)
    dr = date.fromisoformat(data_referencia_str) if data_referencia_str else date.today()
    dias = (dr - da).days

    if dias <= 180:
        aliquota = 22.5
    elif dias <= 360:
        aliquota = 20.0
    elif dias <= 720:
        aliquota = 17.5
    else:
        aliquota = 15.0

    valor_ir = round(rendimento_bruto * aliquota / 100, 2)
    return {
        "isento": False,
        "aliquota": aliquota,
        "valor_ir": valor_ir,
        "rendimento_liquido": round(rendimento_bruto - valor_ir, 2),
    }


def simular_investimento(valor_inicial: float, aporte_mensal: float,
                          taxa_mensal: float, meses: int) -> list[dict]:
    saldo = valor_inicial
    resultado = []
    for m in range(1, meses + 1):
        saldo = (saldo + aporte_mensal) * (1 + taxa_mensal)
        resultado.append({
            "mes": m,
            "saldo": round(saldo, 2),
            "total_investido": round(valor_inicial + aporte_mensal * m, 2),
            "rendimento": round(saldo - valor_inicial - aporte_mensal * m, 2),
        })
    return resultado


def comparar_investimentos(valor: float, meses: int, opcoes: list[dict]) -> list[dict]:
    """opcoes: [{'nome': str, 'taxa_tipo': str, 'taxa_valor': float}]"""
    CDI_MENSAL = 0.009
    resultado = []
    for op in opcoes:
        if op["taxa_tipo"] == "MENSAL":
            tm = op["taxa_valor"] / 100
        elif op["taxa_tipo"] == "ANUAL":
            tm = (1 + op["taxa_valor"] / 100) ** (1 / 12) - 1
        else:
            tm = CDI_MENSAL * (op["taxa_valor"] / 100)
        vf = valor * ((1 + tm) ** meses)
        resultado.append({
            "nome": op["nome"],
            "valor_final": round(vf, 2),
            "rendimento": round(vf - valor, 2),
            "rentabilidade_pct": round(((vf - valor) / valor) * 100, 2),
        })
    return sorted(resultado, key=lambda x: x["valor_final"], reverse=True)


# ─── Simulador de antecipação de dívida ──────────────────────────────────────


def simular_antecipacao(valor_parcela: float, num_parcelas_restantes: int,
                         desconto_pct: float) -> dict:
    valor_sem_desconto = valor_parcela * num_parcelas_restantes
    desconto = valor_sem_desconto * (desconto_pct / 100)
    valor_com_desconto = valor_sem_desconto - desconto
    return {
        "valor_sem_desconto": round(valor_sem_desconto, 2),
        "desconto": round(desconto, 2),
        "valor_com_desconto": round(valor_com_desconto, 2),
        "economia": round(desconto, 2),
    }


# ─── Formatação ──────────────────────────────────────────────────────────────


def fmt_data(data_iso: str) -> str:
    """Converte YYYY-MM-DD para DD/MM/YYYY. Retorna o valor original se inválido."""
    try:
        if data_iso and len(data_iso) >= 10:
            return f"{data_iso[8:10]}/{data_iso[5:7]}/{data_iso[:4]}"
    except Exception:
        pass
    return data_iso or "—"


def fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(valor: float) -> str:
    return f"{valor:.2f}%"

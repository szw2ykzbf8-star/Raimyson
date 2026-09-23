"""
Gera relatório PDF do mês anterior e envia via Telegram.
Executado no 1º dia de cada mês pelo agendador (09:05 UTC / 06:05 BRT).
"""
import io
import json
import os
import sys
from datetime import date, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests
import gspread
from google.oauth2.service_account import Credentials
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from src.config import (
    GOOGLE_CREDENTIALS_PATH, GOOGLE_CREDENTIALS_JSON, SPREADSHEET_ID,
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SHEETS,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_BRT    = timezone(timedelta(hours=-3))

MESES_PT = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
            "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]


def _get_sp():
    if GOOGLE_CREDENTIALS_JSON:
        info  = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    else:
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=_SCOPES)
    return gspread.authorize(creds).open_by_key(SPREADSHEET_ID)


def _get_rows(sp, sheet_name: str) -> list[dict]:
    try:
        return sp.worksheet(sheet_name).get_all_records()
    except Exception:
        return []


def _get_config(sp, chave: str, default: str = "") -> str:
    rows = _get_rows(sp, "config")
    for r in rows:
        if str(r.get("chave", "")) == chave:
            return str(r.get("valor", default))
    return default


def _mes_anterior_str(hoje: date) -> str:
    if hoje.month == 1:
        return f"{hoje.year - 1}-12"
    return f"{hoje.year}-{hoje.month - 1:02d}"


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(sp, mes_ref: str) -> bytes:
    ano, mes_num = int(mes_ref[:4]), int(mes_ref[5:])
    nome_mes     = f"{MESES_PT[mes_num - 1]} {ano}"

    # Dados
    entradas = [r for r in _get_rows(sp, SHEETS["entradas"]) if r.get("mes_referencia") == mes_ref]
    gastos   = [r for r in _get_rows(sp, SHEETS["gastos"])   if r.get("mes_referencia") == mes_ref]

    total_e = sum(float(r.get("valor", 0)) for r in entradas)
    total_g = sum(float(r.get("valor_parcela", 0)) for r in gastos)
    resultado = total_e - total_g

    meta = float(_get_config(sp, "meta_economia", "0") or 0)

    # Gastos por categoria
    by_cat: dict[str, float] = {}
    for r in gastos:
        cat = r.get("categoria", "Outros")
        by_cat[cat] = by_cat.get(cat, 0) + float(r.get("valor_parcela", 0))
    by_cat_sorted = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)

    # Montar PDF
    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    # Estilos
    title_style   = ParagraphStyle("title",   parent=styles["Title"],   fontSize=18, textColor=colors.HexColor("#2ECC71"), spaceAfter=4)
    subtitle_style= ParagraphStyle("subtitle",parent=styles["Normal"],  fontSize=11, textColor=colors.HexColor("#A0AEC0"), alignment=TA_CENTER, spaceAfter=12)
    label_style   = ParagraphStyle("label",   parent=styles["Normal"],  fontSize=9,  textColor=colors.HexColor("#A0AEC0"))
    section_style = ParagraphStyle("section", parent=styles["Heading2"],fontSize=12, textColor=colors.HexColor("#3498DB"), spaceBefore=14, spaceAfter=6)

    story.append(Paragraph("💰 FinTrack", title_style))
    story.append(Paragraph(f"Relatório Mensal — {nome_mes}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2D3748")))
    story.append(Spacer(1, 0.4*cm))

    # Resumo
    cor_res = colors.HexColor("#2ECC71") if resultado >= 0 else colors.HexColor("#E74C3C")
    resumo_data = [
        ["💰 Total de Entradas", "💸 Total de Saídas", "📊 Resultado"],
        [_fmt_brl(total_e), _fmt_brl(total_g), _fmt_brl(resultado)],
    ]
    resumo_table = Table(resumo_data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
    resumo_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1A1F2E")),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.HexColor("#A0AEC0")),
        ("TEXTCOLOR",    (0, 1), (0, 1),   colors.HexColor("#2ECC71")),
        ("TEXTCOLOR",    (1, 1), (1, 1),   colors.HexColor("#E74C3C")),
        ("TEXTCOLOR",    (2, 1), (2, 1),   cor_res),
        ("FONTSIZE",     (0, 0), (-1, -1), 11),
        ("FONTNAME",     (0, 1), (-1, 1),  "Helvetica-Bold"),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0,1),(-1,1), [colors.HexColor("#0D1117")]),
        ("ROUNDEDCORNERS",(0,0),(-1,-1),4),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#2D3748")),
    ]))
    story.append(resumo_table)
    story.append(Spacer(1, 0.3*cm))

    # Meta
    if meta > 0:
        pct  = min(resultado / meta * 100, 100) if meta else 0
        emoji = "✅" if resultado >= meta else ("⚠️" if resultado >= 0 else "❌")
        story.append(Paragraph(f"{emoji} Meta de economia: {_fmt_brl(meta)} — {pct:.0f}% atingido", label_style))
        story.append(Spacer(1, 0.3*cm))

    # Gastos por categoria
    story.append(Paragraph("Gastos por Categoria", section_style))

    if by_cat_sorted:
        cat_data = [["Categoria", "Valor", "% do Total"]]
        for cat, val in by_cat_sorted:
            pct_cat = val / total_g * 100 if total_g else 0
            cat_data.append([cat, _fmt_brl(val), f"{pct_cat:.1f}%"])
        cat_data.append(["TOTAL", _fmt_brl(total_g), "100%"])

        cat_table = Table(cat_data, colWidths=[8*cm, 4*cm, 4*cm])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0),   colors.HexColor("#1A1F2E")),
            ("TEXTCOLOR",    (0, 0), (-1, 0),   colors.HexColor("#A0AEC0")),
            ("BACKGROUND",   (0, -1),(-1, -1),  colors.HexColor("#1A1F2E")),
            ("FONTNAME",     (0, 0), (-1, 0),   "Helvetica-Bold"),
            ("FONTNAME",     (0, -1),(-1, -1),  "Helvetica-Bold"),
            ("TEXTCOLOR",    (1, -1),(1, -1),   colors.HexColor("#E74C3C")),
            ("FONTSIZE",     (0, 0), (-1, -1),  10),
            ("ALIGN",        (1, 0), (-1, -1),  "RIGHT"),
            ("ALIGN",        (0, 0), (0, -1),   "LEFT"),
            ("ROWBACKGROUNDS",(0,1),(-1,-2), [colors.HexColor("#0D1117"), colors.HexColor("#111827")]),
            ("TOPPADDING",   (0, 0), (-1, -1),  7),
            ("BOTTOMPADDING",(0, 0), (-1, -1),  7),
            ("LEFTPADDING",  (0, 0), (-1, -1),  8),
            ("RIGHTPADDING", (0, 0), (-1, -1),  8),
            ("GRID",         (0, 0), (-1, -1),  0.5, colors.HexColor("#2D3748")),
        ]))
        story.append(cat_table)
    else:
        story.append(Paragraph("Nenhum gasto registrado neste mês.", label_style))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#2D3748")))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f"Gerado automaticamente pelo FinTrack em {date.today().strftime('%d/%m/%Y')}",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.HexColor("#718096"), alignment=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()


def _send_pdf(pdf_bytes: bytes, nome_arquivo: str, legenda: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[relatorio] Telegram não configurado.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": legenda, "parse_mode": "HTML"},
            files={"document": (nome_arquivo, pdf_bytes, "application/pdf")},
            timeout=30,
        )
        print(f"[relatorio] ✅ PDF enviado: {nome_arquivo}")
    except Exception as e:
        print(f"[relatorio] Falha ao enviar: {e}")


def main():
    hoje    = date.today()
    mes_ref = _mes_anterior_str(hoje)
    ano, mes_num = int(mes_ref[:4]), int(mes_ref[5:])
    nome_mes = f"{MESES_PT[mes_num - 1]} {ano}"

    print(f"[relatorio] Gerando relatório de {nome_mes}...", flush=True)

    try:
        sp = _get_sp()
    except Exception as e:
        print(f"[relatorio] Erro ao conectar: {e}")
        return

    pdf_bytes    = gerar_pdf(sp, mes_ref)
    nome_arquivo = f"fintrack_{mes_ref}.pdf"
    legenda      = (
        f"📊 <b>FinTrack — Relatório de {nome_mes}</b>\n"
        f"Resumo completo de entradas, saídas e gastos por categoria."
    )
    _send_pdf(pdf_bytes, nome_arquivo, legenda)


if __name__ == "__main__":
    main()

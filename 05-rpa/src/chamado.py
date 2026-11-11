"""Gera o PDF do chamado de manutencao."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from .config import OBRIGACAO_MUNICIPIO, Config
from .regras import Decisao


def _t(texto: object) -> str:
    """Fontes core do PDF so aceitam latin-1; troca o que nao couber."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _linha(pdf: FPDF, rotulo: str, valor: object) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(45, 6, _t(rotulo))
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _t(valor), new_x="LMARGIN", new_y="NEXT")


def gerar_pdf(o: dict, decisao: Decisao, foto_limpa: Path, destino_dir: Path,
              cfg: Config, hoje: date) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    prazo = cfg.prazo_urgente if decisao.prioridade == "URGENTE" else cfg.prazo_normal
    mapa = f"https://www.google.com/maps?q={o['latitude']},{o['longitude']}"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _t("Chamado de manutencao de iluminacao publica"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Emitido em {hoje.strftime('%d/%m/%Y')} pelo robo CitizenTech"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    _linha(pdf, "Ocorrencia:", o["id"])
    _linha(pdf, "Poste:", o["poste_id"])
    _linha(pdf, "Prioridade:", f"{decisao.prioridade} ({decisao.motivo})")
    _linha(pdf, "Prazo sugerido:", prazo)
    _linha(pdf, "Coordenadas:", f"{o['latitude']}, {o['longitude']}")
    _linha(pdf, "Mapa:", mapa)
    _linha(pdf, "Luminosidade (lux):", o.get("lux_medido", ""))
    _linha(pdf, "Registro em:", o.get("data_hora", ""))
    _linha(pdf, "Analise da IA:", f"{o.get('descricao_ia', '')} (confianca {o['confianca_ia']})")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _t("Fundamento"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _t(OBRIGACAO_MUNICIPIO), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _t("Foto do local (sem metadados; rostos/placas desfocados quando detectados)"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.image(str(foto_limpa), w=110)

    caminho = destino_dir / f"chamado_{o['id']}.pdf"
    pdf.output(str(caminho))
    return caminho

"""Gera o PDF do chamado de manutencao."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF

from . import regras
from .config import (FUNDAMENTO_BASE, FUNDAMENTO_ENERGIA, FUNDAMENTO_ILUMINACAO, SETOR_PADRAO,
                     SETORES, TIPOS_ENERGIA, TIPOS_ILUMINACAO, Config)


def setores(o: dict) -> list[str]:
    return [SETORES.get(t, SETOR_PADRAO) for t in sorted(regras.tipos(o))]


def descricao_curta(o: dict) -> str:
    """Resumo de uma linha, usado no portal e no e-mail."""
    partes = []
    if o.get("status_trecho"):
        partes.append(f"trecho {o['status_trecho']}")
    if o.get("postes_apagados") not in ("", "0", None):
        partes.append(f"{o['postes_apagados']} poste(s) apagado(s)")
    if o.get("motivos"):
        partes.append(o["motivos"])
    return "; ".join(partes) or "ver PDF anexo"


def fundamento(o: dict) -> str:
    texto = FUNDAMENTO_BASE
    if regras.tipos(o) & TIPOS_ILUMINACAO:
        texto += " " + FUNDAMENTO_ILUMINACAO
    if regras.tipos(o) & TIPOS_ENERGIA:
        texto += " " + FUNDAMENTO_ENERGIA
    return texto


def _t(texto: object) -> str:
    """Fontes core do PDF so aceitam latin-1; troca o que nao couber."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _linha(pdf: FPDF, rotulo: str, valor: object) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(48, 6, _t(rotulo))
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _t(valor), new_x="LMARGIN", new_y="NEXT")


def _lista_membros(membros: list[tuple[dict, float]], limite: int = 10) -> str:
    itens = [f"{m['id_captura']} ({d:.0f} m)" for m, d in membros[:limite]]
    if len(membros) > limite:
        itens.append(f"e mais {len(membros) - limite}")
    return ", ".join(itens)


def gerar_pdf(o: dict, membros: list[tuple[dict, float]], foto_limpa: Path, destino_dir: Path,
              cfg: Config, hoje: date) -> Path:
    destino_dir.mkdir(parents=True, exist_ok=True)
    nivel = o["prioridade_nivel"]
    mapa = f"https://www.google.com/maps?q={o['latitude']},{o['longitude']}"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(True, 15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _t("Chamado de manutenção de iluminação pública"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, _t(f"Emitido em {hoje.strftime('%d/%m/%Y')} pelo robô CitizenTech"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    _linha(pdf, "Chamado (id_captura):", o["id_captura"])
    _linha(pdf, "Setor responsável:", "; ".join(setores(o)))
    _linha(pdf, "Prioridade:", f"{nivel.upper()} (pontuação {regras.pontuacao(o)}/100)")
    _linha(pdf, "Prazo sugerido:", cfg.prazos.get(nivel, "a definir"))
    _linha(pdf, "Coordenadas:", f"{o['latitude']}, {o['longitude']}")
    _linha(pdf, "Mapa:", mapa)
    _linha(pdf, "Registro em:", o.get("timestamp", ""))
    _linha(pdf, "Origem:", o.get("origem", ""))
    if o.get("sensor_lux"):
        _linha(pdf, "Sensor de luz (lux):", o["sensor_lux"])
    _linha(pdf, "Situação do trecho:", f"{o.get('status_trecho', '')}, "
                                       f"{o.get('postes_apagados') or 0} poste(s) apagado(s)")
    _linha(pdf, "Confirmação sensor+foto:", o.get("confirmacao", ""))
    _linha(pdf, "Fatores da prioridade:", o.get("fatores", ""))
    _linha(pdf, "Motivos da validação:", o.get("motivos", ""))
    _linha(pdf, "Modelo de IA:", o.get("modelo", ""))
    if membros:
        _linha(pdf, "Consolida:", f"{len(membros)} chamado(s) no mesmo trecho: "
                                  f"{_lista_membros(membros)}")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _t("Fundamento"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _t(fundamento(o)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _t("Foto do local (sem metadados; rostos e placas desfocados quando detectados)"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.image(str(foto_limpa), w=110)

    caminho = destino_dir / f"chamado_{o['id_captura']}.pdf"
    pdf.output(str(caminho))
    return caminho

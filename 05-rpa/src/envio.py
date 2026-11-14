"""Registro do chamado na prefeitura: mock (.eml em disco), smtp (e-mail real) ou portal (fila UiPath)."""
from __future__ import annotations

import csv
import logging
import smtplib
import time
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from .chamado import descricao_curta, setores
from .config import Config


class ErroEnvio(Exception):
    """Falha de envio depois de esgotar as tentativas."""


@dataclass(frozen=True)
class ResultadoEnvio:
    etapa: str          # enviado | na_fila_portal   (coluna rpa_etapa)
    protocolo: str      # vazio enquanto o portal nao devolve o numero
    canal: str
    encaminhado: bool   # True: o chamado ja pode passar a status `encaminhado`


def com_retry(fn, tentativas: int, espera_base: float, log: logging.Logger, rotulo: str):
    """Repete `fn` com backoff exponencial. Ao esgotar, levanta ErroEnvio (nada fica silencioso)."""
    for n in range(1, tentativas + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - qualquer falha de rede/SMTP entra no retry
            if n == tentativas:
                raise ErroEnvio(f"{rotulo}: falhou apos {n} tentativas ({e})") from e
            espera = espera_base * 2 ** (n - 1)
            log.warning("%s: tentativa %d/%d falhou (%s); nova tentativa em %.1fs",
                        rotulo, n, tentativas, e, espera)
            time.sleep(espera)


def _montar_email(o: dict, n_agrupados: int, pdf: Path, cfg: Config) -> EmailMessage:
    nivel = o["prioridade_nivel"]
    msg = EmailMessage()
    msg["From"] = cfg.remetente
    msg["To"] = cfg.destino_email
    msg["Subject"] = f"[{nivel.upper()}] Iluminação pública, chamado {o['id_captura']}"
    extra = f"Consolida {n_agrupados} chamado(s) do mesmo trecho.\n" if n_agrupados else ""
    msg.set_content(
        f"Segue chamado de manutenção.\n\n"
        f"Setor: {'; '.join(setores(o))}\n"
        f"Prioridade: {nivel.upper()} (prazo sugerido: {cfg.prazos.get(nivel, 'a definir')})\n"
        f"Coordenadas: {o['latitude']}, {o['longitude']}\n"
        f"{extra}\nDetalhes e foto no PDF anexo.\n"
    )
    msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf", filename=pdf.name)
    return msg


def enviar(o: dict, n_agrupados: int, pdf: Path, cfg: Config, hoje: date,
           log: logging.Logger) -> ResultadoEnvio:
    cid = o["id_captura"]
    protocolo = f"CH-{hoje:%Y%m%d}-{cid}"  # referencia interna; o portal devolve o numero oficial

    if cfg.envio_modo == "mock":
        pasta = cfg.outbox_dir / "emails"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{cid}.eml").write_bytes(bytes(_montar_email(o, n_agrupados, pdf, cfg)))
        return ResultadoEnvio("enviado", protocolo, "mock", True)

    if cfg.envio_modo == "smtp":
        msg = _montar_email(o, n_agrupados, pdf, cfg)

        def _smtp():
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as s:
                s.starttls()
                if cfg.smtp_user:
                    s.login(cfg.smtp_user, cfg.smtp_senha)
                s.send_message(msg)

        com_retry(_smtp, cfg.max_tentativas, cfg.backoff_base_s, log, f"smtp {cid}")
        return ResultadoEnvio("enviado", protocolo, "smtp", True)

    if cfg.envio_modo == "portal":
        cfg.outbox_dir.mkdir(parents=True, exist_ok=True)
        fila = cfg.outbox_dir / "fila_portal.csv"
        novo = not fila.exists()
        with fila.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if novo:
                w.writerow(["id_captura", "latitude", "longitude", "tipos_chamado",
                            "prioridade", "descricao", "pdf", "agrupados"])
            w.writerow([cid, o["latitude"], o["longitude"], o["tipos_chamado"],
                        o["prioridade_nivel"], descricao_curta(o), str(pdf), n_agrupados])
        return ResultadoEnvio("na_fila_portal", "", "portal", False)

    raise ErroEnvio(f"ENVIO_MODO desconhecido: {cfg.envio_modo!r}")

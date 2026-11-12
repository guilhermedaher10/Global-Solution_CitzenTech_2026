"""Envio do chamado: mock (.eml em disco), smtp (e-mail real) ou portal (fila para o UiPath)."""
from __future__ import annotations

import csv
import logging
import smtplib
import time
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from .config import Config
from .regras import Decisao


class ErroEnvio(Exception):
    """Falha de envio depois de esgotar as tentativas."""


@dataclass(frozen=True)
class ResultadoEnvio:
    status: str      # ENVIADO | FILA_PORTAL
    protocolo: str
    canal: str


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


def _montar_email(o: dict, decisao: Decisao, pdf: Path, cfg: Config) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = cfg.remetente
    msg["To"] = cfg.destino_email
    msg["Subject"] = f"[{decisao.prioridade}] Iluminacao publica - poste {o['poste_id']} ({o['id']})"
    msg.set_content(
        f"Segue chamado de manutencao de iluminacao publica.\n\n"
        f"Poste: {o['poste_id']}\nPrioridade: {decisao.prioridade} ({decisao.motivo})\n"
        f"Coordenadas: {o['latitude']}, {o['longitude']}\n\n"
        f"Detalhes e foto no PDF anexo.\n"
    )
    msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf", filename=pdf.name)
    return msg


def enviar(o: dict, decisao: Decisao, pdf: Path, cfg: Config, hoje: date,
           log: logging.Logger) -> ResultadoEnvio:
    protocolo = f"CH-{hoje:%Y%m%d}-{o['id']}"

    if cfg.envio_modo == "mock":
        pasta = cfg.outbox_dir / "emails"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / f"{o['id']}.eml").write_bytes(bytes(_montar_email(o, decisao, pdf, cfg)))
        return ResultadoEnvio("ENVIADO", protocolo, "mock")

    if cfg.envio_modo == "smtp":
        msg = _montar_email(o, decisao, pdf, cfg)

        def _smtp():
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as s:
                s.starttls()
                if cfg.smtp_user:
                    s.login(cfg.smtp_user, cfg.smtp_senha)
                s.send_message(msg)

        com_retry(_smtp, cfg.max_tentativas, cfg.backoff_base_s, log, f"smtp {o['id']}")
        return ResultadoEnvio("ENVIADO", protocolo, "smtp")

    if cfg.envio_modo == "portal":
        cfg.outbox_dir.mkdir(parents=True, exist_ok=True)
        fila = cfg.outbox_dir / "fila_portal.csv"
        novo = not fila.exists()
        with fila.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if novo:
                w.writerow(["id", "poste_id", "latitude", "longitude", "prioridade",
                            "descricao", "pdf"])
            w.writerow([o["id"], o["poste_id"], o["latitude"], o["longitude"],
                        decisao.prioridade, o.get("descricao_ia", ""), str(pdf)])
        return ResultadoEnvio("FILA_PORTAL", "", "portal")

    raise ErroEnvio(f"ENVIO_MODO desconhecido: {cfg.envio_modo!r}")

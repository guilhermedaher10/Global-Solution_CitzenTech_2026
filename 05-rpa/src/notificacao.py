"""Avisa o n8n (webhook) com o resumo da execucao. Falha aqui nao derruba o robo, mas e logada."""
from __future__ import annotations

import logging

import requests

from .config import Config


def notificar_n8n(payload: dict, cfg: Config, log: logging.Logger) -> bool:
    if not cfg.n8n_webhook_url:
        log.info("n8n: webhook nao configurado, notificacao ignorada")
        return False
    try:
        r = requests.post(cfg.n8n_webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("n8n: resumo enviado (HTTP %s)", r.status_code)
        return True
    except requests.RequestException as e:
        log.error("n8n: falha ao notificar (%s)", e)
        return False

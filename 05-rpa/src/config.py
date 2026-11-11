"""Configuracao central. Segredos vem de variaveis de ambiente / .env, nunca do codigo."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv e opcional na hora de rodar testes
    load_dotenv = None

RAIZ = Path(__file__).resolve().parent.parent

# Texto-base do chamado. CONFIRME com o grupo/professor antes de usar no relatorio.
OBRIGACAO_MUNICIPIO = (
    "A iluminacao publica e servico de interesse local, de competencia do municipio "
    "(CF/88, art. 30, V), custeado pela Contribuicao para o Custeio do Servico de "
    "Iluminacao Publica (CF/88, art. 149-A). Solicita-se a vistoria e o reparo do ponto "
    "de iluminacao informado."
)


@dataclass(frozen=True)
class Config:
    csv_path: Path = RAIZ / "data" / "ocorrencias.csv"
    outbox_dir: Path = RAIZ / "outbox"
    logs_dir: Path = RAIZ / "logs"

    envio_modo: str = "mock"  # mock | smtp | portal
    destino_email: str = "zeladoria@example.org"
    remetente: str = "robo@example.org"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_senha: str = ""

    limiar_confianca: float = 0.70
    janela_duplicidade_dias: int = 30
    max_tentativas: int = 3
    backoff_base_s: float = 1.0

    n8n_webhook_url: str = ""

    prazo_urgente: str = "48 horas"
    prazo_normal: str = "15 dias"

    @property
    def base_dir(self) -> Path:
        """Pasta usada para resolver o caminho relativo das fotos."""
        return self.csv_path.parent

    @classmethod
    def from_env(cls) -> "Config":
        if load_dotenv:
            load_dotenv(RAIZ / ".env")
        e = os.environ.get
        return cls(
            envio_modo=e("ENVIO_MODO", "mock").lower(),
            destino_email=e("DESTINO_EMAIL", cls.destino_email),
            remetente=e("REMETENTE", cls.remetente),
            smtp_host=e("SMTP_HOST", ""),
            smtp_port=int(e("SMTP_PORT", "587")),
            smtp_user=e("SMTP_USER", ""),
            smtp_senha=e("SMTP_SENHA", ""),
            limiar_confianca=float(e("LIMIAR_CONFIANCA", "0.70")),
            janela_duplicidade_dias=int(e("JANELA_DUPLICIDADE_DIAS", "30")),
            max_tentativas=int(e("MAX_TENTATIVAS", "3")),
            backoff_base_s=float(e("BACKOFF_BASE_S", "1.0")),
            n8n_webhook_url=e("N8N_WEBHOOK_URL", ""),
        )

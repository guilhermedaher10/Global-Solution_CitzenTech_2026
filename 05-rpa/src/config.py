"""Configuracao central. Segredos vem de variaveis de ambiente / .env, nunca do codigo."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv e opcional na hora de rodar testes
    load_dotenv = None

RAIZ = Path(__file__).resolve().parent.parent

# Setor responsavel por cada tipo de chamado (fusao.tipos_chamado, contrato da Visao v1.1).
SETORES = {
    "conserto_poste": "Iluminação pública: conserto de ponto apagado",
    "instalacao_iluminacao": "Iluminação pública: instalação de novo ponto",
    "poda_ou_obstrucao": "Zeladoria: poda ou obstrução que bloqueia a iluminação",
    "buraco": "Vias públicas: reparo de buraco",
}
SETOR_PADRAO = "Zeladoria urbana (geral)"
TIPOS_ILUMINACAO = {"conserto_poste", "instalacao_iluminacao", "poda_ou_obstrucao"}

# Texto-base do chamado. CONFIRME com o grupo/professor antes de usar no relatorio.
FUNDAMENTO_BASE = (
    "Os serviços públicos de interesse local são de competência do município "
    "(CF/88, art. 30, V). Solicita-se a vistoria e o reparo no ponto informado."
)
FUNDAMENTO_ILUMINACAO = (
    "A iluminação pública é custeada pela Contribuição para o Custeio do Serviço de "
    "Iluminação Pública (CF/88, art. 149-A)."
)


@dataclass(frozen=True)
class Config:
    csv_path: Path = RAIZ / "data" / "chamados.csv"
    outbox_dir: Path = RAIZ / "outbox"
    logs_dir: Path = RAIZ / "logs"

    envio_modo: str = "mock"  # mock | smtp | portal
    destino_email: str = "zeladoria@example.org"
    remetente: str = "robo@example.org"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_senha: str = ""

    # Agrupamento de duplicados: mesmo trecho = ate `raio` metros e ao menos um tipo em comum.
    raio_agrupamento_m: float = 30.0
    janela_agrupamento_dias: int = 30
    max_tentativas: int = 3
    backoff_base_s: float = 1.0

    n8n_webhook_url: str = ""

    # Prazo sugerido por nivel de prioridade da Visao (proposta do grupo, ajustavel).
    prazos: dict = field(default_factory=lambda: {
        "alta": "48 horas", "media": "7 dias", "baixa": "15 dias",
    })

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
            raio_agrupamento_m=float(e("RAIO_AGRUPAMENTO_M", "30")),
            janela_agrupamento_dias=int(e("JANELA_AGRUPAMENTO_DIAS", "30")),
            max_tentativas=int(e("MAX_TENTATIVAS", "3")),
            backoff_base_s=float(e("BACKOFF_BASE_S", "1.0")),
            n8n_webhook_url=e("N8N_WEBHOOK_URL", ""),
        )

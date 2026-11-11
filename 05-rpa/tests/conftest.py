import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.config import Config  # noqa: E402


@pytest.fixture
def cfg(tmp_path) -> Config:
    """Config isolada: copia os dados de exemplo para uma pasta temporaria."""
    shutil.copytree(RAIZ / "data", tmp_path / "data")
    return replace(
        Config(),
        csv_path=tmp_path / "data" / "ocorrencias.csv",
        outbox_dir=tmp_path / "outbox",
        logs_dir=tmp_path / "logs",
        envio_modo="mock",
        backoff_base_s=0.0,
        n8n_webhook_url="",
    )

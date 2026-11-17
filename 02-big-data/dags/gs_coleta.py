from __future__ import annotations
import json
from pathlib import Path

import pendulum
import requests
from airflow import DAG
from airflow.models import Variable
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import PythonOperator

CHEGADA = Path("/opt/airflow/chegada")

def _salvar(subpasta: str, nome: str, conteudo: str):
    destino = CHEGADA / subpasta / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")

def coletar_clima(ds, **_):
    # Clima diário de SP (contexto de anoitecer/chuva). Troque lat/long se quiser.
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={"latitude": -23.55, "longitude": -46.63,
                "start_date": ds, "end_date": ds,
                "hourly": "temperature_2m,precipitation"},
        timeout=60)
    r.raise_for_status()
    _salvar("clima", f"clima_{ds}.json", r.text)

def coletar_ibge(ds, **_):
    # Municípios do estado de SP (base para população/por mil habitantes)
    r = requests.get(
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios",
        timeout=60)
    r.raise_for_status()
    _salvar("ibge", f"municipios_sp_{ds}.json", r.text)

def coletar_sp156(ds, **_):
    url = Variable.get("sp156_url")          # link do xlsx, fica na Variable
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    destino = CHEGADA / "sp156" / f"sp156_{ds}.xlsx"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(r.content)           # binário, não texto

def conferir_chegada(ds, **_):
    esperados = [
        CHEGADA / "clima" / f"clima_{ds}.json",
        CHEGADA / "ibge" / f"municipios_sp_{ds}.json",
        CHEGADA / "sp156" / f"sp156_{ds}.xlsx",
    ]
    faltando, vazios = [], []
    for p in esperados:
        if not p.exists():
            faltando.append(p.name)
        elif p.stat().st_size == 0:
            vazios.append(p.name)
    if faltando or vazios:
        raise ValueError(f"faltando={faltando} vazios={vazios}")
    print("OK:", [p.name for p in esperados])

with DAG(
    dag_id="gs_coleta",
    schedule="@daily",
    start_date=pendulum.datetime(2026, 11, 1, tz="America/Sao_Paulo"),
    catchup=True,
    max_active_runs=1,
    tags=["gs", "big-data", "vesper"],
) as dag:
    inicio = EmptyOperator(task_id="inicio")
    clima = PythonOperator(task_id="coletar_clima", python_callable=coletar_clima)
    ibge = PythonOperator(task_id="coletar_ibge", python_callable=coletar_ibge)
    sp156 = PythonOperator(task_id="coletar_sp156", python_callable=coletar_sp156)
    conferir = PythonOperator(task_id="conferir_chegada", python_callable=conferir_chegada)

    inicio >> [clima, ibge, sp156] >> conferir
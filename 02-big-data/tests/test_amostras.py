import csv, json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
AMOSTRAS = RAIZ / "amostras"

def _cabecalho_sp156():
    with open(AMOSTRAS / "sp156_amostra.csv", encoding="utf-8") as f:
        return next(csv.reader(f))

def test_clima_listas_paralelas_do_mesmo_tamanho():
    dados = json.loads((AMOSTRAS / "clima_amostra.json").read_text(encoding="utf-8"))
    hourly = (dados[0] if isinstance(dados, list) else dados)["hourly"]
    tamanhos = {len(v) for v in hourly.values()}
    assert len(tamanhos) == 1 and tamanhos.pop() > 0

def test_ibge_municipios_tem_id_e_nome():
    dados = json.loads((AMOSTRAS / "ibge_amostra.json").read_text(encoding="utf-8"))
    assert dados and all("id" in m and "nome" in m for m in dados)

def test_sp156_tem_colunas_da_bronze():
    cab = _cabecalho_sp156()
    for c in ["data_de_abertura", "servico", "status", "distrito", "arquivo_origem", "carregado_em"]:
        assert c in cab

def test_sp156_sem_coluna_de_dado_pessoal():
    cab = {c.lower() for c in _cabecalho_sp156()}
    assert not cab & {"nome", "cpf", "email", "e_mail", "telefone", "celular"}

def test_dag_le_credenciais_de_variables():
    codigo = (RAIZ / "dags" / "gs_coleta.py").read_text(encoding="utf-8")
    assert 'Variable.get("sp156_url")' in codigo

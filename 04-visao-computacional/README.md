# Visão Computacional · Ruas Escuras

**Disciplina:** Applied Computer Vision · **Professores:** Arnaldo Viana e Paulo Rodrigues

**Responsável:** Guilherme Gonçalves Calil Daher (RM 98611)

**Atividade "Enxergando o mundo real":** treinamento customizado de um detector de objetos (YOLO26) que encontra
**luminárias acesas e apagadas** em fotos e vídeos noturnos, em tempo real, e transforma o que vê em um **chamado
confirmado, localizado e priorizado** para a prefeitura.

📄 Relatório: _link do PDF_ · 🎬 Vídeo: _link do YouTube_ · 📅 [Plano](PLANO.md)

---

## Onde a visão entra no produto

```
 Cidadão (foto no app)  ─┐
 Robô (câmera + LDR)    ─┼─►  YOLO26 ─► poste_aceso / poste_apagado
 Câmera / vídeo         ─┘        │
                                  ▼
                 regras explicáveis (configs/regras.yaml)
                  ├─ status do trecho: iluminada | parcial | escura
                  ├─ validação: a foto serve de evidência? (dia? tremida? sem poste?)
                  └─ prioridade 0-100 com os fatores
                                  │
                                  ▼
                 privacidade: rostos borrados, EXIF descartado, nada armazenado
                                  │
                                  ▼
          JSON do contrato ─► Backend / RPA / Big Data / GenAI ─► atendente confirma ─► conserto
```

O modelo **enxerga**. Quem **decide** são regras auditáveis e, no fim, uma pessoa da prefeitura.

## O que tem aqui

| Caminho | O quê |
|---|---|
| `visao/` | Biblioteca: detector, regras, fusão sensor + foto, privacidade, pipeline, painel de RA, contrato (schemas) |
| `api/main.py` | API FastAPI: `POST /v1/analisar` (foto + sensores, orientação do GenAI), `POST /v1/alerta-robo` (só sensores), `GET /saude` |
| `scripts/` | Coleta → unificação → treino → avaliação → tempo real (passo a passo abaixo) |
| `configs/` | Classes e aliases, regras de negócio, fontes de dados |
| `tests/` | 35 testes (regras, fusão com o robô, integração GenAI, EXIF/privacidade, pipeline, API), sem precisar de GPU |
| `docs/` | [Integração/contrato](docs/integracao.md) · [Dataset](docs/dataset.md) · [Ética e LGPD](docs/etica-lgpd.md) · [Relatório](docs/relatorio.md) · [Roteiro do vídeo](docs/roteiro-video.md) |
| `results/` | Métricas, curvas, matriz de confusão e exemplos (gerados pelos scripts) |
| `models/best.pt` | Modelo treinado |

## Como rodar

```bash
cd 04-visao-computacional
python -m venv .venv
.venv\Scripts\activate                     # Linux/Mac: source .venv/bin/activate

# GPU NVIDIA (opcional, recomendado para treinar)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements-dados.txt -r requirements-dev.txt

pytest                                     # 35 testes
```

### 1. Dataset → 2. Treino → 3. Avaliação
Passo a passo completo em [docs/dataset.md](docs/dataset.md). Resumo:

```bash
python scripts/baixar_roboflow.py          # datasets públicos já anotados (precisa ROBOFLOW_API_KEY no .env)
python scripts/coletar_web.py              # imagens CC do Openverse e Wikimedia (autor e licença no manifesto)
python scripts/extrair_frames.py --fonte <video ou link>
python scripts/deduplicar.py               # remove repetidas e evita vazamento treino/teste
python scripts/unificar_dataset.py --teste-fonte anotado
python scripts/treinar.py --modelo yolo26n.pt
python scripts/avaliar.py
```

### 4. Tempo real (com painel de realidade aumentada)
```bash
python scripts/tempo_real.py --fonte 0                                   # webcam
python scripts/tempo_real.py --fonte video.mp4 --salvar results/demo.mp4
python scripts/tempo_real.py --fonte video.mp4 --lux 2.5 --eventos results/eventos.jsonl   # simula o robô
```
Cada poste ganha um id (ByteTrack) e é contado uma vez no trajeto, pela classe que mais apareceu. Quando um apagado é
confirmado, sai um evento no formato da API.

### 5. API
```bash
uvicorn api.main:app --port 8000           # documentação em http://localhost:8000/docs
curl -F "imagem=@rua.jpg" -F "origem=cidadao" http://localhost:8000/v1/analisar

docker build -t ruas-escuras-visao . && docker run -p 8000:8000 ruas-escuras-visao
```

### 6. Integração com o GenAI (01)
Com `GENAI_URL` definida, `incluir_orientacao=true` devolve o prazo/canal oficial do chamado com a fonte citada
(ou "não consta"). Detalhes em [docs/integracao.md](docs/integracao.md).

### 7. Robô do Maker Lab (LDR + ultrassônico + GPS, sem câmera)
O robô **desconfia** (sensor dispara → `POST /v1/alerta-robo` → suspeita + LED) e a **foto confirma** e diz o tipo
do chamado: conserto de poste, instalação de iluminação, poda ou buraco. Detalhes e exemplo para ESP32 em
[docs/integracao.md](docs/integracao.md).
```bash
python scripts/simular_robo.py                 # testa sem o robô físico (API rodando)
python scripts/simular_robo.py --patrulha 20   # robô andando por uma rua
```

## Resultados
_Preenchido automaticamente por `scripts/avaliar.py` em [results/metricas.md](results/metricas.md)._

| Modelo | mAP50 | mAP50-95 | Precisão | Recall | FPS |
|---|---|---|---|---|---|
| YOLO26n | | | | | |
| YOLO26s | | | | | |

## Decisões de engenharia
- **YOLO26n como padrão:** é leve o bastante para CPU e para o robô (export ONNX). O `s` entra na comparação.
- **Regras fora do modelo:** limiares em YAML. A prefeitura ajusta a política (ex.: o que é "alta") sem retreinar,
  e cada decisão vem com o motivo.
- **Teste com outra origem:** o mAP do relatório é medido em imagens de fonte diferente das do treino.
- **Imagens com licença aberta:** nada de raspar Google/Bing. Toda imagem da web tem autor e licença registrados.
- **Privacidade por padrão:** rostos borrados, EXIF descartado, nenhuma imagem armazenada pela API.
- **Contrato versionado:** `versao_contrato` no JSON; campo novo não quebra quem consome.

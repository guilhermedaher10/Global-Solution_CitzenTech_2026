# Visão Computacional · Vésper

**Disciplina:** Applied Computer Vision · **Professores:** Arnaldo Viana e Paulo Rodrigues

**Responsável:** Guilherme Gonçalves Calil Daher (RM 98611)

**Vésper: da escuridão à luz.** O cidadão que está numa rua escura, ou sem luz no bairro, abre o site, filma alguns
segundos e o chamado chega à central já **confirmado, localizado, priorizado e encaminhado ao órgão certo**
(iluminação pública da prefeitura ou distribuidora de energia).

Nesta disciplina temos dois modelos treinados de forma customizada:
- um detector **YOLO26s** que encontra **postes acesos e apagados**;
- um classificador **YOLO26n-cls** que diz se a cena é **rua iluminada, trecho escuro ou apagão**.

Os dois rodam **em tempo real**, com rastreamento ByteTrack e painel de realidade aumentada.

| | |
|---|---|
| **MVP no ar** | https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io |
| **Relatório (PDF)** | [docs/Relatorio-Visao-Computacional.pdf](docs/Relatorio-Visao-Computacional.pdf) |
| **API (Swagger)** | [/docs](https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io/docs) · contrato **1.5** em [docs/integracao.md](docs/integracao.md) |
| **Vídeo** | _link do YouTube_ · [roteiro](docs/roteiro-video.md) |

---

## Onde a visão entra no produto

```
 Cidadão: "Estou no escuro agora" ─┐   (câmera ao vivo no navegador, foto ou vídeo de 10 s, GPS junto, QR Code)
 Cidadão: foto da galeria          ─┤
 Robô do Maker Lab (LDR + GPS)     ─┘   (o robô desconfia, a foto confirma)
                │
                ▼
   Detector YOLO26s ──► poste_aceso / poste_apagado
   Leitura da cena ───► medidas de luz + classificador YOLO26n-cls + exposição da câmera (EXIF)
                │        vetos físicos: poste aceso na foto = a rede tem energia, então não é apagão
                ▼
   Regras explicáveis (configs/regras.yaml)
     ├─ trecho: iluminado | parcial | escuro       ├─ a foto serve de evidência? (dia? tremida?)
     ├─ prioridade 0-100 com os motivos            └─ tipo: poste, apagão, poda, buraco
                │
                ▼
   Privacidade: rostos borrados, EXIF descartado, imagem e vídeo nunca guardados
                │
                ▼
   Central de chamados: protocolo VSP-XXXXXX, status, órgão responsável, regiões em alerta
     ├─ poste apagado  → Iluminação pública (SP156)
     ├─ falta de energia → Enel (0800 72 72 196) + Defesa Civil (199)
     └─ 3+ relatos a até 500 m em 6 h → "Trecho escuro recorrente" ou "Possível apagão no bairro"
                │
                ▼
   Cidadão acompanha pelo protocolo · Atendente confirma · RPA, Big Data e GenAI consomem a mesma API
```

O modelo **enxerga**. Quem **decide** são regras auditáveis e, no fim, uma pessoa da prefeitura.

## O MVP (site)

| Tela | O que faz |
|---|---|
| **Início** | Botão principal **"Estou no escuro agora"**: abre a câmera ao vivo e manda o chamado sozinho depois do GPS. Também tem o QR Code que abre direto a câmera |
| **Reportar** | **Tirar foto** (câmera do celular) ou **Escolher da galeria**. Mostra a imagem marcada, o protocolo, para onde o chamado vai, a leitura da região e o motivo da prioridade |
| **Acompanhar** | Busca pelo protocolo: linha do tempo com datas, órgão responsável, mapa e quantos vizinhos relataram perto |
| **Robô** | Patrulha ao vivo do carrinho do Maker Lab numa rua com 8 postes. A **mesma IA embarcada (TinyML 4→12→4)** do firmware roda no navegador sobre as leituras de luz e distância e mostra a rede neural, as probabilidades e o log serial. Ao confirmar um trecho escuro, o robô manda um **alerta real** à central (`POST /v1/alerta-robo`); escuro + obstáculo sobe para prioridade alta |
| **Central** | Visão da prefeitura: fila por prioridade, mapa, filtros, mudança de status e regiões em alerta (atualiza a cada 15 s) |
| **Indicadores** | A **camada Ouro do Big Data** dentro do produto: 277 mil chamados reais do SP156, tempo até o conserto, Centro × Periferia por mil habitantes, top 10 distritos, chamados por mês e a linhagem Bronze → Prata → Ouro. Ao lado, o card **"O Vésper agora"** mostra a central ao vivo |

HTML, CSS e JS puros, com ícones de linha em SVG, Leaflet e OpenStreetMap. Funciona no celular, não exige cadastro e não precisa instalar nada.

## O que tem aqui

| Caminho | O quê |
|---|---|
| `visao/` | Biblioteca: detector, leitura de cena, classificador de cena, regras, fusão com o robô, privacidade, vídeo, central de chamados, regiões, painel de RA, contrato (schemas) |
| `web/` | Front do MVP (servido em `/`) |
| `api/main.py` | API FastAPI (rotas abaixo) |
| `scripts/` | Coleta → unificação → treino → avaliação → tempo real → demonstração |
| `configs/` | Classes e aliases, regras de negócio, encaminhamento, regiões, fontes de dados |
| `tests/` | 90 testes (regras, cena, classificador, fusão, EXIF, pipeline, vídeo, central SQLite e Azure Table, API, front, IA do robô e indicadores), sem GPU |
| `docs/` | [Relatório](docs/Relatorio-Visao-Computacional.pdf) · [Integração/contrato](docs/integracao.md) · [Dataset](docs/dataset.md) · [Ética e LGPD](docs/etica-lgpd.md) · [Roteiro do vídeo](docs/roteiro-video.md) |
| `results/` | Métricas, curvas, matrizes de confusão e exemplos (gerados pelos scripts) |
| `models/best.pt` · `models/cena.pt` | Detector YOLO26s · classificador de cena YOLO26n-cls (3 MB) |

### Rotas da API (contrato 1.5)

| Rota | Para quê |
|---|---|
| `POST /v1/analisar` | Foto (+ sensores opcionais) → análise e chamado com protocolo |
| `POST /v1/analisar-video` | Vídeo de até 20 s → um quadro a cada 0,5 s; o mais evidente vira a prova |
| `POST /v1/alerta-robo` · `POST /v1/relatos` | Suspeita do robô (só sensores) · relato sem foto |
| `GET /v1/chamados` · `GET /v1/chamados/{protocolo}` | Fila da central · acompanhamento pelo protocolo |
| `POST /v1/chamados/{protocolo}/status` | Atendente muda o status (transições validadas) |
| `GET /v1/regioes` | Trechos escuros recorrentes e possíveis apagões |
| `GET /v1/indicadores` | Agregados da camada Ouro do Big Data (aba Indicadores), sem dado pessoal |
| `GET /saude` · `GET /metrics` | Saúde e métricas Prometheus (usadas pelo DevOps) |

## Como rodar

```bash
cd 04-visao-computacional
python -m venv .venv
.venv\Scripts\activate                     # Linux/Mac: source .venv/bin/activate

# GPU NVIDIA (opcional, recomendado para treinar)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements-dados.txt -r requirements-dev.txt

pytest                                     # 90 testes
```

### 1. Dataset → 2. Treino → 3. Avaliação (detector)
Passo a passo completo em [docs/dataset.md](docs/dataset.md). Resumo:

```bash
python scripts/baixar_roboflow.py          # datasets públicos já anotados (precisa ROBOFLOW_API_KEY no .env)
python scripts/coletar_web.py              # imagens CC do Openverse e Wikimedia (autor e licença no manifesto)
python scripts/extrair_frames.py --fonte <video ou link>
python scripts/pre_anotar.py               # YOLO-World sugere as caixas; a equipe revisa no Roboflow
python scripts/apagar_lampadas.py          # postes apagados sintéticos (só no treino)
python scripts/deduplicar.py               # remove repetidas e evita vazamento treino/teste
python scripts/unificar_dataset.py --teste-fonte anotado
python scripts/treinar.py --modelo yolo26s.pt
python scripts/avaliar.py
```

### 4. Classificador de cena (iluminada, trecho escuro, apagão)
```bash
python scripts/pranchas_cena.py            # pranchas numeradas para rotular à mão
python scripts/montar_dataset_cena.py      # dedup por hash; fotos da equipe só no teste
python scripts/treinar_cena.py             # YOLO26n-cls, 320 px
python scripts/avaliar_cena.py             # regras × classificador × fusão, com matrizes de confusão
```

### 5. Tempo real (com painel de realidade aumentada)
```bash
python scripts/tempo_real.py --fonte 0                                   # webcam
python scripts/tempo_real.py --fonte video.mp4 --salvar results/demo.mp4
python scripts/tempo_real.py --fonte video.mp4 --lux 2.5 --eventos results/eventos.jsonl   # simula o robô
```
Cada poste ganha um id (ByteTrack) e é contado uma vez no trajeto, pela classe que mais apareceu. O painel mostra o
trecho, a contagem, a leitura da região e o chamado gerado. Cada poste apagado confirmado vira um evento no formato da API.

### 6. API, site e central
```bash
uvicorn api.main:app --port 8000           # site em http://localhost:8000 · API em /docs
curl -F "imagem=@rua.jpg" -F "origem=cidadao" http://localhost:8000/v1/analisar

python scripts/demo_central.py --url http://localhost:8000   # semeia um "possível apagão" no Capão Redondo
python scripts/gerar_qr.py                                    # QR Code que abre a câmera ao vivo

docker build -t vesper-visao . && docker run -p 8000:8000 vesper-visao
```

| Variável | Para quê |
|---|---|
| `CENTRAL_TABELA_URL` + `AZURE_CLIENT_ID` | Central na Azure Table, com identidade gerenciada e sem chave (produção) |
| `CENTRAL_DB` | Central em SQLite (local; padrão na pasta temporária) |
| `CENTRAL_TOKEN` | Libera `POST /v1/central/limpar` (zerar a central antes de uma demonstração) |
| `GENAI_URL` | Assistente de IA generativa (01) para prazos e canais oficiais com a fonte citada |
| `MODELO_PATH` · `CENA_MODELO_PATH` | Troca o detector ou o classificador sem mexer no código |

### 7. Robô do Maker Lab (LDR + ultrassônico + GPS, sem câmera)
O robô **desconfia** (sensor dispara → `POST /v1/alerta-robo` → suspeita + LED) e a **foto confirma** e diz o tipo
do chamado: conserto de poste, instalação de iluminação, poda ou buraco. Detalhes e exemplo para ESP32 em
[docs/integracao.md](docs/integracao.md).
O alerta leva a classe e a confiança da IA do carrinho (`classe_ia`, `confianca_ia`), e `escuro_obstaculo` vira
prioridade alta (LED vermelho).
```bash
python scripts/simular_robo.py                 # testa sem o robô físico (API rodando)
python scripts/simular_robo.py --patrulha 20   # robô andando por uma rua
python scripts/exportar_tinyml_web.py          # copia os pesos do firmware (07) para a aba Robô
```
O gêmeo digital do carrinho (`07-maker-lab/ia/gemeo_digital.py`) reproduz as leituras reais com os mesmos pesos e
manda os alertas para esta API.

### 8. Indicadores (camada Ouro do Big Data)
```bash
python scripts/exportar_ouro_web.py            # lê os resultados do notebook do 02 e gera web/ouro-bigdata.json
```
Um teste falha se o site ficar diferente dos números da Ouro.

## Resultados

**Detector de postes:** teste com 152 imagens reais nunca vistas (228 postes acesos e 27 apagados), sem nenhuma sintética.

| Modelo | mAP50 | AP50 aceso | AP50 apagado | Precisão | Recall | Tempo/imagem |
|---|---|---|---|---|---|---|
| Modelo-base (antes da revisão) | 0,42 | 0,80 | 0,04 | 0,64 | 0,40 | 36 ms CPU |
| YOLO26n | 0,46 | 0,84 | 0,09 | 0,78 | 0,43 | 31 ms CPU |
| **YOLO26s (produção)** | **0,49** | **0,84** | **0,15** | **0,79** | **0,47** | **61 ms CPU · 4,6 ms GPU** |
| YOLO26s a 960 px | 0,50 | 0,87 | 0,14 | 0,59 | 0,50 | 107 ms CPU |

**Leitura de cena** (iluminada, trecho escuro, apagão):

| Abordagem | Teste aberto (43) | Fotos da equipe (38) |
|---|---|---|
| Só regras (medidas de luz) | 72% | 42% |
| **Fusão: classificador + regras + vetos + detector** | **81%** (apagão P 0,78 · R 0,64) | **47%** |

**Tempo real:** 11 FPS no pipeline completo (detecção, rastreamento, borramento de rostos e painel).

**Limitações:**
- Poste apagado à noite é uma silhueta escura, por isso o AP50 dessa classe é baixo. A leitura da cena cobre esse caso.
- Nas fotos de celular da equipe, o apagão ainda é confundido com trecho escuro (P ≈ 0,29).
- Análise completa, com os erros comentados, no [relatório](docs/Relatorio-Visao-Computacional.pdf).

## Decisões de engenharia
- **YOLO26s em produção:** a mesma qualidade do 960 px, com muito mais precisão e metade do tempo. A escolha foi feita pelo teste real, não pela validação.
- **Classificador pequeno com vetos físicos:** o YOLO26n-cls decide quando está confiante. Vetos impedem erros absurdos: um poste aceso na foto significa que a rede tem energia, então a cena não é apagão.
- **Regras fora do modelo:** limiares, encaminhamento e regiões ficam em YAML. A prefeitura ajusta a política sem retreinar, e cada decisão vem com o motivo.
- **Teste honesto:** o teste usa uma origem diferente da do treino, sem imagens sintéticas. As fotos da equipe ficam só no teste.
- **Imagens com licença aberta:** nada de raspar Google ou Bing. Toda imagem da web tem autor e licença registrados.
- **Privacidade por padrão:** rostos borrados e EXIF descartado (só a exposição é lida, para medir a luz). Imagem e vídeo nunca são guardados; a central guarda só os dados do chamado.
- **Central sem chave:** a Azure Table é acessada com identidade gerenciada, e o SQLite é usado no ambiente local. Uma falha na central não derruba a análise.
- **Contrato versionado:** `versao_contrato` vai no JSON. Um campo novo não quebra quem consome.

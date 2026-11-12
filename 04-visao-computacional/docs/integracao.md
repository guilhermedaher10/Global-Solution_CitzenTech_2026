# Integração: como os outros componentes usam a Visão

A Visão expõe **uma API HTTP** e **um formato de JSON** (o contrato, versão `1.3`).
Quem precisa saber se uma foto é evidência de rua escura chama a API. Ninguém precisa entender o YOLO.

```
Robô (Maker Lab: LDR + ultrassônico + GPS, SEM câmera)
   └─ sensor dispara ──► POST /v1/alerta-robo ──► SUSPEITA + prioridade prévia + LED para o robô
                                                   │ (sistema pede foto de confirmação no local)
App do cidadão ──foto + GPS (+ leituras do robô)──┐ ▼
Câmera / vídeo de patrulha ───────────────────────┴──► POST /v1/analisar ──► CHAMADO confirmado e tipado
                                                                              │  (conserto, instalação, poda, buraco)
                                                                              ▼
                                                     Backend / RPA / Big Data → atendente da prefeitura confirma
```

**O robô desconfia, a foto confirma.** Sensor sozinho gera suspeita; a foto transforma em chamado com prova e
diz para qual setor ele vai.

## Endpoints

| Método | Rota | Para quê |
|---|---|---|
| `GET` | `/saude` | Status da API e do modelo (DevOps: health check e monitoramento) |
| `POST` | `/v1/analisar` | Analisa uma foto (e cruza com os sensores, se vierem) e devolve o JSON abaixo |
| `POST` | `/v1/relatos` | Relato do cidadão **sem foto** (só o local + endereço): vira suspeita até uma foto confirmar |
| `POST` | `/v1/alerta-robo` | Alerta do robô **sem foto**: registra a suspeita e diz qual LED acender |
| `GET` | `/docs` | Documentação interativa (Swagger): dá para testar pelo navegador |
| `GET` | `/metrics` | Métricas Prometheus (4 métricas de ouro + chamados, robô, modelo). Com `METRICS_TOKEN` definido, exige `Authorization: Bearer <token>` |

### `POST /v1/analisar` (multipart/form-data)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `imagem` | arquivo | sim | JPEG, PNG ou WebP, até 10 MB |
| `origem` | texto | não | `cidadao` (padrão), `robo` ou `camera` |
| `latitude`, `longitude` | número | não | Se não vier, a API tenta usar o GPS do EXIF da foto |
| `sensor_lux` | número | não | Leitura do sensor de luz (LDR) do robô |
| `sensor_distancia_cm` | número | não | Leitura do ultrassônico do robô |
| `alerta` | texto | não | O que disparou, separado por vírgula: `escuro`, `buraco` ou `escuro,buraco` |
| `retornar_imagem` | bool | não | Devolve a foto com rostos borrados, em base64 |
| `incluir_orientacao` | bool | não | Pergunta ao GenAI o prazo/canal oficial do chamado (ver abaixo) |

```bash
curl -F "imagem=@rua.jpg" -F "origem=robo" -F "sensor_lux=2.4" \
     -F "latitude=-23.5505" -F "longitude=-46.6333" http://localhost:8000/v1/analisar
```

```python
import httpx
with open("rua.jpg", "rb") as f:
    r = httpx.post("http://localhost:8000/v1/analisar",
                   files={"imagem": ("rua.jpg", f, "image/jpeg")},
                   data={"origem": "cidadao", "latitude": -23.55, "longitude": -46.63})
analise = r.json()
if analise["validacao"]["abrir_chamado"]:
    criar_chamado(analise)          # do lado de quem consome
```

## Resposta (exemplo real gerado pelo pipeline)

```json
{
  "versao_contrato": "1.3",
  "id_captura": "b58cccb5-ab16-43cb-8f35-180c00b2939d",
  "timestamp": "2026-11-09T22:12:45-03:00",
  "hora_captura": null,
  "origem": "robo",
  "localizacao": { "latitude": -23.5505, "longitude": -46.6333, "fonte": "informada" },
  "sensor_lux": 2.4,
  "sensor_distancia_cm": null,
  "deteccoes": [
    { "classe": "poste_apagado", "confianca": 0.91, "bbox": [412, 88, 470, 410], "id_rastreio": null },
    { "classe": "poste_aceso",   "confianca": 0.88, "bbox": [120, 60, 170, 400], "id_rastreio": null }
  ],
  "resumo": { "postes_acesos": 1, "postes_apagados": 1, "buracos": 0, "luminosidade_media": 44.7, "status_trecho": "escura" },
  "validacao": {
    "foto_valida": true,
    "falha_detectada": true,
    "abrir_chamado": true,
    "motivos": ["1 poste(s) apagado(s) detectado(s)", "trecho classificado como escuro",
                "sensor de luz do robô marcou 2.4 lux"]
  },
  "prioridade": {
    "nivel": "alta",
    "pontuacao": 90,
    "fatores": ["+25: 1 poste(s) apagado(s)", "+30: trecho escuro", "+20: sensor de luz abaixo de 5.0 lux",
                "+15: sensor do robô e foto concordam"]
  },
  "fusao": {
    "alertas_sensor": ["escuro"], "tipos_chamado": ["conserto_poste"], "confirmacao": "confirmado",
    "motivos": ["poste apagado na foto: conserto", "escuro: a foto confirma o sensor de luz"]
  },
  "privacidade": { "rostos_borrados": 0, "exif_removido": true, "imagem_armazenada": false },
  "modelo": { "nome": "yolo26n-postes", "versao": "1.0" },
  "imagem_anonimizada_base64": null
}
```

### Campos que mais importam para cada componente

| Componente | Usa | Para quê |
|---|---|---|
| **Backend / app do cidadão** | `validacao.abrir_chamado`, `validacao.motivos` | Abrir o chamado ou dizer ao cidadão por que a foto não serviu ("parece ser de dia") |
| **RPA** | `prioridade.nivel`, `localizacao`, `id_captura` | Ordenar a fila, agrupar chamados do mesmo trecho e registrar no sistema da prefeitura (ex.: SP156) |
| **Big Data** | o JSON inteiro (Bronze) | Prata: tipar e deduplicar por `id_captura`; Ouro: fato `capturas` com dimensões tempo, local, origem e modelo |
| **GenAI** | é chamado pela Visão (`POST /consulta`) e aparece em `orientacao` | Prazo e canal oficiais com fonte citada, devolvidos junto com o chamado |
| **Maker Lab (robô)** | envia o alerta a `/v1/alerta-robo`; lê `acao_robo` | Acender o LED/buzzer certo; o ponto vira suspeita até uma foto confirmar |
| **DevOps** | `GET /saude` (health check) e `GET /metrics` | Grafana com as 4 métricas de ouro e os chamados por tipo/prioridade; alertas no Prometheus (ver `06-devops-cloud/`) |

### Campo `fusao` (novo na 1.1): sensor + foto

| Robô diz | Foto mostra | `tipos_chamado` | `confirmacao` |
|---|---|---|---|
| escuro | poste apagado | `conserto_poste` | `confirmado` |
| escuro | nenhum poste, cena escura | `instalacao_iluminacao` | `confirmado` |
| escuro | poste aceso, cena clara | `poda_ou_obstrucao` | `nao_confirmado` |
| buraco | buraco | `buraco` | `confirmado` |
| escuro + buraco | apagado + buraco | `conserto_poste`, `buraco` | `confirmado` (prioridade máxima: risco de queda) |
| buraco | sem buraco | — | `parcial` / `nao_confirmado` (segue como suspeita) |
| (nada) | — | conforme a foto | `sem_sensor` |
| qualquer | foto inválida (de dia, tremida) | — | `nao_confirmado`: a suspeita continua aberta |

```json
"fusao": {
  "alertas_sensor": ["escuro", "buraco"],
  "tipos_chamado": ["conserto_poste"],
  "confirmacao": "parcial",
  "motivos": ["poste apagado na foto: conserto", "escuro: a foto confirma o sensor de luz",
              "buraco: não aparece na foto; segue como suspeita"]
}
```

> A classe `buraco` entra no modelo no próximo treino (dataset público de buracos). Até lá, buraco só do
> ultrassônico fica como suspeita, que é o comportamento correto: não abrimos chamado sem prova.

### Novidades da 1.3
- **Breu como evidência:** foto noturna nítida com quase nenhuma luz (brilho < `limiar_breu`) e sem poste visível é
  aceita: o poste apagado não aparece no escuro. Tipo de chamado `trecho_sem_luz` (equipe inspeciona no local).
- **Sanidade:** caixas que cobrem mais de 50% da foto (`deteccao.area_maxima`) são descartadas: não são luminárias.
- **Endereço:** campo opcional `endereco` em `/v1/analisar` e `/v1/relatos`; volta em `localizacao.endereco`.
- **`POST /v1/relatos`** (JSON): `{"latitude": -23.56, "longitude": -46.65, "endereco": "Av. Paulista, 1578", "problema": ["escuro"]}`
  → mesma resposta do alerta do robô (`status: suspeita`, prioridade prévia, próximo passo).

### Campo `orientacao` (novo na 1.2): integração com o GenAI

Quando o chamado é aberto e o pedido traz `incluir_orientacao=true`, a Visão pergunta ao assistente do
**GenAI (01-generative-ai)** o prazo/canal oficial daquele tipo de serviço e devolve a resposta **com o trecho
da fonte oficial**. Se a base não cobre, vem `nao_consta` (não inventamos). Se o GenAI estiver desligado ou lento,
vem `indisponivel` e a análise continua normal.

```json
"orientacao": [
  {
    "tipo_chamado": "conserto_poste",
    "pergunta": "Qual o prazo para consertar a iluminação pública em São Paulo?",
    "status": "ok",
    "resposta": "Normalmente em até 24 horas.",
    "citacao": "SP-prazo",
    "trecho_citado": "São Paulo (capital): normalmente a manutenção da iluminação pública é concluída em até 24 horas. …",
    "aviso": "Pré-orientação automática. Confirme com o canal oficial da prefeitura (humano no circuito).",
    "motivo": null
  }
]
```

Como ligar (a API do GenAI usa a porta 8000 por padrão, então ela sobe na **8001**):
```bash
# terminal 1: GenAI (precisa do Ollama com qwen2.5:1.5b-instruct e nomic-embed-text)
cd 01-generative-ai && uvicorn src.api:app --port 8001
# terminal 2: Visão apontando para ele
cd 04-visao-computacional
GENAI_URL=http://localhost:8001 uvicorn api.main:app --port 8000      # PowerShell: $env:GENAI_URL="http://localhost:8001"
```
`GET /saude` mostra `"genai": {"configurado": true, "no_ar": true}`. As perguntas por tipo de chamado ficam em
`configs/regras.yaml` (`orientacao.perguntas`) e a cidade em `GENAI_CIDADE` (padrão São Paulo). Respostas
repetidas vêm do cache (o LLM roda com temperatura 0).

**Tempo de resposta (medido com o GenAI real, RTX 4060 Ti):** a 1ª pergunta leva ~100 s (o Ollama carrega o
modelo na GPU); com o modelo carregado, ~7 s; repetida, instantânea (cache). Por isso a Visão **aquece** o GenAI
ao subir: faz cada pergunta configurada em segundo plano. `GENAI_TIMEOUT` padrão: 120 s.

### `POST /v1/alerta-robo` (JSON, sem foto)

É o que o robô do Maker Lab chama quando o LDR ou o ultrassônico dispara. Funciona **mesmo sem o modelo
carregado**. Se `alerta` vier vazio, a API deduz pelas leituras (`sensor_lux < 5` → escuro;
`sensor_distancia_cm >= 15` → buraco; limiares em `configs/regras.yaml`).

```json
{"origem":"robo","latitude":-23.55,"longitude":-46.63,"sensor_lux":3.2,"sensor_distancia_cm":12,"alerta":["escuro","buraco"]}
```

Resposta (curta, para a placa ler):
```json
{
  "versao_contrato": "1.3", "recebido": true,
  "id_alerta": "1f0c…", "timestamp": "2026-11-10T21:40:12-03:00",
  "status": "suspeita",
  "alertas": ["escuro", "buraco"],
  "localizacao": {"latitude": -23.55, "longitude": -46.63, "fonte": "informada"},
  "prioridade_previa": {"nivel": "alta", "pontuacao": 85,
                        "fatores": ["o robô sinalizou 'escuro'", "o robô sinalizou 'buraco'", "+30: trecho escuro",
                                    "+30: possível buraco", "+25: buraco no escuro (risco de queda)"]},
  "proximo_passo": "aguardando foto de confirmação (cidadão próximo ou patrulha) para virar chamado",
  "acao_robo": "led_vermelho"
}
```

`acao_robo`: `led_vermelho` (prioridade alta), `led_amarelo` (suspeita registrada) ou `nenhuma` (`status: descartado`).

**Simulador** (testa tudo sem o robô físico):
```bash
uvicorn api.main:app --port 8000                     # terminal 1
python scripts/simular_robo.py                       # terminal 2: escuro, buraco, os dois, normal
python scripts/simular_robo.py --patrulha 20         # robô andando por uma rua
python scripts/simular_robo.py --cenario ambos --foto rua.jpg   # alerta + foto do mesmo ponto
```

Exemplo para o firmware (ESP32, Arduino IDE, bibliotecas `HTTPClient` e `ArduinoJson`):
```cpp
HTTPClient http;
http.begin("http://IP_DA_API:8000/v1/alerta-robo");
http.addHeader("Content-Type", "application/json");
String corpo = String("{\"origem\":\"robo\",\"latitude\":") + String(lat, 6) +
               ",\"longitude\":" + String(lon, 6) + ",\"sensor_lux\":" + String(lux, 1) +
               ",\"sensor_distancia_cm\":" + String(dist, 1) + "}";
if (http.POST(corpo) == 200) {
  JsonDocument resp; deserializeJson(resp, http.getString());
  String acao = resp["acao_robo"];            // "led_vermelho", "led_amarelo" ou "nenhuma"
  digitalWrite(LED_VERMELHO, acao == "led_vermelho");
  digitalWrite(LED_AMARELO,  acao == "led_amarelo");
}
http.end();
```

### Códigos de erro

| Código | Quando |
|---|---|
| `413` | Imagem maior que o limite |
| `415` | Arquivo não é JPEG, PNG ou WebP |
| `422` | Arquivo corrompido ou campo inválido (ex.: latitude 200, `alerta=fogo`) |
| `503` | Modelo não carregado (o `/saude` explica o motivo) |

## Regras de versão
- Campo novo **não quebra** ninguém: continua `1.x`.
- Remover ou renomear campo muda para `2.0` e precisa de aviso ao grupo antes.
- O modelo em uso aparece em `modelo.nome`/`modelo.versao`. Isso permite auditar qual versão decidiu cada chamado.

## Vídeo e robô (fluxo contínuo)
`scripts/tempo_real.py --eventos eventos.jsonl --webhook URL` gera **um evento por poste apagado confirmado**
(o mesmo poste rastreado em vários frames conta uma vez), no mesmo formato acima. O `--webhook` faz POST do JSON
para o backend, que pode tratar igual a uma foto de cidadão.

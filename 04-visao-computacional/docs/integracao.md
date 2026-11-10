# Integração: como os outros componentes usam a Visão

A Visão expõe **uma API HTTP** e **um formato de JSON** (o contrato, versão `1.0`).
Quem precisa saber se uma foto é evidência de rua escura chama a API. Ninguém precisa entender o YOLO.

```
App do cidadão ──foto + GPS──────────┐
Robô (Maker Lab) ──foto + lux + GPS──┼──► POST /v1/analisar ──► JSON do chamado ──► Backend / RPA / Big Data
Câmera fixa / vídeo ─────────────────┘                                                    │
                                                                                          ▼
                                                                        atendente da prefeitura confirma
```

## Endpoints

| Método | Rota | Para quê |
|---|---|---|
| `GET` | `/saude` | Status da API e do modelo (DevOps: health check e monitoramento) |
| `POST` | `/v1/analisar` | Analisa uma foto e devolve o JSON abaixo |
| `GET` | `/docs` | Documentação interativa (Swagger): dá para testar pelo navegador |

### `POST /v1/analisar` (multipart/form-data)

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `imagem` | arquivo | sim | JPEG, PNG ou WebP, até 10 MB |
| `origem` | texto | não | `cidadao` (padrão), `robo` ou `camera` |
| `latitude`, `longitude` | número | não | Se não vier, a API tenta usar o GPS do EXIF da foto |
| `sensor_lux` | número | não | Leitura do sensor de luz (LDR) do robô |
| `retornar_imagem` | bool | não | Devolve a foto com rostos borrados, em base64 |

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
  "versao_contrato": "1.0",
  "id_captura": "b58cccb5-ab16-43cb-8f35-180c00b2939d",
  "timestamp": "2026-11-09T22:12:45-03:00",
  "hora_captura": null,
  "origem": "robo",
  "localizacao": { "latitude": -23.5505, "longitude": -46.6333, "fonte": "informada" },
  "sensor_lux": 2.4,
  "deteccoes": [
    { "classe": "poste_apagado", "confianca": 0.91, "bbox": [412, 88, 470, 410], "id_rastreio": null },
    { "classe": "poste_aceso",   "confianca": 0.88, "bbox": [120, 60, 170, 400], "id_rastreio": null }
  ],
  "resumo": { "postes_acesos": 1, "postes_apagados": 1, "luminosidade_media": 44.7, "status_trecho": "escura" },
  "validacao": {
    "foto_valida": true,
    "falha_detectada": true,
    "abrir_chamado": true,
    "motivos": ["1 poste(s) apagado(s) detectado(s)", "trecho classificado como escuro",
                "sensor de luz do robô marcou 2.4 lux"]
  },
  "prioridade": {
    "nivel": "alta",
    "pontuacao": 75,
    "fatores": ["+25: 1 poste(s) apagado(s)", "+30: trecho escuro", "+20: sensor de luz abaixo de 5.0 lux"]
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
| **GenAI** | `resumo`, `validacao.motivos`, `prioridade.fatores` | Gerar o texto do chamado e responder ao cidadão com base em dados, sem inventar |
| **Maker Lab (robô)** | envia `sensor_lux` + foto; lê `status_trecho` | Decidir a ação do robô (alerta, LED, voz) a partir do que a câmera viu |
| **DevOps** | `GET /saude`, código HTTP, latência | Health check, dashboard das 4 métricas de ouro, alerta se `modelo_carregado=false` |

### Códigos de erro

| Código | Quando |
|---|---|
| `413` | Imagem maior que o limite |
| `415` | Arquivo não é JPEG, PNG ou WebP |
| `422` | Arquivo corrompido ou campo inválido (ex.: latitude 200) |
| `503` | Modelo não carregado (o `/saude` explica o motivo) |

## Regras de versão
- Campo novo **não quebra** ninguém: continua `1.x`.
- Remover ou renomear campo muda para `2.0` e precisa de aviso ao grupo antes.
- O modelo em uso aparece em `modelo.nome`/`modelo.versao`. Isso permite auditar qual versão decidiu cada chamado.

## Vídeo e robô (fluxo contínuo)
`scripts/tempo_real.py --eventos eventos.jsonl --webhook URL` gera **um evento por poste apagado confirmado**
(o mesmo poste rastreado em vários frames conta uma vez), no mesmo formato acima. O `--webhook` faz POST do JSON
para o backend, que pode tratar igual a uma foto de cidadão.

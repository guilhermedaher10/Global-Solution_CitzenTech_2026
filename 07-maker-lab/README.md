# CitizenTech — Robô de monitoramento de iluminação e obstáculos

**FIAP · Global Solution 2026.2 · Maker Lab**

Protótipo de carrinho robótico com **ESP32**, sensor digital de luminosidade **LDR**, sensor ultrassônico **HC-SR04**, módulo **GPS NEO-6M** e driver de motores **L298N**. O projeto utiliza uma rede neural supervisionada de pequeno porte (**TinyML**) para classificar situações combinando iluminação e distância, e disponibiliza leituras, classificações e alertas em um painel web acessível pelo celular.

## Vídeo de demonstração

[**Assistir à demonstração do protótipo no YouTube**](https://youtube.com/shorts/BpEB6Awb1jY?feature=share)

O vídeo apresenta o funcionamento do carrinho, as informações dos sensores, o monitoramento no terminal e a integração da IA embarcada.

## Equipe

| Integrante | RM |
|---|---|
| Guilherme Daher | 98611 |
| Gabriel Freitas | 550187 |
| Heitor Nobre | 551539 |
| Vinicius Yamashita | 550908 |
| Lucca Alexandre | 99700 |

## Problema e proposta

Áreas com iluminação insuficiente e obstáculos podem dificultar a circulação em espaços urbanos. Como proposta de **CitizenTech**, desenvolvemos um protótipo educacional para monitorar condições ambientais, classificar cenários e disponibilizar alertas contextualizados. A solução se relaciona ao **ODS 11 — Cidades e comunidades sustentáveis**.

## Componentes e ligações

| Componente | Conexão ao ESP32 |
|---|---|
| LDR digital LM393 — saída DO | GPIO34 (D34); alimentação 3,3 V e GND |
| HC-SR04 | TRIG GPIO26; ECHO GPIO25; VCC 5 V e GND |
| GPS NEO-6M | TX do GPS no GPIO16 (RX2); RX opcional no GPIO17; GND comum |
| Driver L298N | IN1 GPIO18, IN2 GPIO5, IN3 GPIO12, IN4 GPIO14 |
| Motores DC | Conectados às saídas do driver L298N |

**Cuidados elétricos:** o sinal ECHO de 5 V do HC-SR04 deve ser reduzido para 3,3 V antes de entrar no ESP32. Não conecte 5 V diretamente a um GPIO. A alimentação do GPS depende da placa adaptadora usada. Os GPIOs 5 e 12 podem influenciar a inicialização do ESP32.

## Arquitetura

```text
LDR digital ───────┐
                   ├─> ESP32 ─> janela de leituras ─> MLP TinyML ─> classificação e alerta
HC-SR04 ──────────┘      │                                   │
                          ├─> painel web local <───────────────┘
GPS NEO-6M ───────────────┤    (localização quando há fix GPS)
                          └─> controle manual ─> driver L298N ─> motores
```

O painel apresenta as leituras dos sensores, a classe prevista, a confiança do modelo, o número de inferências e informações do GPS quando disponíveis. O módulo GPS recebe sinais de satélite **sem precisar de internet**; abrir mapas online, porém, pode exigir conexão à internet.

## Modelo de IA (TinyML)

A IA foi treinada em **Python** usando `scikit-learn` (`MLPClassifier`) e seus parâmetros foram exportados para o arquivo `ModeloTreinado.h`, utilizado diretamente pelo firmware C++ do ESP32. A inferência ocorre **localmente**, sem Python nem internet no carrinho.

**Classes:**

- `claro_livre`
- `claro_obstaculo`
- `escuro_livre`
- `escuro_obstaculo`

A cada aproximadamente 100 ms, o sistema obtém novas leituras. A janela de dez amostras resume quatro características: **distância média, distância mínima, desvio-padrão da distância e proporção de leituras escuras**. A MLP utiliza quatro entradas, doze neurônios ocultos (ReLU) e quatro saídas (softmax), produzindo uma classificação e uma pontuação de confiança. O sistema monitora também estabilidade e atualidade das inferências.

O conjunto preparado para treinamento/teste está em `dados/treino/` e `dados/teste/`. A avaliação registrada em `resultado_treinamento.json` apresenta **40 janelas de teste e acurácia de 100% nesse conjunto**. Trata-se do resultado desse teste específico, e não de uma medição de precisão em operação urbana real.

### Reproduzir o treinamento

Com Python instalado, abra um terminal na pasta do projeto:

```powershell
py -m pip install -r requirements.txt
py treinar_modelo.py
```

O script lê os CSVs, treina o modelo, gera `resultado_treinamento.json` e exporta os pesos em `ModeloTreinado.h`. **O repositório já inclui um `ModeloTreinado.h` preenchido**, correspondente ao modelo fornecido para a versão final.

## Como executar no ESP32

1. Instale o **Arduino IDE**, o pacote **ESP32 by Espressif Systems** e a biblioteca **TinyGPSPlus**.
2. Abra `MakerLab_Controle_Independente_TinyML.ino` na Arduino IDE, mantendo todos os `.h` na mesma pasta.
3. Confira as definições em `Config.h`:

   ```cpp
   #define USAR_TINYML 1
   #define HABILITAR_MOTORES 1
   #define CONTROLE_MANUAL_INDEPENDENTE 1
   ```

4. Selecione a placa/porta correta e envie o firmware ao ESP32.
5. Abra o **Monitor Serial em 115200 baud** para acompanhar a inicialização, leituras e inferências.
6. No iPhone, conecte-se à rede **Carrinho-ESP32** (senha padrão `12345678`), abra o Safari e acesse **http://192.168.4.1**. O painel local funciona mesmo que o telefone indique ausência de internet.

Também é possível configurar `WIFI_CASA_SSID` e `WIFI_CASA_SENHA` em `Config.h` para o ESP32 acessar uma rede doméstica **2,4 GHz**. Nesse caso, utilize o IP exibido no Monitor Serial. 

### Modos de controle

- `CONTROLE_MANUAL_INDEPENDENTE=1`: o operador movimenta o carrinho pelas setas do painel, enquanto sensores e TinyML **continuam monitorando e classificando em paralelo**. Nessa configuração, a classificação não determina o movimento dos motores.
- `CONTROLE_MANUAL_INDEPENDENTE=0`: utiliza o modo de **controle assistido**, no qual a lógica de sensores e da IA pode restringir o avanço.

O carrinho não possui navegação autônoma. Antes de testes motorizados, faça a primeira verificação com as rodas suspensas e supervisão.

## Organização dos arquivos

```text
MakerLab_Controle_Independente_TinyML/
├── MakerLab_Controle_Independente_TinyML.ino  # firmware principal
├── Config.h                                  # pinos, Wi-Fi e opções
├── Controle.h                                # lógica dos motores
├── Pagina.h                                  # interface web
├── ModeloTreinado.h                          # pesos da rede neural
├── treinar_modelo.py                         # treinamento/exportação
├── resultado_treinamento.json                # métricas do treinamento
├── requirements.txt                          # dependências Python
├── dados/
│   ├── treino/                              # CSVs de treinamento
│   └── teste/                               # CSVs de avaliação
├── COMO_TESTAR.md
└── README.md
```



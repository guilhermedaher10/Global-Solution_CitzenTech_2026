# 03 · Negócio e Pitch — Vésper

**Disciplina:** Business Intelligence & Startup Development · **Professor:** André Maluf
**Responsável:** Lucca Alexandre · RM 99700

🎬 **Vídeo pitch:** https://youtu.be/1hk3eRDgr4I
🌐 **MVP no ar:** https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io

---

## Por que o Vésper merece existir

### O problema, com evidência

- **Rua escura gera crime e acidente.** Num experimento aleatório em Nova York, instalar iluminação reduziu em pelo menos **36%** os crimes graves noturnos ao ar livre ([NBER, Chalfin et al., 2019](https://www.nber.org/papers/25798)).
- **Quando falta energia, a cidade para.** No apagão de outubro de 2024, cerca de **3,1 milhões de imóveis** ficaram sem luz na Grande São Paulo ([Folha PE](https://www.folhape.com.br/noticias/apagao-sp-casos/367352/)), e o varejo e os serviços da capital perderam cerca de **R$ 1,65 bilhão** ([Agência Brasil, dados da FecomercioSP](https://agenciabrasil.ebc.com.br/radioagencia-nacional/economia/audio/2024-10/apagao-em-sao-paulo-gera-r-16-bilhao-de-prejuizo-ao-comercio)).
- **A falha demora a chegar a quem conserta.** No SP156 de jul–set/2026, a cidade abriu **1.113 chamados de poste e fiação**; só **119** foram fechados no período, e 10% dos fechados levaram mais de **41 dias** (pipeline de [Big Data](../02-big-data/README.md)).

### A solução e a proposta de valor

O Vésper é a **ponte entre quem está no escuro e quem pode acender a rua**. O cidadão aponta o celular para a rua e, em segundos, o chamado chega **confirmado por IA**, com localização, evidência, prioridade e **para o responsável certo**: poste apagado vai para a iluminação pública, apagão vai para a distribuidora de energia. Sem cadastro, sem instalar app e sem guardar a foto.

---

## Modelo de negócio

**Quem usa não paga:** o cidadão reporta de graça, pelo navegador ou por um QR Code colado no poste.
**Quem paga é quem tem a obrigação de acender a rua**, por assinatura (SaaS).

| Frente | Cliente | Como paga | O que recebe |
|---|---|---|---|
| **B2G** (principal) | Prefeituras e concessionárias de iluminação pública | Assinatura mensal por cidade, que pode ser custeada pela **COSIP**, a contribuição de iluminação pública que o município já arrecada na conta de luz | Central de chamados confirmados por IA, painel de indicadores e integração com o sistema do órgão (ex.: 156) |
| **B2B** | Distribuidoras de energia (ex.: Enel) | Assinatura mensal de dados | Alertas em tempo real de apagões e dos pontos sem energia relatados e confirmados |
| **B2C** (possibilidade futura) | Cidadão | Venda de hardware | Dispositivo que se pluga na tomada e avisa o celular quando a energia cai, com opção de kit de emergência (power bank, lanterna e cabo) |

### Go-to-market

1. **Piloto gratuito de 90 dias** em um distrito com muita falha de iluminação, com QR Codes nos postes.
2. **Prova com números:** tempo até o conserto e % de chamados fechados, comparados com a linha de base do SP156.
3. **Contratação** pelo Contrato Público de Solução Inovadora (CPSI) do **Marco Legal das Startups** (Lei Complementar 182/2021), que permite ao poder público testar startups sem a licitação tradicional.
4. **Expansão** para outras cidades e para as distribuidoras de energia.

---

## Indicadores

| Tipo | Indicador | Linha de base (SP156, jul–set/2026) |
|---|---|---|
| Impacto | Tempo da falha até o fechamento do chamado | Mediana de 11 dias; 10% passam de 41 dias |
| Impacto | % de chamados fechados | 119 de 1.113 chamados de poste e fiação |
| Impacto | Chamados por 100 mil habitantes, Centro × Periferia | Centro 16,3 × Periferia 9,5 |
| Impacto | % de chamados válidos (a IA filtra foto de dia, repetida ou sem evidência) | Medido na central do Vésper |
| Negócio | Cidades e distribuidoras pagantes | — |
| Negócio | Chamados por mês na plataforma | Central ao vivo (aba Indicadores do site) |
| Negócio | Custo por chamado (nuvem ÷ análises) | Centavos (~1.000 análises/mês dentro da cota grátis) |

**Leitura do Centro × Periferia:** a periferia registra quase metade dos chamados por habitante. A hipótese é que ela não tem menos poste quebrado, e sim que reclamar é mais difícil. Baixar essa barreira é o papel do Vésper.

### ODS

| ODS | Como o Vésper contribui |
|---|---|
| **11** · Cidades sustentáveis | Encurta o tempo entre a rua apagar e o conserto |
| **3** · Saúde e bem-estar | Rua iluminada reduz atropelamentos e quedas à noite |
| **10** · Redução das desigualdades | Basta um celular e um navegador; mede a diferença centro × periferia |
| **9** · Infraestrutura | Transforma relatos soltos em dados confiáveis para a manutenção |
| **16** · Instituições eficazes | Protocolo e acompanhamento de cada etapa do chamado |

---

## Viabilidade e pedido

- **Custo de operação:** de **R$ 28 a R$ 150 por mês** de nuvem (Azure), porque o serviço desliga sozinho quando ninguém usa ([estimativa do DevOps](../06-devops-cloud/docs/custo.md)).
- **Receita:** assinatura mensal por cidade e por distribuidora. Com poucas cidades pagando, a receita cobre a nuvem muitas vezes e passa a pagar a equipe. O valor da assinatura é uma premissa a validar no piloto.
- **Próximo passo (o pedido):** um piloto de 90 dias em um distrito, com a prefeitura ou a concessionária de iluminação, para provar a redução do tempo de reparo.

---

## Roteiro do pitch (5 minutos)

| Tempo | Bloco |
|---|---|
| 0:00 | O cidadão e o problema, com um dado que prove a dor |
| 0:30 | A solução e a proposta de valor |
| 1:00 | Demonstração do MVP na URL pública |
| 2:30 | Modelo de negócio: quem paga, quem usa e como chega |
| 3:30 | Indicadores de negócio e de impacto, e os ODS |
| 4:15 | Viabilidade e pedido: custo, receita e próximo passo |

---

## Equipe

| Nome completo | RM |
|---|---|
| Guilherme Daher | 98611 |
| Gabriel Freitas | 550187 |
| Heitor Nobre | 551539 |
| Vinicius Yamashita | 550908 |
| Lucca Alexandre | 99700 |

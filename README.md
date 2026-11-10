# GS 2026.2 · CitizenTech · Ruas Escuras

Global Solution da FIAP · Engenharia de Software, 4º ano.
Um único produto que atravessa 7 disciplinas: cada integrante cuida de uma pasta.

## Problema
Ruas com iluminação pública falha geram medo, aumentam o risco de assalto e causam acidentes
(quedas de pedestres, ciclistas e motociclistas). Isso afeta o bem-estar e a mobilidade das pessoas.
Além disso, a falha demora a chegar até a prefeitura, porque depende de alguém reclamar.

## Solução
Nós não consertamos o poste: somos a **ponte entre o cidadão e a prefeitura**.

- **Cidadão:** reporta a rua escura com uma foto (ou um robô com câmera e sensor de luz detecta sozinho) e acompanha o status até o conserto.
- **Prefeitura:** recebe o chamado já confirmado, com localização, evidência e prioridade.

## ODS
- **ODS 11:** cidades e comunidades sustentáveis
- **ODS 3:** saúde e bem-estar (acidentes)
- **ODS 10:** redução das desigualdades
- **ODS 9:** indústria, inovação e infraestrutura

## Integrantes

| Nome completo | RM | Disciplina |
|---|---|---|
| Guilherme Gonçalves Calil Daher | 98611 | Visão Computacional |
| | | |
| | | |
| | | |
| | | |

## Pastas

| Pasta | Disciplina |
|---|---|
| `01-generative-ai/` | Generative AI |
| `02-big-data/` | Big Data |
| `03-negocio-pitch/` | Negócio e Pitch |
| `04-visao-computacional/` | Visão Computacional |
| `05-rpa/` | RPA |
| `06-devops-cloud/` | DevOps e Cloud |
| `07-maker-lab/` | Maker Lab |

## Como cada um commita

```bash
git clone https://github.com/guilhermedaher10/Global-Solution_CitzenTech_2026.git
cd Global-Solution_CitzenTech_2026

git pull                          # sempre antes de começar
# trabalhe só dentro da pasta da sua disciplina
git add 05-rpa/                   # adicione só a sua pasta
git commit -m "rpa: primeira versão"
git pull                          # de novo, antes de enviar
git push
```

- Mexa **só na sua pasta**. Se precisar mudar algo na raiz ou na pasta de outro, avise no grupo.
- Comece a mensagem do commit pelo nome da pasta (`rpa:`, `big-data:`, `visao:`...).
- Nunca commite senha, chave de API ou `.env`.
- Arquivos grandes (dataset, modelo pesado, vídeo) vão por link (Drive, YouTube), não pro Git.

**Entrega:** 19/11/2026, até 23h55. O repositório precisa estar público durante a correção.

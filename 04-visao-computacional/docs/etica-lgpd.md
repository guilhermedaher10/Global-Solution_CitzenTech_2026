# IA responsável, privacidade e LGPD

## O que o modelo faz e o que ele NÃO faz
- **Faz:** detecta postes e diz se estão acesos ou apagados. Mede o brilho da cena.
- **Não faz:** não reconhece pessoas, não identifica rostos nem placas e não julga se um lugar ou alguém é "perigoso".
  Esses usos foram descartados de propósito no desenho do produto.

## Pessoa no circuito
O modelo **sugere**; quem decide é gente. O JSON traz `abrir_chamado` e `prioridade`, mas o chamado só é
encaminhado ao conserto depois que um atendente da prefeitura (ou da concessionária) confirma. Toda decisão vem com
`motivos` e `fatores` legíveis, então dá para contestar e auditar.

## Minimização de dados (LGPD, art. 6º, III)
| Dado | O que fazemos |
|---|---|
| Rostos que aparecem por acaso | Borrados antes de qualquer imagem sair do componente (`privacidade.py`) |
| EXIF (modelo do celular, nº de série, data, GPS) | Lemos só GPS e hora, que servem ao chamado; o resto é descartado. A imagem que sai não tem EXIF |
| A foto em si | A API **não armazena**. Se a prefeitura quiser guardar a evidência, a decisão e a base legal são dela |
| Identidade do cidadão | A Visão não recebe nome, CPF nem telefone. Isso fica no backend, separado |

Base legal sugerida para o produto: execução de políticas públicas (art. 7º, III) para a prefeitura;
consentimento informado no app para o envio da foto e da localização.

## Vieses conhecidos e como medimos
| Risco | Efeito | Mitigação |
|---|---|---|
| Dataset com mais fotos do exterior (Flickr, Wikimedia) | Pior em postes brasileiros (braço curvo, luminária LED da PPP) | Incluir imagens brasileiras e medir separado (`--teste-fonte`) |
| Poste apagado à noite é quase invisível | Recall baixo em `poste_apagado` | A regra do trecho usa também o brilho da cena e o sensor do robô |
| Bairros com menos gente usando o app | Menos chamados onde talvez mais falte luz (ODS 10) | O robô e as câmeras fazem varredura ativa; o Big Data compara chamados por região com a população |
| Foto falsa ou de dia | Chamado sem fundamento | Validação recusa foto diurna, pequena, tremida ou sem poste |

## Transparência para o cidadão
Quando a foto é recusada, o app mostra o motivo em linguagem simples (vem pronto em `validacao.motivos`),
por exemplo "a foto parece ter sido tirada de dia". Ninguém fica sem resposta.

## Licenças das imagens
Imagens de terceiros ficam fora do repositório. As da web vêm de Openverse e Wikimedia Commons, com autor e
licença registrados em `data/bruto/web/manifesto.csv`. Os datasets do Roboflow são citados em `docs/dataset.md`.

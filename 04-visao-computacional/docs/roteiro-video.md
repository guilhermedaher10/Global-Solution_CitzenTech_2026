# Roteiro do vídeo: Vésper · Visão Computacional (3 a 4 minutos)

Grave a tela com OBS (gratuito) em 1080p e o celular com o espelhamento do Windows (ou filme o celular).
Fale pouco e mostre muito. Suba no YouTube como **não listado** e teste o link numa aba anônima.

Os dois requisitos da disciplina precisam aparecer com clareza:
1. **Treinamento customizado** de um detector (YOLO26), mostrado nas cenas 3 e 4.
2. **Tempo real com técnicas avançadas e realidade aumentada**, mostrado nas cenas 5 e 6.

| Tempo | Cena | Na tela | Fala (resumo) |
|---|---|---|---|
| 0:00 | **1. Problema** | Uma rua escura de verdade, filmada por você à noite | "Rua escura dá medo e causa acidente. Quando falta luz, ninguém sabe para quem ligar, e a reclamação chega sem prova e sem endereço." |
| 0:20 | **2. Vésper** | Site no celular, tela Início, com o dedo no botão **"Estou no escuro agora"** | "O Vésper é a ponte entre quem está no escuro e quem pode resolver. Basta um navegador, sem cadastro e sem instalar nada." |
| 0:35 | **3. Dados e treino** | `docs/img/deteccao/val_batch0_pred.jpg`, depois a tabela de resultados do README | "Treinamos um YOLO26s com 1.137 imagens: datasets públicos, imagens com licença aberta e fotos noturnas da equipe. O poste apagado é a classe difícil, então criamos exemplos sintéticos só no treino." |
| 1:00 | **4. Resultado honesto** | Tabela do detector: mAP50 0,49, aceso 0,84, 4,6 ms em GPU | "No teste com 152 fotos nunca vistas, o poste aceso tem AP50 de 0,84. O apagado é uma silhueta no escuro, e por isso criamos uma segunda IA." |
| 1:15 | **5. Leitura da cena** | Matriz de confusão da fusão (`docs/img/cena/matriz_test_fusao_detector.png`) | "Um classificador YOLO26n-cls diz se a cena é rua iluminada, trecho escuro ou apagão. Vetos físicos evitam erros: poste aceso na foto quer dizer que a rede tem energia. Acerto de 81%, contra 72% só com regras." |
| 1:40 | **6. Tempo real + RA** | `tempo_real.py` num vídeo noturno: caixas, ids #1 a #7, painel mudando, 11 FPS | "Em tempo real, cada poste ganha um id e é contado uma vez no trajeto. O painel em realidade aumentada mostra o trecho, a leitura da região e o chamado gerado, com os rostos borrados." |
| 2:15 | **7. Ao vivo no celular** | Na rua (ou no protótipo): **Estou no escuro agora** → grava 5 s → envio automático → protocolo **VSP-…** e **"Para onde o chamado vai"** | "O cidadão filma alguns segundos. A IA analisa um quadro a cada meio segundo, escolhe a melhor prova e apaga o vídeo. O chamado já sai com protocolo e órgão responsável." |
| 2:45 | **8. Acompanhar** | Tocar em **Acompanhar chamado**: linha do tempo, mapa, vizinhos | "Com o protocolo, o cidadão acompanha cada etapa e vê quantos vizinhos relataram o mesmo problema." |
| 3:00 | **9. Central** | Aba **Central** no computador: **"Possível apagão em Capão Redondo"** → Enel e Defesa Civil; **"Trecho escuro recorrente"** → SP156; mudar um status | "Na central, relatos próximos viram um alerta de região, e cada um vai ao órgão certo: poste para a prefeitura, apagão para a Enel." |
| 3:25 | **10. Responsável e fechamento** | Foto de dia recusada com o motivo, depois a selagem "Vídeo não guardado · Nenhum rosto" e a tela Início com o lema | "Foto de dia não vira chamado, nenhum rosto aparece e nada fica guardado. Vésper: da escuridão à luz." |

## Checklist antes de gravar

**No dia anterior**
- [ ] Testar o site no celular, com 4G e Wi-Fi: https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io
- [ ] Ver se `/saude` responde `"modelo_carregado": true`
- [ ] Ter um vídeo noturno com pelo menos 2 postes apagados para o `tempo_real.py`, gravado como backup com `--salvar results/demo.mp4`
- [ ] Separar uma foto diurna para a cena da recusa

**Central limpa e pronta para a cena 9**
- [ ] Zerar e semear de uma vez: `python scripts/demo_central.py --url <URL do site> --limpar`. O comando apaga os
  chamados de teste e cria "Possível apagão em Capão Redondo". Ele precisa do `CENTRAL_TOKEN` no `.env` e no segredo
  do GitHub; o script para criar o segredo já está pronto. Sem o token, rode sem `--limpar`: os chamados antigos continuam lá.
- [ ] Fazer 3 relatos perto um do outro com postes acesos ao fundo, para aparecer "Trecho escuro recorrente"

**Na hora**
- [ ] Celular com o brilho no máximo, o modo "não perturbe" ligado e a permissão de câmera e GPS já aceita
- [ ] Para filmar na rua à noite, ir acompanhado e escolher um lugar seguro
- [ ] Gravar em blocos, cena por cena, e juntar depois no editor (o Clipchamp, que vem no Windows, resolve)
- [ ] Revisar se nenhum rosto ou placa aparece sem borrão no vídeo final

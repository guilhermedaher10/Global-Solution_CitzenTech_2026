"""Gera base/trechos.jsonl e base/fontes.csv a partir das páginas oficiais lidas em 09/11/2026.
Cada trecho: id, fonte, ref, texto. Rodar: python src/build_base.py
"""
import json, csv, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
POA = "https://prefeitura.poa.br/carta-de-servicos/"

# (slug, título, descrição, prazo, extra_responsavel)
SERV = [
    ("iluminacao-publica-luminaria-apagada-durante-noite", "Luminária Apagada Durante a Noite",
     "Serviço de troca de lâmpadas apagadas em vias públicas, vias de pedestres, praças e parques e ciclovias, durante a noite.",
     "O prazo de atendimento pode variar de 06 (seis) horas até 15 (quinze) dias corridos, conforme a criticidade e a complexidade do serviço."),
    ("iluminacao-publica-luminaria-oscilante", "Luminária Oscilante",
     "A lâmpada acende e apaga de forma intermitente (piscando) durante o dia e à noite.",
     "O prazo de atendimento pode variar de 06 (seis) horas até 15 (quinze) dias corridos, conforme a criticidade e a complexidade do serviço."),
    ("iluminacao-publica-luminaria-ausente", "Luminária Ausente",
     "Solicitação de reposição de luminária em ponto já existente.",
     "O prazo de atendimento pode variar de 06 (seis) horas até 15 (quinze) dias corridos, conforme a criticidade e a complexidade do serviço."),
    ("iluminacao-publica-luminaria-acesa-durante-o-dia", "Luminária Acesa Durante o Dia",
     "A lâmpada permanece acesa durante o dia.",
     "Os prazos de atendimento são conforme níveis de criticidade, de 06 (seis) horas até 15 (quinze) dias corridos, dependendo da complexidade."),
    ("iluminacao-publica-luminaria-ou-braco-pendurado", "Luminária ou Braço Pendurado",
     "Serviço de conserto de luminária ou braço pendurado ou quebrado.",
     "O prazo de atendimento é de até 06 (seis) horas."),
    ("iluminacao-publica-luminaria-faiscando", "Luminária Faiscando",
     "Conserto na iluminação quando há faíscas na ligação entre o fio e a luminária.",
     "O prazo de atendimento é de até 06 (seis) horas."),
    ("vias-ou-passeios-obstruidos-por-equipamentos-de-iluminacao-publica", "Vias ou Passeios Obstruídos por Equipamentos de Iluminação Pública",
     "Solicitação de retirada de equipamentos de iluminação pública que obstruam as vias públicas, vias de pedestres, praças, parques e ciclovias.",
     "O prazo de atendimento é de até 06 (seis) horas."),
    ("poste-caido-torto-ou-danificado-de-iluminacao-publica", "Poste Caído, Torto ou Danificado (de Iluminação Pública)",
     "Poste de iluminação pública com avaria, caído ou com risco de queda.",
     "Os prazos de atendimento são de até 06 horas."),
]

KEYS = {s[0]: k for s, k in zip(SERV, ["apagada","oscilante","ausente","acesa-dia","pendurado","faiscando","obstruidos","poste-caido"])}

COMUM = ("O serviço pode ser solicitado pelo telefone, pelo 156WEB ou pelo portal IPSul POA Iluminada. "
         "Documentos necessários: dados pessoais (nome completo, telefone, endereço) e o endereço da ocorrência. "
         "A solicitação é feita por um desses canais e depois é feita a programação e execução do serviço.")

trechos = []
for slug, titulo, desc, prazo in SERV:
    key = KEYS[slug]
    ref = f"Carta de Serviços de Porto Alegre, '{titulo}'"
    trechos.append(dict(id=f"POA-{key}-descricao", fonte="F1", ref=ref,
        texto=f"Porto Alegre, serviço de iluminação pública '{titulo}'. {desc} Responsável: Secretaria Municipal de Serviços Urbanos (SMSURB)."))
    trechos.append(dict(id=f"POA-{key}-prazo", fonte="F1", ref=ref,
        texto=f"Porto Alegre, '{titulo}'. {prazo}"))
    trechos.append(dict(id=f"POA-{key}-canais", fonte="F1", ref=ref,
        texto=f"Porto Alegre, '{titulo}'. {COMUM} O serviço é prestado por contrato de Parceria Público-Privada (PPP)."))

trechos += [
    dict(id="POA-contato-smsurb", fonte="F1", ref="Carta de Serviços de Porto Alegre (seção Dúvidas)",
         texto="Porto Alegre, dúvidas sobre serviços de iluminação pública: SMSURB, telefone 156 (opção 8) ou 0800 000 1740 (ligação gratuita). Para ligações de outras cidades: (51) 3289 0156."),
    dict(id="POA-legislacao", fonte="F1", ref="Carta de Serviços de Porto Alegre (campo Legislação)",
         texto="Porto Alegre: nas páginas de serviços de iluminação pública da Carta de Serviços, o campo Legislação não traz nenhuma lei ou decreto citado."),
    dict(id="POA-atualizacao", fonte="F1", ref="Carta de Serviços de Porto Alegre (campo Atualizado em)",
         texto="Porto Alegre: as páginas de iluminação pública da Carta de Serviços constam como atualizadas em 10/08/2021."),
    dict(id="SP-responsavel", fonte="F2", ref="SP Regula, Entenda os tipos de não conformidades na iluminação pública",
         texto="São Paulo (capital): a SP Regula faz rondas diárias e a manutenção da iluminação pública, trocando lâmpadas com mau funcionamento e vistoriando a fiação correspondente."),
    dict(id="SP-prazo", fonte="F2", ref="SP Regula, Entenda os tipos de não conformidades na iluminação pública",
         texto="São Paulo (capital): normalmente a manutenção da iluminação pública é concluída em até 24 horas. Fatores externos podem estender esse prazo."),
    dict(id="SP-causas", fonte="F2", ref="SP Regula, Entenda os tipos de não conformidades na iluminação pública",
         texto="São Paulo (capital): a queda de árvores, o furto de cabos ou fenômenos naturais podem atrasar os reparos da iluminação pública. O furto ou vandalismo de fiação também é causa possível de defeito."),
    dict(id="SP-canais", fonte="F2", ref="SP Regula, Entenda os tipos de não conformidades na iluminação pública",
         texto="São Paulo (capital): a solicitação de serviço de iluminação pública é feita pelo telefone 156 ou pelo 0800 779 0156."),
]

with open(RAIZ / "base" / "trechos.jsonl", "w", encoding="utf-8") as f:
    for t in trechos:
        f.write(json.dumps(t, ensure_ascii=False) + "\n")

fontes = [
    ("F1", "Carta de Serviços da Prefeitura de Porto Alegre – Iluminação Pública (8 páginas de serviço)", POA + "…", "HTML (site oficial)", "Informação pública de órgão oficial; uso com citação da fonte", sum(t["fonte"] == "F1" for t in trechos)),
    ("F2", "SP Regula – Entenda os tipos de não conformidades na iluminação pública (São Paulo)", "https://prefeitura.sp.gov.br/web/spregula/w/iluminacao_publica/335723", "HTML (site oficial)", "Informação pública de órgão oficial; uso com citação da fonte", sum(t["fonte"] == "F2" for t in trechos)),
]
with open(RAIZ / "base" / "fontes.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["fonte", "titulo", "url", "formato", "licenca", "n_trechos"]); w.writerows(fontes)
print(len(trechos), "trechos")

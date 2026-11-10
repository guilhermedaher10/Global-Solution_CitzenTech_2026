"""Gera avaliacao/conjunto_teste.jsonl (gabarito deterministico). Rodar: python src/build_teste.py"""
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
H6 = r"(06|\b6\b|seis)\s*(\(seis\)\s*)?horas"
D15 = r"(15|quinze)\s*(\(quinze\)\s*)?dias"
POA_CANAIS = ["POA-%s-canais" % k for k in ["apagada","oscilante","ausente","acesa-dia","pendurado","faiscando","obstruidos","poste-caido"]]
POA_DESC = ["POA-%s-descricao" % k for k in ["apagada","oscilante","ausente","acesa-dia","pendurado","faiscando","obstruidos","poste-caido"]]
A = lambda id,s,q,f,c: dict(id=id,split=s,tipo="resposta",pergunta=q,fontes=f,chaves=c)
N = lambda id,s,q: dict(id=id,split=s,tipo="nao_consta",pergunta=q,fontes=[],chaves=[])
T = [
 A("q01","teste","Qual o prazo de atendimento para um poste de iluminação caído em Porto Alegre?",["POA-poste-caido-prazo"],[H6]),
 A("q02","dev","Em Porto Alegre, qual o prazo para trocar uma lâmpada apagada durante a noite?",["POA-apagada-prazo"],[H6,D15]),
 A("q03","teste","Quem é o órgão responsável pela iluminação pública em Porto Alegre?",POA_DESC+["POA-contato-smsurb"],[r"SMSURB|Serviços Urbanos"]),
 A("q04","teste","Como solicito o conserto de uma luminária faiscando em Porto Alegre?",["POA-faiscando-canais"],[r"156|IPSul"]),
 A("q05","dev","Qual o telefone gratuito para tirar dúvidas sobre iluminação pública em Porto Alegre?",["POA-contato-smsurb"],[r"0800 000 1740"]),
 A("q06","teste","Qual o prazo para consertar uma luminária ou braço pendurado em Porto Alegre?",["POA-pendurado-prazo"],[H6]),
 A("q07","teste","Que documentos preciso para pedir um serviço de iluminação pública em Porto Alegre?",POA_CANAIS,[r"endere[çc]o",r"telefone|nome"]),
 A("q08","dev","Qual o prazo quando a lâmpada está piscando em Porto Alegre?",["POA-oscilante-prazo"],[H6,D15]),
 A("q09","teste","Quanto tempo leva para resolver lâmpada acesa durante o dia em Porto Alegre?",["POA-acesa-dia-prazo"],[D15]),
 A("q10","teste","Qual o prazo para repor uma luminária ausente em um ponto já existente em Porto Alegre?",["POA-ausente-prazo"],[D15]),
 A("q11","teste","Qual o prazo para retirar equipamento de iluminação que obstrui o passeio em Porto Alegre?",["POA-obstruidos-prazo"],[H6]),
 A("q12","teste","Como é prestado o serviço de iluminação pública em Porto Alegre?",POA_CANAIS,[r"PPP|Parceria P[úu]blico-Privada"]),
 A("q13","dev","Em São Paulo, qual o prazo normal para concluir a manutenção da iluminação pública?",["SP-prazo"],[r"24"]),
 A("q14","teste","Quem faz a manutenção da iluminação pública na capital paulista?",["SP-responsavel"],[r"SP Regula"]),
 A("q15","teste","Qual telefone usar para pedir serviço de iluminação pública em São Paulo?",["SP-canais"],[r"156|0800 779 0156"]),
 A("q16","dev","O que pode atrasar o reparo da iluminação pública em São Paulo?",["SP-causas","SP-prazo"],[r"furto|[áa]rvores|fen[ôo]menos"]),
 A("q17","teste","Que número ligar de outra cidade para falar sobre iluminação de Porto Alegre?",["POA-contato-smsurb"],[r"3289 0156"]),
 A("q18","teste","Qual o prazo para consertar luminária faiscando em Porto Alegre?",["POA-faiscando-prazo"],[H6]),
 A("q19","teste","Quando foram atualizadas as páginas de iluminação pública da Carta de Serviços de Porto Alegre?",["POA-atualizacao"],[r"10/08/2021"]),
 A("q20","dev","Quais canais posso usar para comunicar um poste caído em Porto Alegre?",["POA-poste-caido-canais"],[r"156WEB|IPSul"]),
 A("q21","teste","O que é o serviço de luminária ausente em Porto Alegre?",["POA-ausente-descricao"],[r"reposi[çc][ãa]o"]),
 A("q22","teste","O que significa luminária oscilante em Porto Alegre?",["POA-oscilante-descricao"],[r"intermitente|piscando"]),
 A("q23","dev","Que tipo de poste é atendido pelo serviço de poste caído, torto ou danificado em Porto Alegre?",["POA-poste-caido-descricao"],[r"risco de queda|ca[ií]do|avaria"]),
 A("q24","teste","A ligação para tirar dúvidas de iluminação em Porto Alegre é gratuita?",["POA-contato-smsurb"],[r"0800 000 1740|gratuita"]),
 A("q25","teste","Em quais locais o serviço de lâmpada apagada à noite atende em Porto Alegre?",["POA-apagada-descricao"],[r"pra[çc]as|ciclovias|parques"]),
 A("q26","teste","O que a SP Regula faz na iluminação pública de São Paulo?",["SP-responsavel"],[r"l[âa]mpadas|rondas|fia[çc][ãa]o"]),
 N("n01","dev","Qual a lei municipal que regula a iluminação pública em Porto Alegre?"),
 N("n02","teste","Qual o prazo para consertar um poste caído em São Paulo?"),
 N("n03","teste","Qual o prazo para consertar poste apagado em Fortaleza?"),
 N("n04","dev","Quanto custa a contribuição de iluminação pública (COSIP) em Porto Alegre?"),
 N("n05","teste","Quem é responsável pela iluminação pública em Curitiba?"),
 N("n06","teste","Qual aplicativo posso usar para reclamar de poste apagado em Fortaleza?"),
 N("n07","teste","Quantos postes de iluminação existem em Porto Alegre?"),
 N("n08","dev","Qual a multa para quem danifica um poste de iluminação pública?"),
 N("n09","teste","A que horas os postes acendem em Porto Alegre?"),
 N("n10","teste","Qual o telefone da iluminação pública do Rio de Janeiro?"),
 N("n11","teste","Como peço a instalação de um poste novo em uma rua sem iluminação em Porto Alegre?"),
 N("n12","teste","Quanto custa o contrato de PPP da iluminação de Porto Alegre?"),
 N("n13","teste","Qual o prazo de atendimento da iluminação pública em Belo Horizonte?"),
 N("n14","teste","Posso solicitar conserto de iluminação em Porto Alegre pelo WhatsApp?"),
]
with open(R/"avaliacao"/"conjunto_teste.jsonl","w",encoding="utf-8") as f:
    for t in T: f.write(json.dumps(t,ensure_ascii=False)+"\n")
print(len(T), sum(t["split"]=="dev" for t in T), "dev")

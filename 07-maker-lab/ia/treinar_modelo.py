"""Treina uma pequena rede neural MLP com CSVs de treino e teste.

Uso: python treinar_modelo.py
Arquivos: dados/treino/*.csv e dados/teste/*.csv (nao misturar sessoes).
Exporta ../firmware/MakerLab_Controle_Independente_TinyML/ModeloTreinado.h.
Ativa USAR_TINYML=1 no Config.h; nao altera HABILITAR_MOTORES.
"""
import csv
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import numpy as np
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
except ImportError:
    sys.exit('Faltam bibliotecas. Instale com: py -m pip install -r requirements.txt')

RAIZ = Path(__file__).resolve().parent
FIRMWARE = RAIZ.parent / 'firmware' / 'MakerLab_Controle_Independente_TinyML'
DADOS = RAIZ / 'dados'
CLASSES = ('claro_livre', 'claro_obstaculo', 'escuro_livre', 'escuro_obstaculo')
COLUNAS = ('timestamp_ms', 'distancia_cm', 'escuro', 'ldr_do')
JANELA = 10


def ler_arquivo(caminho, grupo):
    nome = caminho.name
    m = re.match(r'^([a-z_]+)\.(treino|teste)_[A-Za-z0-9_-]+\.csv$', nome)
    if not m or m.group(1) not in CLASSES:
        raise ValueError(f'Nome invalido: {nome}. Exemplo: claro_livre.treino_A_1.csv')
    classe, tipo = m.groups()
    if tipo != grupo:
        raise ValueError(f'{nome} esta em dados/{grupo}, mas o nome indica {tipo}.')
    with caminho.open('r', encoding='utf-8-sig', newline='') as arq:
        leitor = csv.DictReader(arq)
        if leitor.fieldnames != list(COLUNAS):
            raise ValueError(f'{nome}: colunas esperadas: {", ".join(COLUNAS)}')
        linhas = list(leitor)
    if len(linhas) != 50:
        raise ValueError(f'{nome}: CSV incompleto (esperadas 50 amostras, achei {len(linhas)}).')
    valores = []
    for idx, linha in enumerate(linhas):
        try:
            tempo = int(linha['timestamp_ms'])
            distancia = float(linha['distancia_cm'])
            escuro = int(linha['escuro'])
            raw = int(linha['ldr_do'])
        except (ValueError, TypeError) as e:
            raise ValueError(f'{nome}: dados invalidos na linha {idx+2}') from e
        if tempo != idx*100 or not math.isfinite(distancia) or not (2<=distancia<=300):
            raise ValueError(f'{nome}: timestamp/distancia invalidos na linha {idx+2}')
        if escuro not in (0,1) or raw not in (0,1):
            raise ValueError(f'{nome}: coluna escuro/ldr_do deve conter 0 ou 1')
        valores.append((distancia,escuro))
    # Toda a gravacao deve representar a classe declarada, sem trocar condicao.
    fracao_escuro = sum(x[1] for x in valores)/len(valores)
    esperado = 1 if classe.startswith('escuro_') else 0
    if abs(fracao_escuro-esperado)>0.10:
        raise ValueError(f'{nome}: classe informada contradiz LDR em {fracao_escuro:.0%} das leituras. Ajuste limiar ou rotulo.')
    windows=[]
    for inicio in range(0,len(valores),JANELA):
        trecho=valores[inicio:inicio+JANELA]
        ds=np.array([v[0] for v in trecho],dtype=np.float64)
        windows.append([float(ds.mean()),float(ds.min()),float(ds.std()),
                        float(sum(v[1] for v in trecho)/JANELA)])
    return classe,windows


def construir_dataset(grupo):
    arquivos=sorted((DADOS/grupo).glob('*.csv'))
    if not arquivos:
        raise ValueError(f'Pasta dados/{grupo}/ sem CSVs. Transfira os arquivos do celular para o PC.')
    X,y=[],[];contagem=Counter()
    for f in arquivos:
        classe,linhas=ler_arquivo(f,grupo)
        X.extend(linhas);y.extend([CLASSES.index(classe)]*len(linhas))
        contagem[classe]+=1
    for classe in CLASSES:
        if contagem[classe]<(2 if grupo=='treino' else 1):
            raise ValueError(f'Insuficiente em {grupo}/{classe}: {contagem[classe]} CSVs. '
                             f'Minimo {2 if grupo=="treino" else 1} arquivos por classe.')
    return np.asarray(X,dtype=np.float64),np.asarray(y),contagem


def fmt(n):
    if not math.isfinite(float(n)):
        raise ValueError('Modelo treinado contem coeficientes invalidos.')
    numero = f'{float(n):.9g}'
    if '.' not in numero and 'e' not in numero and 'E' not in numero:
        numero += '.0'
    return numero+'f'


def vetor(a):
    return '{'+', '.join(fmt(v) for v in a)+'}'


def matriz(a):
    return '{\n'+',\n'.join('  '+vetor(row) for row in a)+'\n}'


def prever_em_c(x,scaler,mlp):
    """Mesmo calculo do ESP32, validado contra predict_proba do sklearn."""
    a=np.maximum(0.0,((x-scaler.mean_)/scaler.scale_)@mlp.coefs_[0]+mlp.intercepts_[0])
    l=a@mlp.coefs_[1]+mlp.intercepts_[1]
    ex=np.exp(l-l.max(axis=1,keepdims=True))
    return ex/ex.sum(axis=1,keepdims=True)


def main():
    xtr,ytr,ntr=construir_dataset('treino')
    xte,yte,nte=construir_dataset('teste')
    print('CSV por classe:')
    for c in CLASSES:
        print(f'  {c:18s} | treino={ntr[c]:2d} | teste={nte[c]:2d}')
    print(f'Janelas independentes? Nao: 5 janelas por arquivo. Treino={len(xtr)}, teste={len(xte)}')
    scaler=StandardScaler().fit(xtr)
    # Nao selecionar parametros usando o conjunto final de teste.
    mlp=MLPClassifier(hidden_layer_sizes=(12,),activation='relu',solver='lbfgs',
                      alpha=0.05,random_state=42,max_iter=2500)
    mlp.fit(scaler.transform(xtr),ytr)
    if list(mlp.classes_)!=list(range(4)):
        raise ValueError('Treinamento nao contemplou as 4 classes. Verifique CSVs.')
    prob=mlp.predict_proba(scaler.transform(xte))
    p=prever_em_c(xte,scaler,mlp)
    erro=float(np.max(np.abs(prob-p)))
    if erro>1e-6:
        raise ValueError(f'Saida exportada nao confere com sklearn: erro {erro}')
    pred=np.argmax(p,axis=1)
    acuracia=float(accuracy_score(yte,pred))
    matriz_confusao=confusion_matrix(yte,pred,labels=list(range(4)))
    print('\n=== RESULTADO EM TESTE SEPARADO ===')
    print(f'Acuracia das janelas: {acuracia:.1%}')
    print(classification_report(yte,pred,target_names=CLASSES,labels=range(4),zero_division=0))
    print('Matriz de confusao (linhas=real, colunas=previsto):')
    print(matriz_confusao)
    print('Diferenca implementacao C vs sklearn:',erro)
    # Aviso importante: nao inventar modelo bom com dados insuficientes.
    if acuracia<0.75:
        sys.exit('\nAcuracia <75%. Modelo NAO exportado. Recolha dados variados e teste novamente.')
    cabecalho='''#pragma once
// GERADO por treinar_modelo.py a partir dos CSVs reais. NAO EDITE MANUALMENTE.
// Features: media_distancia, min_distancia, desvio_distancia, fracao_escuro
// Classes: claro_livre, claro_obstaculo, escuro_livre, escuro_obstaculo
// Rede: 4 entradas -> ReLU 12 neuronios -> softmax 4 classes.
namespace modelo {
constexpr bool DISPONIVEL = true;
constexpr int ENTRADAS = 4, OCULTOS = 12, SAIDAS = 4;
static const float media[4] = %s;
static const float escala[4] = %s;
static const float w1[4][12] = %s;
static const float b1[12] = %s;
static const float w2[12][4] = %s;
static const float b2[4] = %s;
}
'''%(vetor(scaler.mean_),vetor(scaler.scale_),matriz(mlp.coefs_[0]),
        vetor(mlp.intercepts_[0]),matriz(mlp.coefs_[1]),vetor(mlp.intercepts_[1]))
    # Validar que o header nao inclui pesos ficticios antes de gravar.
    (FIRMWARE/'ModeloTreinado.h').write_text(cabecalho,encoding='utf-8')
    arq=FIRMWARE/'Config.h'
    conf=arq.read_text(encoding='utf-8')
    conf,numero=re.subn(r'(#define\s+USAR_TINYML\s+)0\b',r'\g<1>1',conf,count=1)
    if numero!=1 and '#define USAR_TINYML 1' not in conf:
        raise ValueError('Nao encontrei a configuracao USAR_TINYML em Config.h')
    arq.write_text(conf,encoding='utf-8')
    resultados={'dataset':'CSVs separados em treino e teste',
        'classes':list(CLASSES),'arquivos_treino':dict(ntr),'arquivos_teste':dict(nte),
        'janelas_treino':len(xtr),'janelas_teste':len(xte),
        'acuracia_teste':acuracia,'matriz_confusao':matriz_confusao.tolist(),
        'erro_exportacao_max':erro,'modelo':'MLP 4-12-4 ReLU/softmax',
        'alerta':'Acuracia em janelas correlacionadas nao equivale a validacao em ruas reais.'}
    (RAIZ/'resultado_treinamento.json').write_text(json.dumps(resultados,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n[OK] ModeloTreinado.h gerado a partir dos CSVs fornecidos.')
    print('[OK] Config.h -> USAR_TINYML=1; HABILITAR_MOTORES nao foi alterado.')
    print('Agora recarregue MakerLab_Controle_Independente_TinyML.ino no ESP32.')

if __name__=='__main__':
    try:main()
    except ValueError as e:sys.exit('ERRO: '+str(e))

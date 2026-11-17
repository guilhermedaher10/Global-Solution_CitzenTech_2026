#pragma once
#include <Arduino.h>

const char PAGINA[] PROGMEM = R"HTML(
<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CitizenTech | Carrinho ESP32</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{font:15px/1.45 system-ui,Arial;background:#0c1524;color:#e9effa;max-width:780px;margin:0 auto;padding:18px 12px}
h1{font-size:23px;margin:6px 0}h2{font-size:17px;margin:0 0 10px}.box{background:#19263a;border:1px solid #32445a;border-radius:14px;padding:15px;margin:13px 0}
.muted{color:#bac7dc;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:9px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,Menlo,monospace;margin:0}
button,select,input,a.download{font:inherit;padding:10px;background:#30445e;color:#fff;border:0;border-radius:9px;margin:3px}button{cursor:pointer}button:disabled{opacity:.4}a{color:#a9d4ff}.download{display:inline-block;background:#176c58;text-decoration:none}
#alerta[data-nivel="alto"]{border-color:#e26666;background:#54272d}#alerta[data-nivel="medio"]{border-color:#eeb463}#alerta[data-nivel="normal"]{border-color:#4aaa83}
.pad{text-align:center}.drive{width:66px;height:56px;font-size:23px;touch-action:none;user-select:none}.stop{background:#98252d}
input{max-width:135px}label{display:inline-block;margin:5px 2px}#gpsCoords{width:100%;max-width:none}.status{font-weight:700}
</style></head><body>
<h1>Carrinho CitizenTech</h1><div class="muted">GPS + ultrassom + sensor digital de luminosidade + TinyML</div>
<div class="box"><div class="status" id="mode">Conectando...</div><div id="wifiStatus" class="muted"></div></div>
<div class="box" id="alerta" data-nivel="normal"><h2>Diagnostico automatico</h2><pre id="alertaTexto">Aguardando dados...</pre></div>
<div class="grid">
<div class="box"><h2>Sensores</h2><pre id="sensores">...</pre></div>
<div class="box"><h2>Modelo</h2><pre id="modelo">...</pre></div>
</div>
<div class="box"><h2>GPS NEO-6M</h2><pre id="gpsStatus">...</pre>
<p class="muted">O GPS obtém coordenadas por satélite, sem internet. Google Maps precisa de internet para carregar o mapa. Sem FIX, o GPS ainda nao sabe a localizacao.</p>
<input id="gpsCoords" readonly placeholder="Latitude e longitude aparecerao aqui quando houver FIX">
<button id="copiarGps" onclick="copiarGps()" disabled>Copiar coordenadas</button>
<a id="gpsMap" target="_blank" rel="noopener noreferrer" hidden>Abrir Google Maps (usa internet)</a>
</div>
<div class="box" id="collection"><h2>Coleta para treinar IA</h2>
<p class="muted">Selecione a situacao REAL observada. Grave 5 segundos SEM trocar de condicao. Baixe o CSV a cada gravacao; separe treino e teste.</p>
<label>Classe<select id="label"><option value="claro_livre">Claro + livre</option><option value="claro_obstaculo">Claro + obstaculo</option><option value="escuro_livre">Escuro + livre</option><option value="escuro_obstaculo">Escuro + obstaculo</option></select></label>
<label>Conjunto<select id="subset"><option value="treino">Treino</option><option value="teste">Teste</option></select></label>
<label>Sessao<input id="session" value="A" maxlength="20" pattern="[A-Za-z0-9_-]+"></label>
<div><button id="start" onclick="startCapture()">Gravar 5 segundos</button>
<a class="download" id="download" href="/coleta.csv" hidden>Baixar CSV</a></div><p class="muted" id="captureMessage"></p></div>
<div class="box" id="vesperBox"><h2>Central Vesper (nuvem)</h2><pre id="vesper">...</pre>
<p class="muted">Quando a IA confirma escuro_livre ou escuro_obstaculo, o carrinho envia o alerta para a API do Vesper (POST /v1/alerta-robo) e ele vira suspeita na central de chamados do site. Requer Wi-Fi de casa ou hotspot no Config.h.</p></div>
<div class="box"><h2>Registro de eventos</h2><pre id="eventos">...</pre><a class="download" href="/eventos.csv">Baixar eventos CSV</a>
<p class="muted">Eventos guardados temporariamente na memoria RAM; reiniciar o ESP32 apaga o historico. GPS e anexado apenas quando ha FIX valido.</p></div>
<div class="box" id="control" hidden><h2>Movimento manual</h2><div id="controlMode" class="status"></div>
<p class="muted">Modo diagnostico: setas movimentam sem bloqueio dos sensores ou da IA. IA continua classificando separadamente. Segure para mover; solte para parar. Teste somente com rodas suspensas.</p>
<div class="pad"><button class="drive" data-cmd="frente">▲</button><br><button class="drive" data-cmd="esquerda">◀</button><button class="drive stop" onclick="release()">■</button><button class="drive" data-cmd="direita">▶</button><br><button class="drive" data-cmd="tras">▼</button></div></div>
<script>
let held='',inflight=false,sequence=0;
const el=id=>document.getElementById(id);const n=v=>v===null?'--':v;
async function sendHeld(){if(!held||inflight)return;const cmd=held;inflight=true;try{const r=await fetch('/'+cmd,{cache:'no-store'});if(!r.ok)throw Error(await r.text());}catch(e){console.warn('Erro no comando:',e);}finally{inflight=false;}}
function release(){if(!held)return;held='';sequence++;fetch('/parar',{cache:'no-store',keepalive:true}).catch(()=>{});}
document.querySelectorAll('[data-cmd]').forEach(b=>{b.addEventListener('pointerdown',e=>{e.preventDefault();sequence++;held=b.dataset.cmd;b.setPointerCapture(e.pointerId);sendHeld();});b.addEventListener('pointerup',release);b.addEventListener('pointercancel',release);b.addEventListener('lostpointercapture',release);});
window.addEventListener('blur',release);document.addEventListener('visibilitychange',()=>{if(document.hidden)release();});setInterval(sendHeld,180);
async function startCapture(){const p=new URLSearchParams({classe:el('label').value,conjunto:el('subset').value,sessao:el('session').value});el('start').disabled=true;try{const r=await fetch('/coleta/iniciar?'+p,{cache:'no-store'});const t=await r.text();if(!r.ok)throw Error(t);el('captureMessage').textContent=t;}catch(e){el('captureMessage').textContent=e.message;el('start').disabled=false;}}
function copiarGps(){const x=el('gpsCoords');x.focus();x.select();try{document.execCommand('copy');}catch(e){} }
async function poll(){try{const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const s=await r.json();
el('mode').textContent=s.tinyml?'IA TREINADA / INFERENCIA ATIVA':'MODO COLETA - IA NAO TREINADA';
el('wifiStatus').textContent='Acesso direto: '+s.wifi.ap_ip+' | Wi-Fi casa: '+(s.wifi.casa?s.wifi.casa_ip:'desconectado / nao configurado');
el('control').hidden=!s.motores_habilitados;el('collection').hidden=s.tinyml;
el('controlMode').textContent=s.controle_independente?'CONTROLE MANUAL INDEPENDENTE (SENSORES NAO BLOQUEIAM)':'CONTROLE ASSISTIDO (IA + SENSORES)';
el('sensores').textContent='Distancia: '+(s.distancia_cm===null?'INVALIDA':s.distancia_cm.toFixed(1)+' cm')+'\nLDR D34: '+s.luz.estado+' (sinal '+s.luz.raw+')';
el('modelo').textContent='Modelo: '+(s.tinyml?'treinado':'indisponivel')+'\nClasse: '+s.ml.classe+'\nConfianca: '+(s.ml.confianca*100).toFixed(1)+'%\nInferencias: '+s.ml.inferencias+'\nUltima: '+s.ml.duracao_ms+' ms\nMotor: '+s.acao;
const risco=s.alerta.nivel;el('alerta').dataset.nivel=risco;
el('alertaTexto').textContent=s.alerta.mensagem+'\nNivel: '+risco.toUpperCase()+'\nOrigem: '+s.alerta.origem;
const g=s.gps, fix=g.fix&&g.latitude!==null&&g.longitude!==null;
el('gpsStatus').textContent='Serial GPS: '+(g.recebendo?'OK':'sem dados')+' | Satelites: '+n(g.satelites)+'\nFIX: '+(fix?'SIM':'NAO')+'\nLatitude: '+n(g.latitude)+' | Longitude: '+n(g.longitude);
el('gpsMap').hidden=!fix;el('copiarGps').disabled=!fix;el('gpsCoords').value=fix?g.latitude.toFixed(6)+','+g.longitude.toFixed(6):'';
if(fix)el('gpsMap').href='https://www.google.com/maps?q='+g.latitude+','+g.longitude;
const v=s.vesper;if(v)el('vesper').textContent='Envio: '+v.estado.toUpperCase()+' | enviados: '+v.enviados+' | falhas: '+v.falhas+'\nProtocolo: '+(v.protocolo||'--')+' | LED: '+v.acao_robo+'\n'+v.mensagem;
el('eventos').textContent=s.ultimo_evento||'Nenhum evento registrado ainda.';
el('start').disabled=s.coletando;el('download').hidden=!s.csv_pronto;el('captureMessage').textContent=s.coletando?'Gravando '+s.coleta_leituras+'/50':s.coleta_mensagem;
}catch(e){el('mode').textContent='ESP32 sem comunicacao: '+e.message;}finally{setTimeout(poll,650);}}
poll();
</script></body></html>
)HTML";

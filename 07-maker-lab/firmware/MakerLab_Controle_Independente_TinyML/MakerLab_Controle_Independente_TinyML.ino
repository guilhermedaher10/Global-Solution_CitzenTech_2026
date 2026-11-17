/* CitizenTech - Maker Lab FIAP - 2026.2
 * ESP32 + HC-SR04 + GPS NEO-6M + LDR DO(GPIO34)
 * Modelo TinyML MLP: rede neural exportada do treino em Python com DADOS REAIS.
 * Modos seguros: USAR_TINYML=0 e HABILITAR_MOTORES=0 por padrao.
 * Leia README.md e TODO_DO_ALUNO.md antes de ativar os motores.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <HardwareSerial.h>
#include <TinyGPSPlus.h>
#include <math.h>
#include <ctype.h>
#include <esp_system.h>
#include "Config.h"
#include "Controle.h"
#include "Pagina.h"
#include "Vesper.h"   // integracao com a central do Vesper (POST /v1/alerta-robo)
#if USAR_TINYML
#include "ModeloTreinado.h"
static_assert(modelo::ENTRADAS == 4 && modelo::OCULTOS == 12 && modelo::SAIDAS == 4,
              "Modelo deve ser MLP (4 entradas, 12 ocultos, 4 saidas)");
#endif

WebServer server(80);
HardwareSerial portaGps(2);
TinyGPSPlus gps;
uint32_t ultimoByteGPS=0, totalBytesGPS=0, ultimoLog=0, ultimaLeitura=0, proximaLeitura=0;
uint32_t ultimoStatusWifi=0;
int luzDO=-1;
float distanciaCm=-1;
Pedido pedido=Pedido::PARAR;
uint32_t ultimoComando=0;
Acao acaoAtual={0,0,"INICIANDO"};
int pwmA=0,pwmB=0;

struct Leitura {float distancia;uint8_t escuro;uint8_t raw;};
Leitura janela[cfg::LEITURAS_JANELA]={};
int janelaIndice=0,janelaTotal=0,novasLeituras=0;
Leitura coleta[cfg::LEITURAS_COLETA]={};
int coletaTotal=0;
bool coletando=false,csvPronto=false;
String coletaNome,coletaMensagem="Selecione classe, treino/teste, sessao e grave 5 segundos.";
uint32_t sequenciaCSV=0, bootId=0;

bool modeloAtivo=false, mlValido=false;
Classe mlClasse=Classe::INDEFINIDA;
float mlConfianca=0;
uint32_t mlUltimaEntrada=0,mlInferencias=0,mlDuracaoMs=0;
int estadoPendente=-1,repeticoesPendente=0,estadoConfirmado=-1;

struct Evento {
  uint32_t uptimeS;
  Classe classe;
  float confianca, distancia;
  bool escuro,temGps;
  double lat,lon;
};
constexpr int MAX_EVENTOS=20;
Evento eventos[MAX_EVENTOS]={};
int eventosCount=0,eventosProximo=0;
String ultimoEvento="";

bool gpsRecebendo(){return totalBytesGPS>0 && millis()-ultimoByteGPS<=cfg::GPS_MAX_IDADE_MS;}
bool gpsFix(){return gpsRecebendo() && gps.location.isValid() && gps.location.age()<=cfg::GPS_MAX_IDADE_MS;}
void lerGps(){
  for(int n=0;n<256 && portaGps.available()>0;n++){
    char c=(char)portaGps.read();gps.encode(c);ultimoByteGPS=millis();totalBytesGPS++;
  }
}

float lerUltrassom(){
  digitalWrite(cfg::TRIG,LOW);delayMicroseconds(2);
  digitalWrite(cfg::TRIG,HIGH);delayMicroseconds(10);digitalWrite(cfg::TRIG,LOW);
  unsigned long micros=pulseIn(cfg::ECHO,HIGH,25000);
  if(micros==0)return -1;
  float cm=micros*0.0343f/2.0f;
  return (isfinite(cm)&&cm>=cfg::DIST_MIN_CM&&cm<=cfg::DIST_MAX_CM)?cm:-1;
}

bool luzEscura(){return luzDO==cfg::LUZ_NIVEL_ESCURO;}
void limparJanela(){
  janelaIndice=0;janelaTotal=0;novasLeituras=0;
  mlValido=false;mlClasse=Classe::INDEFINIDA;mlConfianca=0;
  estadoPendente=-1;repeticoesPendente=0;
}
void abortarColeta(const char* msg){
  if(!coletando)return;
  coletando=false;csvPronto=false;coletaTotal=0;
  coletaMensagem=msg;
  Serial.printf("[COLETA] ABORTADA: %s\n",msg);
}

// Durante o treino, o usuario precisa manter a classe fisica indicada no painel.
void amostrar(){
  const uint32_t agora=millis();
  int32_t atraso=(int32_t)(agora-proximaLeitura);
  if(atraso<0)return;
  if((uint32_t)atraso>cfg::TOLERANCIA_MS){
    limparJanela();abortarColeta("Amostragem atrasada. Repita a gravacao.");
    proximaLeitura=agora+cfg::PERIODO_MS;
  } else proximaLeitura+=cfg::PERIODO_MS;

  distanciaCm=lerUltrassom();
  luzDO=digitalRead(cfg::LUZ_DO);
  ultimaLeitura=millis();
  if(distanciaCm<0){
    limparJanela();abortarColeta("Ultrassom sem leitura valida: confira alvo e fios.");
    return;
  }
  Leitura l={distanciaCm,(uint8_t)(luzEscura()?1:0),(uint8_t)luzDO};
  if(coletando){
    coleta[coletaTotal++]=l;
    if(coletaTotal==cfg::LEITURAS_COLETA){
      coletando=false;csvPronto=true;
      coletaMensagem="CSV pronto: baixe antes de iniciar outra coleta.";
      Serial.printf("[COLETA] PRONTA: %s (%d leituras)\n",coletaNome.c_str(),coletaTotal);
    }
  }
  janela[janelaIndice]=l;
  janelaIndice=(janelaIndice+1)%cfg::LEITURAS_JANELA;
  if(janelaTotal<cfg::LEITURAS_JANELA)janelaTotal++;
  novasLeituras++;
}

// 4 atributos: distancia media, menor distancia, desvio-padrao, fracao de leituras escuras.
void extrairAtributos(float x[4]){
  float soma=0,minimo=100000,somaQ=0,escuro=0;
  for(int i=0;i<cfg::LEITURAS_JANELA;i++){
    float d=janela[i].distancia;
    soma+=d;somaQ+=d*d;if(d<minimo)minimo=d;
    escuro+=janela[i].escuro;
  }
  float media=soma/cfg::LEITURAS_JANELA;
  float variancia=somaQ/cfg::LEITURAS_JANELA-media*media;
  x[0]=media;x[1]=minimo;x[2]=sqrtf(fmaxf(0.0f,variancia));
  x[3]=escuro/cfg::LEITURAS_JANELA;
}

#if USAR_TINYML
// Inferencia local: normalizacao + ReLU + softmax (sem internet nem servidor).
// Pesos de ModeloTreinado.h gerados a partir dos CSVs reais.
bool preverRede(const float x[4], float probabilidades[4]){
  float h[12];
  for(int j=0;j<12;j++){
    float v=modelo::b1[j];
    for(int i=0;i<4;i++){
      if(!isfinite(x[i]) || !isfinite(modelo::escala[i]) || modelo::escala[i]<=0)return false;
      v+=((x[i]-modelo::media[i])/modelo::escala[i])*modelo::w1[i][j];
    }
    h[j]=fmaxf(0,v);
  }
  float logits[4],maximo=-INFINITY;
  for(int k=0;k<4;k++){
    float v=modelo::b2[k];
    for(int j=0;j<12;j++)v+=h[j]*modelo::w2[j][k];
    logits[k]=v;if(v>maximo)maximo=v;
  }
  float total=0;
  for(int k=0;k<4;k++){probabilidades[k]=expf(logits[k]-maximo);total+=probabilidades[k];}
  if(!isfinite(total)||total<=0)return false;
  for(int k=0;k<4;k++)probabilidades[k]/=total;
  return true;
}
#endif

const char* nivelAlerta(Classe c){
  if(c==Classe::ESCURO_OBSTACULO)return "alto";
  if(c==Classe::ESCURO_LIVRE||c==Classe::CLARO_OBSTACULO)return "medio";
  return "normal";
}
const char* descricaoAlerta(Classe c){
  switch(c){
    case Classe::CLARO_LIVRE: return "Iluminado e sem obstaculo frontal relevante";
    case Classe::CLARO_OBSTACULO: return "Obstaculo detectado em local iluminado";
    case Classe::ESCURO_LIVRE: return "Iluminacao abaixo do limiar configurado";
    case Classe::ESCURO_OBSTACULO: return "Escuro com obstaculo: verificar trecho";
    default:return "Sem classificacao valida";
  }
}

void registrarEvento(Classe c,float confianca){
  Evento e={};e.uptimeS=millis()/1000;e.classe=c;e.confianca=confianca;
  e.distancia=distanciaCm;e.escuro=luzEscura();e.temGps=gpsFix();
  if(e.temGps){e.lat=gps.location.lat();e.lon=gps.location.lng();}
  eventos[eventosProximo]=e;eventosProximo=(eventosProximo+1)%MAX_EVENTOS;
  if(eventosCount<MAX_EVENTOS)eventosCount++;
  ultimoEvento=String("t=")+String(e.uptimeS)+"s | "+nomeClasse(c)+" | "+String(confianca,3);
  if(e.temGps)ultimoEvento+=" | GPS: "+String(e.lat,6)+","+String(e.lon,6);
  else ultimoEvento+=" | sem FIX GPS";
  Serial.printf("[EVENTO] %s | %s\n",ultimoEvento.c_str(),descricaoAlerta(c));
  vesper::avisar(nomeClasse(c),confianca,e.temGps,e.lat,e.lon);   // escuro_* vira suspeita na central
}

void inferir(){
#if USAR_TINYML
  if(!modeloAtivo||janelaTotal<cfg::LEITURAS_JANELA||novasLeituras<cfg::PASSO_INFERENCIA)return;
  novasLeituras=0;
  float x[4],probs[4];extrairAtributos(x);
  const uint32_t t0=millis();
  bool ok=preverRede(x,probs);
  mlDuracaoMs=millis()-t0;
  if(!ok){mlValido=false;return;}
  int melhor=0;
  for(int i=1;i<4;i++)if(probs[i]>probs[melhor])melhor=i;
  mlClasse=(Classe)melhor;mlConfianca=probs[melhor];
  mlValido=mlConfianca>=cfg::ESCORE_MIN;
  mlUltimaEntrada=ultimaLeitura;mlInferencias++;
  if(!mlValido){estadoPendente=-1;repeticoesPendente=0;return;}
  if(estadoPendente==melhor)repeticoesPendente++;
  else {estadoPendente=melhor;repeticoesPendente=1;}
  // Registrar somente quando a classe se mantiver por 3 inferencias (~600ms).
  if(repeticoesPendente>=3&&estadoConfirmado!=melhor){
    estadoConfirmado=melhor;registrarEvento(mlClasse,mlConfianca);
  }
#endif
}

void escreverMotor(int inPos,int inNeg,int pwm){
  if(pwm>=0){analogWrite(inNeg,0);analogWrite(inPos,pwm);}
  else {analogWrite(inPos,0);analogWrite(inNeg,-pwm);}
}
void aplicarAcao(const Acao& a){
  bool mudou=a.motorA!=pwmA||a.motorB!=pwmB||strcmp(a.motivo,acaoAtual.motivo)!=0;
  if(a.motorA!=pwmA||a.motorB!=pwmB){
    escreverMotor(cfg::IN1,cfg::IN2,a.motorA);
    escreverMotor(cfg::IN3,cfg::IN4,a.motorB);
  }
  pwmA=a.motorA;pwmB=a.motorB;acaoAtual=a;
  if(mudou)Serial.printf("[MOTORES] %s | A=%d B=%d\n",a.motivo,pwmA,pwmB);
}
void atualizarAcao(){
  uint32_t agora=millis();
  const bool comandoVigente=(agora-ultimoComando<=cfg::COMANDO_MAX_IDADE_MS);
#if CONTROLE_MANUAL_INDEPENDENTE
  Acao nova=decidirManualIndependente(pedido,HABILITAR_MOTORES,comandoVigente);
#else
  const bool podeMover=(USAR_TINYML && HABILITAR_MOTORES && modeloAtivo);
  Acao nova=decidir(pedido,podeMover,comandoVigente,
                   distanciaCm,agora-ultimaLeitura<=cfg::SENSOR_MAX_IDADE_MS,
                   mlValido && agora-mlUltimaEntrada<=cfg::MODELO_MAX_IDADE_MS,
                   mlClasse,mlConfianca);
#endif
  aplicarAcao(nova);
}

bool sessaoValida(const String& s){
  if(s.isEmpty()||s.length()>20)return false;
  for(unsigned i=0;i<s.length();i++){
    char c=s[i];if(!isalnum((unsigned char)c)&&c!='_'&&c!='-')return false;
  }
  return true;
}
void iniciarColeta(){
  if(USAR_TINYML){server.send(409,"text/plain","Para gravar CSV, use USAR_TINYML=0.");return;}
  if(coletando){server.send(409,"text/plain","Ja existe uma coleta.");return;}
  String c=server.arg("classe"),subset=server.arg("conjunto"),sessao=server.arg("sessao");
  if(classePorNome(c)==Classe::INDEFINIDA||(subset!="treino"&&subset!="teste")||!sessaoValida(sessao)){
    server.send(400,"text/plain","Classe/conjunto/sessao invalidos.");return;
  }
  if(distanciaCm<0){server.send(409,"text/plain","Ultrassom sem leitura valida.");return;}
  coletaTotal=0;csvPronto=false;coletando=true;
  pedido=Pedido::PARAR;atualizarAcao();
  coletaNome=c+"."+subset+"_"+sessao+"_"+String(bootId)+"_"+String(++sequenciaCSV)+".csv";
  coletaMensagem="Gravando. Mantenha luz e obstaculo estaveis.";
  Serial.printf("[COLETA] %s\n",coletaNome.c_str());
  server.send(202,"text/plain; charset=utf-8",coletaMensagem);
}
void baixarCsv(){
  if(!csvPronto||coletando){server.send(409,"text/plain","Nenhum CSV pronto.");return;}
  String csv="timestamp_ms,distancia_cm,escuro,ldr_do\n";
  csv.reserve(1850);
  for(int i=0;i<coletaTotal;i++){
    csv+=String((unsigned long)i*cfg::PERIODO_MS)+","+String(coleta[i].distancia,3)+","+
         String(coleta[i].escuro)+","+String(coleta[i].raw)+"\n";
  }
  server.sendHeader("Content-Disposition","attachment; filename=\""+coletaNome+"\"");
  server.sendHeader("Cache-Control","no-store");
  server.send(200,"text/csv; charset=utf-8",csv);
}
void baixarEventos(){
  String csv="uptime_s,classe,nivel,confianca,distancia_cm,escuro,gps_fix,latitude,longitude\n";
  csv.reserve(2400);
  for(int k=0;k<eventosCount;k++){
    int idx=(eventosProximo-eventosCount+k+MAX_EVENTOS)%MAX_EVENTOS;
    const Evento& e=eventos[idx];
    csv+=String(e.uptimeS)+","+nomeClasse(e.classe)+","+nivelAlerta(e.classe)+","+
         String(e.confianca,4)+","+String(e.distancia,2)+","+String(e.escuro?1:0)+","+
         String(e.temGps?1:0)+",";
    if(e.temGps)csv+=String(e.lat,6)+","+String(e.lon,6);
    else csv+=",";
    csv+="\n";
  }
  server.sendHeader("Content-Disposition","attachment; filename=\"eventos_citizentech.csv\"");
  server.sendHeader("Cache-Control","no-store");
  server.send(200,"text/csv; charset=utf-8",csv);
}

void enviarStatus(){
  const bool fix=gpsFix();
  const bool inferenciaRecente=mlValido && (millis()-mlUltimaEntrada<=cfg::MODELO_MAX_IDADE_MS);
  Classe c=inferenciaRecente?mlClasse:Classe::INDEFINIDA;
  String s;s.reserve(1750);
  s="{\"tinyml\":"+String(modeloAtivo?"true":"false");
  s+=",\"motores_habilitados\":"+String((HABILITAR_MOTORES && (CONTROLE_MANUAL_INDEPENDENTE || (USAR_TINYML && modeloAtivo)))?"true":"false");
  s+=",\"controle_independente\":"+String(CONTROLE_MANUAL_INDEPENDENTE?"true":"false");
  s+=",\"distancia_cm\":"+String(distanciaCm>=0?String(distanciaCm,2):String("null"));
  s+=",\"luz\":{\"raw\":"+String(luzDO)+",\"estado\":\""+(luzDO<0?"AGUARDANDO":(luzEscura()?"ESCURO":"CLARO"))+"\"}";
  s+=",\"ml\":{\"classe\":\""+String(nomeClasse(c))+"\",\"confianca\":"+String(inferenciaRecente?mlConfianca:0,4);
  s+=",\"inferencias\":"+String(mlInferencias)+",\"duracao_ms\":"+String(mlDuracaoMs)+"}";
  s+=",\"acao\":\""+String(acaoAtual.motivo)+"\"";
  s+=",\"alerta\":{\"nivel\":\""+String(nivelAlerta(c))+"\",\"mensagem\":\""+
       String(inferenciaRecente?descricaoAlerta(c):"Aguardando IA treinada e inferencia confiavel")+"\",\"origem\":\""+
       String(inferenciaRecente?"modelo MLP executado no ESP32":"sem modelo valido")+"\"}";
  s+=",\"gps\":{\"recebendo\":"+String(gpsRecebendo()?"true":"false");
  s+=",\"fix\":"+String(fix?"true":"false");
  s+=",\"satelites\":"+String(gps.satellites.isValid()&&gps.satellites.age()<=5000?String(gps.satellites.value()):String("null"));
  s+=",\"latitude\":"+String(fix?String(gps.location.lat(),6):String("null"));
  s+=",\"longitude\":"+String(fix?String(gps.location.lng(),6):String("null"))+"}";
  s+=",\"wifi\":{\"ap_ip\":\""+WiFi.softAPIP().toString()+"\",\"casa\":"+
       String(WiFi.status()==WL_CONNECTED?"true":"false")+",\"casa_ip\":\""+
       String(WiFi.status()==WL_CONNECTED?WiFi.localIP().toString():"")+"\"}";
  s+=",\"coletando\":"+String(coletando?"true":"false")+",\"csv_pronto\":"+String(csvPronto?"true":"false");
  s+=",\"coleta_leituras\":"+String(coletaTotal)+",\"coleta_mensagem\":\""+coletaMensagem+"\"";
  s+=",\"ultimo_evento\":\""+ultimoEvento+"\"";
  s+=",\"vesper\":"+vesper::statusJson()+"}";
  server.sendHeader("Cache-Control","no-store");
  server.send(200,"application/json; charset=utf-8",s);
}

void comando(Pedido p){
  if(!(HABILITAR_MOTORES && (CONTROLE_MANUAL_INDEPENDENTE || (USAR_TINYML && modeloAtivo)))&&p!=Pedido::PARAR){
    server.send(409,"text/plain","Motores desabilitados no Config.h.");return;
  }
  pedido=p;ultimoComando=millis();atualizarAcao();
  server.send(200,"text/plain",acaoAtual.motivo);
}
void logSerial(){
  if(coletando||millis()-ultimoLog<cfg::LOG_INTERVALO_MS)return;
  ultimoLog=millis();
  Serial.printf("[SENSORES] distancia=%.1f cm | luz D34=%d (%s)\n",distanciaCm,luzDO,
                luzDO<0?"aguardando":(luzEscura()?"ESCURO":"CLARO"));
  Serial.printf("[GPS] bytes=%lu NMEA_validas=%lu sat=%lu FIX=%s",
                (unsigned long)totalBytesGPS,(unsigned long)gps.passedChecksum(),
                (unsigned long)(gps.satellites.isValid()?gps.satellites.value():0),gpsFix()?"SIM":"NAO");
  if(gpsFix())Serial.printf(" lat=%.6f lon=%.6f",gps.location.lat(),gps.location.lng());
  Serial.println();
  Serial.printf("[IA] ativa=%s | classe=%s | score=%.3f | inferencias=%lu | motores=%s\n",
                modeloAtivo?"SIM":"NAO",nomeClasse(mlClasse),mlConfianca,
                (unsigned long)mlInferencias,acaoAtual.motivo);
  if(WiFi.status()==WL_CONNECTED)Serial.printf("[REDE] casa IP=%s\n",WiFi.localIP().toString().c_str());
}

void setup(){
  Serial.begin(115200);delay(300);
  bootId=esp_random();
  Serial.println("\n=== MAKER LAB CITIZENTECH: GPS + LDR + HC-SR04 + TINYML ===");
  pinMode(cfg::IN1,OUTPUT);pinMode(cfg::IN2,OUTPUT);
  pinMode(cfg::IN3,OUTPUT);pinMode(cfg::IN4,OUTPUT);
  digitalWrite(cfg::IN1,LOW);digitalWrite(cfg::IN2,LOW);
  digitalWrite(cfg::IN3,LOW);digitalWrite(cfg::IN4,LOW);
  analogWrite(cfg::IN1,0);analogWrite(cfg::IN2,0);
  analogWrite(cfg::IN3,0);analogWrite(cfg::IN4,0);
  pinMode(cfg::TRIG,OUTPUT);pinMode(cfg::ECHO,INPUT);
  digitalWrite(cfg::TRIG,LOW);
  pinMode(cfg::LUZ_DO,INPUT); // GPIO34 sem pull-up interno; DO do modulo LM393.
  luzDO=digitalRead(cfg::LUZ_DO);
  portaGps.begin(cfg::GPS_BAUD,SERIAL_8N1,cfg::GPS_RX,cfg::GPS_TX);

#if USAR_TINYML
  modeloAtivo=modelo::DISPONIVEL;
  if(!modeloAtivo)Serial.println("[ERRO] USAR_TINYML=1 mas os pesos ainda nao foram gerados: use treinar_modelo.py.");
#else
  modeloAtivo=false;
#endif
  if(strlen(cfg::WIFI_CASA_SSID)>0){
    WiFi.mode(WIFI_AP_STA);
    WiFi.setAutoReconnect(true);
    WiFi.softAP(cfg::AP_SSID,cfg::AP_SENHA);
    WiFi.begin(cfg::WIFI_CASA_SSID,cfg::WIFI_CASA_SENHA);
    Serial.println("[REDE] Tentando conectar ao Wi-Fi de casa (2.4 GHz), sem bloquear GPS/sensores...");
  } else {
    WiFi.mode(WIFI_AP);
    WiFi.softAP(cfg::AP_SSID,cfg::AP_SENHA);
  }
  server.on("/",[](){server.send_P(200,"text/html; charset=utf-8",PAGINA);});
  server.on("/status",enviarStatus);
  server.on("/coleta/iniciar",iniciarColeta);
  server.on("/coleta.csv",baixarCsv);
  server.on("/eventos.csv",baixarEventos);
  server.on("/frente",[](){comando(Pedido::FRENTE);});
  server.on("/tras",[](){comando(Pedido::TRAS);});
  server.on("/esquerda",[](){comando(Pedido::ESQUERDA);});
  server.on("/direita",[](){comando(Pedido::DIREITA);});
  server.on("/parar",[](){comando(Pedido::PARAR);});
  server.begin();
  vesper::iniciar();
  proximaLeitura=millis()+cfg::PERIODO_MS;
  atualizarAcao();
  Serial.printf("[REDE] Wi-Fi direto: %s | abra http://%s\n",cfg::AP_SSID,WiFi.softAPIP().toString().c_str());
  Serial.printf("[LDR] DO GPIO%d (escuro=%d). [GPS] TX do modulo -> GPIO%d.\n",cfg::LUZ_DO,cfg::LUZ_NIVEL_ESCURO,cfg::GPS_RX);
  Serial.printf("[MODO] IA=%s | Controle=%s | Motores=%s\n",
                modeloAtivo?"ATIVA":"NAO TREINADA",
                CONTROLE_MANUAL_INDEPENDENTE?"MANUAL INDEPENDENTE (SENSORES NAO BLOQUEIAM)":"ASSISTIDO PELA IA",
                HABILITAR_MOTORES?"HABILITADOS":"DESABILITADOS");
}
void loop(){
  lerGps();
  server.handleClient();
  amostrar();
  atualizarAcao();    // Checagens de seguranca antes de inferir
  inferir();
  atualizarAcao();    // Reagir ao resultado do modelo
  lerGps();
  logSerial();
  vesper::atualizarLed();
  delay(1);
}

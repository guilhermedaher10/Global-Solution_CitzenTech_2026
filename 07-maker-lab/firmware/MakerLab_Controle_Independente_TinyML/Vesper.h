#pragma once
/* Integracao com o Vesper (sistema da equipe): o carrinho avisa a central de chamados.
 *
 * Quando o TinyML confirma "escuro_livre" ou "escuro_obstaculo", o ESP32 manda
 *   POST {VESPER_URL}/v1/alerta-robo
 *   {"origem":"robo","latitude":..,"longitude":..,"alerta":["escuro"],
 *    "classe_ia":"escuro_obstaculo","confianca_ia":0.97}
 * A API da Visao Computacional (pasta 04) registra uma SUSPEITA na central (aparece no site,
 * no mapa e no Grafana) e responde "acao_robo": led_vermelho | led_amarelo | nenhuma.
 *
 * - Precisa do Wi-Fi de casa/hotspot configurado em Config.h (WIFI_CASA_SSID). Sem internet,
 *   o carrinho continua funcionando sozinho como antes; o envio so fica "sem rede".
 * - O envio roda numa tarefa separada (FreeRTOS): a leitura dos sensores e o painel nao travam
 *   durante o HTTPS.
 * - Sem FIX de GPS, usa a posicao padrao abaixo e avisa no painel ("posicao padrao").
 * - O LDR e digital: o carrinho nao manda lux, manda o alerta "escuro" decidido pela IA.
 *   O ultrassom e frontal (obstaculo), entao a distancia NAO e enviada como "buraco".
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

#ifndef VESPER_ATIVO
#define VESPER_ATIVO 1
#endif

namespace vesper {
// API publica do Vesper (Azure Container Apps). Sem barra no final.
constexpr const char* URL = "https://ca-ruasescuras-visao.bravehill-24590cb4.eastus.azurecontainerapps.io";
constexpr uint32_t INTERVALO_MIN_MS = 30000;   // no maximo 1 alerta a cada 30 s
constexpr uint32_t TIMEOUT_MS = 8000;
// Posicao usada sem FIX de GPS (FIAP Paulista, so para demonstracao).
constexpr double LAT_PADRAO = -23.5641, LON_PADRAO = -46.6525;
constexpr int LED_PINO = 2;                    // LED azul da placa ESP32 DevKit

enum class Estado : uint8_t { DESLIGADO, SEM_REDE, AGUARDANDO, ENVIANDO, OK, ERRO };

struct Pedido {
  double lat, lon;
  bool temGps;
  char classe[20];
  float confianca;
};

// Compartilhado entre o loop e a tarefa de envio (escrito por um lado de cada vez).
volatile Estado estado = Estado::DESLIGADO;
volatile bool ocupado = false;
uint32_t ultimoEnvio = 0;
uint32_t enviados = 0, falhas = 0;
char protocolo[32] = "";
char acaoRobo[16] = "nenhuma";
char ultimaMsg[96] = "aguardando alerta da IA";
Pedido pedido = {};

inline const char* nomeEstado() {
  switch (estado) {
    case Estado::DESLIGADO: return "desligado";
    case Estado::SEM_REDE: return "sem rede";
    case Estado::AGUARDANDO: return "pronto";
    case Estado::ENVIANDO: return "enviando";
    case Estado::OK: return "enviado";
    default: return "erro";
  }
}

// Le "campo":"valor" de um JSON simples sem biblioteca extra.
inline void campoTexto(const String& json, const char* campo, char* destino, size_t tam) {
  String chave = String("\"") + campo + "\":";
  int i = json.indexOf(chave);
  destino[0] = '\0';
  if (i < 0) return;
  i += chave.length();
  while (i < (int)json.length() && json[i] == ' ') i++;
  if (i >= (int)json.length() || json[i] != '"') return;   // null ou numero
  int fim = json.indexOf('"', i + 1);
  if (fim < 0) return;
  json.substring(i + 1, fim).toCharArray(destino, tam);
}

inline void tarefaEnvio(void*) {
  char corpo[256];
  snprintf(corpo, sizeof(corpo),
           "{\"origem\":\"robo\",\"latitude\":%.6f,\"longitude\":%.6f,\"alerta\":[\"escuro\"],"
           "\"classe_ia\":\"%s\",\"confianca_ia\":%.3f}",
           pedido.lat, pedido.lon, pedido.classe, pedido.confianca);
  WiFiClientSecure cliente;
  // Demonstracao academica: nao valida o certificado. Em producao, use setCACert com a CA da Azure.
  cliente.setInsecure();
  HTTPClient http;
  http.setTimeout(TIMEOUT_MS);
  bool ok = false;
  if (http.begin(cliente, String(URL) + "/v1/alerta-robo")) {
    http.addHeader("Content-Type", "application/json");
    int codigo = http.POST((uint8_t*)corpo, strlen(corpo));
    if (codigo == 200) {
      String resp = http.getString();
      campoTexto(resp, "acao_robo", acaoRobo, sizeof(acaoRobo));
      campoTexto(resp, "protocolo", protocolo, sizeof(protocolo));
      snprintf(ultimaMsg, sizeof(ultimaMsg), "%s %s -> %s%s", pedido.classe,
               protocolo[0] ? protocolo : "(sem protocolo)", acaoRobo,
               pedido.temGps ? "" : " | posicao padrao");
      ok = true;
    } else {
      snprintf(ultimaMsg, sizeof(ultimaMsg), "falha HTTP %d", codigo);
    }
    http.end();
  } else {
    snprintf(ultimaMsg, sizeof(ultimaMsg), "URL invalida");
  }
  if (ok) enviados++; else falhas++;
  estado = ok ? Estado::OK : Estado::ERRO;
  Serial.printf("[VESPER] %s\n", ultimaMsg);
  ocupado = false;
  vTaskDelete(nullptr);
}

inline void iniciar() {
  pinMode(LED_PINO, OUTPUT);
  digitalWrite(LED_PINO, LOW);
  estado = VESPER_ATIVO ? Estado::SEM_REDE : Estado::DESLIGADO;
}

// Chamado quando o TinyML confirma uma classe nova. So envia classes "escuro_*".
inline void avisar(const char* classe, float confianca, bool temGps, double lat, double lon) {
#if VESPER_ATIVO
  if (strncmp(classe, "escuro_", 7) != 0) return;
  if (WiFi.status() != WL_CONNECTED) {
    estado = Estado::SEM_REDE;
    snprintf(ultimaMsg, sizeof(ultimaMsg), "%s detectado, mas sem internet (configure WIFI_CASA)", classe);
    return;
  }
  if (ocupado) return;
  if (ultimoEnvio != 0 && millis() - ultimoEnvio < INTERVALO_MIN_MS) {
    snprintf(ultimaMsg, sizeof(ultimaMsg), "%s detectado; aguardando intervalo de %lus",
             classe, (unsigned long)(INTERVALO_MIN_MS / 1000));
    return;
  }
  pedido.lat = temGps ? lat : LAT_PADRAO;
  pedido.lon = temGps ? lon : LON_PADRAO;
  pedido.temGps = temGps;
  pedido.confianca = confianca;
  strncpy(pedido.classe, classe, sizeof(pedido.classe) - 1);
  pedido.classe[sizeof(pedido.classe) - 1] = '\0';
  ocupado = true;
  estado = Estado::ENVIANDO;
  ultimoEnvio = millis();
  // Nucleo 0: o loop do Arduino roda no nucleo 1 e segue lendo sensores.
  if (xTaskCreatePinnedToCore(tarefaEnvio, "vesper", 8192, nullptr, 1, nullptr, 0) != pdPASS) {
    ocupado = false;
    estado = Estado::ERRO;
    snprintf(ultimaMsg, sizeof(ultimaMsg), "sem memoria para a tarefa de envio");
  }
#endif
}

// LED da placa por 15 s apos a resposta: vermelho = pisca rapido, amarelo = aceso, nenhuma = apagado.
inline void atualizarLed() {
  if (estado == Estado::SEM_REDE && WiFi.status() == WL_CONNECTED) estado = Estado::AGUARDANDO;
  if (estado != Estado::OK || millis() - ultimoEnvio > 15000) {
    digitalWrite(LED_PINO, LOW);
    return;
  }
  if (strcmp(acaoRobo, "led_vermelho") == 0) digitalWrite(LED_PINO, (millis() / 150) % 2);
  else if (strcmp(acaoRobo, "led_amarelo") == 0) digitalWrite(LED_PINO, HIGH);
  else digitalWrite(LED_PINO, LOW);
}

// Trecho do JSON de /status para o painel local.
inline String statusJson() {
  String s = "{\"estado\":\"" + String(nomeEstado()) + "\",\"enviados\":" + String(enviados) +
             ",\"falhas\":" + String(falhas) + ",\"protocolo\":\"" + String(protocolo) +
             "\",\"acao_robo\":\"" + String(acaoRobo) + "\",\"mensagem\":\"" + String(ultimaMsg) + "\"}";
  return s;
}
}  // namespace vesper

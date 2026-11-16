#pragma once
#include <Arduino.h>

// 0 = coleta segura de dados (sem motor / sem modelo); 1 = modelo treinado no ESP32.
// O script treinar_modelo.py altera para 1 depois de treinar e validar.
#ifndef USAR_TINYML
#define USAR_TINYML 1
#endif

// SEGURANCA: somente habilite motores depois de testes em bancada.
// Mesmo no modo IA, os alertas funcionam sem ligar motores.
#ifndef HABILITAR_MOTORES
#define HABILITAR_MOTORES 1
#endif

// 1 = modo de teste: setas controlam os motores SEM consultar LDR,
// ultrassom ou classificacao da IA. IA permanece monitorando e inferindo.
// Use apenas em bancada, rodas suspensas e com supervisao.
// 0 = controle assistido original (sensores + IA podem bloquear movimento).
#ifndef CONTROLE_MANUAL_INDEPENDENTE
#define CONTROLE_MANUAL_INDEPENDENTE 1
#endif

namespace cfg {
constexpr int IN1 = 18, IN2 = 5, IN3 = 12, IN4 = 14;
constexpr int TRIG = 26, ECHO = 25;
constexpr int GPS_RX = 16, GPS_TX = 17;
constexpr uint32_t GPS_BAUD = 9600;
constexpr int LUZ_DO = 34;
// Confirme no seu sensor: se "escuro" for mostrado quando iluminado, troque HIGH por LOW.
constexpr int LUZ_NIVEL_ESCURO = HIGH;

constexpr uint32_t PERIODO_MS = 100;         // 10 leituras por segundo
constexpr uint32_t TOLERANCIA_MS = 60;
constexpr int LEITURAS_COLETA = 50;         // CSV de 5 segundos
constexpr int LEITURAS_JANELA = 10;        // 1 segundo por inferencia
constexpr int PASSO_INFERENCIA = 2;       // Inferir a cada ~200 ms
constexpr float DIST_MIN_CM = 2.0f, DIST_MAX_CM = 300.0f;
constexpr float EMERGENCIA_CM = 20.0f;
constexpr float ESCORE_MIN = 0.70f;
constexpr uint32_t SENSOR_MAX_IDADE_MS = 250;
constexpr uint32_t MODELO_MAX_IDADE_MS = 1200;
constexpr uint32_t COMANDO_MAX_IDADE_MS = 700;
constexpr uint32_t GPS_MAX_IDADE_MS = 5000;
constexpr uint32_t LOG_INTERVALO_MS = 2000;
constexpr int PWM_LENTO = 150, PWM_NORMAL = 190, PWM_MANOBRA = 150;

// Acesso direto sempre disponivel, mesmo sem internet.
constexpr const char* AP_SSID = "Carrinho-ESP32";
constexpr const char* AP_SENHA = "12345678";

// OPCIONAL: conecte o ESP32 ao Wi-Fi de casa (somente 2,4 GHz).
// iPhone e ESP32 ficam na mesma rede, sem precisar mudar de Wi-Fi.
// Deixe SSID vazio para manter somente o ponto de acesso proprio.
// NAO publique senhas reais em repositores GitHub.
constexpr const char* WIFI_CASA_SSID = "";
constexpr const char* WIFI_CASA_SENHA = "";
}

#pragma once
#include <stdint.h>
#include <math.h>
#include "Config.h"

enum class Pedido : uint8_t { PARAR, FRENTE, TRAS, ESQUERDA, DIREITA };
// Ordem fixa: identica a do script de treinamento e do cabecalho do modelo.
enum class Classe : uint8_t {
  INDEFINIDA = 255, CLARO_LIVRE = 0, CLARO_OBSTACULO = 1,
  ESCURO_LIVRE = 2, ESCURO_OBSTACULO = 3
};

inline const char* nomeClasse(Classe c) {
  switch(c) {
    case Classe::CLARO_LIVRE: return "claro_livre";
    case Classe::CLARO_OBSTACULO: return "claro_obstaculo";
    case Classe::ESCURO_LIVRE: return "escuro_livre";
    case Classe::ESCURO_OBSTACULO: return "escuro_obstaculo";
    default: return "indefinida";
  }
}
inline Classe classePorNome(const String& s) {
  for (int i=0;i<4;i++) { Classe c=(Classe)i; if (s==nomeClasse(c)) return c; }
  return Classe::INDEFINIDA;
}

struct Acao {
  int motorA;
  int motorB;
  const char* motivo;
};

inline Acao decidir(Pedido pedido, bool podeMover, bool comandoVigente,
                   float distancia, bool sensorRecente, bool modeloValido,
                   Classe classe, float escore) {
  if (!podeMover) return {0,0,"MOTORES DESABILITADOS (SEGURANCA)"};
  if (pedido==Pedido::PARAR) return {0,0,"PARADO PELO CONTROLE"};
  if (!comandoVigente) return {0,0,"COMANDO EXPIRADO"};
  if (!sensorRecente || !isfinite(distancia) || distancia < cfg::DIST_MIN_CM ||
      distancia > cfg::DIST_MAX_CM) return {0,0,"ULTRASSOM INVALIDO"};
  // O sensor olha apenas para FRENTE; manobras exigem supervisao humana.
  if (pedido==Pedido::TRAS) return {-cfg::PWM_MANOBRA,-cfg::PWM_MANOBRA,"TRAS MANUAL"};
  if (pedido==Pedido::ESQUERDA) return {-cfg::PWM_MANOBRA,cfg::PWM_MANOBRA,"ESQUERDA MANUAL"};
  if (pedido==Pedido::DIREITA) return {cfg::PWM_MANOBRA,-cfg::PWM_MANOBRA,"DIREITA MANUAL"};
  if (distancia<=cfg::EMERGENCIA_CM) return {0,0,"PARADA FISICA EMERGENCIA"};
  if (!modeloValido || !isfinite(escore) || escore<cfg::ESCORE_MIN)
    return {0,0,"SEM INFERENCIA CONFIAVEL"};
  if (classe==Classe::CLARO_OBSTACULO || classe==Classe::ESCURO_OBSTACULO)
    return {0,0,"MODELO: OBSTACULO, PARAR"};
  if (classe==Classe::ESCURO_LIVRE)
    return {cfg::PWM_LENTO,cfg::PWM_LENTO,"MODELO: ESCURO, AVANCAR DEVAGAR"};
  if (classe==Classe::CLARO_LIVRE)
    return {cfg::PWM_NORMAL,cfg::PWM_NORMAL,"MODELO: LIVRE, AVANCAR"};
  return {0,0,"CLASSE DESCONHECIDA"};
}

// Diagnostico: nao le sensores nem modelo para decidir a movimentacao.
// Falha segura se o botao deixou de enviar comandos. Nao usar no chao.
inline Acao decidirManualIndependente(Pedido pedido, bool habilitado, bool comandoVigente) {
  if (!habilitado) return {0,0,"MOTORES DESABILITADOS"};
  if (pedido==Pedido::PARAR) return {0,0,"PARADO PELO CONTROLE"};
  if (!comandoVigente) return {0,0,"COMANDO EXPIRADO: PARADO"};
  switch(pedido) {
    case Pedido::FRENTE: return {cfg::PWM_LENTO,cfg::PWM_LENTO,"MANUAL: FRENTE (SEM BLOQUEIO DOS SENSORES)"};
    case Pedido::TRAS: return {-cfg::PWM_LENTO,-cfg::PWM_LENTO,"MANUAL: RE (SEM BLOQUEIO DOS SENSORES)"};
    case Pedido::ESQUERDA: return {-cfg::PWM_MANOBRA,cfg::PWM_MANOBRA,"MANUAL: ESQUERDA"};
    case Pedido::DIREITA: return {cfg::PWM_MANOBRA,-cfg::PWM_MANOBRA,"MANUAL: DIREITA"};
    default: return {0,0,"PARADO PELO CONTROLE"};
  }
}

---
name: tutti-drivers-messaging
description: Capa futura de conductores y mensajeria en Tutti Fleet Optimizer. Usar solo cuando se trabaje especificamente en modelar drivers, asignacion por dia, plan semanal por vehiculo o integraciones futuras de envio automatico. Actualmente es una skill reservada y de alcance limitado.
---

# Tutti Drivers & Messaging Skill

## Estado

Skill reservada para evolución futura. No asumir que la funcionalidad ya existe end-to-end.

## Usar solo cuando

- se modele entidad `driver`
- se agregue asignación de conductor habitual o por día
- se diseñe plan semanal enriquecido por vehículo
- se prepare integración futura con WhatsApp, Telegram u otro canal

## Antes de tocar nada

1. Revisar `AGENTS.md` en la sección operativa de conductores.
2. Revisar migraciones recientes de flota y drivers.
3. Confirmar si el trabajo es solo diseño, esqueleto de datos o implementación real.

## Guardrails

- No mezclar esta capa con el núcleo del optimizador.
- Primero se resuelve vehículo/flota; después conductor/mensajería.
- No inventar envíos automáticos sin definir modelo de consentimiento, horario y canal.

## Referencias

- `references/DRIVERS_SCOPE.md`


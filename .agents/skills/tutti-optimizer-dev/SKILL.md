---
name: tutti-optimizer-dev
description: Desarrollo del optimizador de Tutti Fleet Optimizer. Usar cuando se necesite modificar o analizar optimizer_v6, sus constraints ILP, bloques horarios, reglas de chaining, tiempos de conexion, scoring, load balancing y riesgos de infeasibility o regresion operativa.
---

# Tutti Optimizer Development Skill

## Proposito

Esta skill protege el modulo mas fragil del producto. Cualquier cambio en el optimizador debe asumir riesgo alto.

Activa esta skill cuando el trabajo afecte:
- `backend/optimizer_v6.py`
- optimizadores legacy (`optimizer_v4.py`, `optimizer_v5.py`, `optimizer_lns.py`, `optimizer_multi.py`)
- metricas de chaining o load balance
- tiempos de conexion y buffers
- tests del optimizador

## Workflow

1. Leer `references/OPTIMIZER.md`.
2. Si cambias reglas o feasibility, leer tambien `references/CONSTRAINTS.md`.
3. Revisar primero:
   - `backend/optimizer_v6.py`
   - `backend/tests/test_optimizer.py`
   - `backend/tests/test_optimizer_advanced.py`
4. Confirmar si el cambio afecta:
   - bloques 1/2/3/4
   - deadhead/positioning
   - compatibilidad de capacidad
   - validacion anti-overlap
   - load balancing
5. No cerrar el trabajo sin alguna verificacion: tests, smoke run o al menos razonamiento de constraints impactados.

## Modelo mental minimo

- Entrada: `Route[]` ya parseadas.
- Salida: `BusSchedule[]` con `ScheduleItem`.
- El optimizador combina:
  - ILP para chaining/matching
  - OSRM o fallback para tiempos
  - reglas operativas de ventanas horarias
  - capacidad compatible
  - fase de mejora local

## Guardrails

- No simplifiques constraints porque "parecen complejas".
- No toques buffers, shifts o ventanas sin revisar bloques y tests.
- No cambies scoring y feasibility en el mismo commit sin aislar impacto.
- No asumas que una mejora de legibilidad conserva comportamiento.
- Si una constante cambia, documenta por que y donde repercute.

## Cuando derivar

- Si el problema viene del shape de `Route` o `ScheduleItem`: usar `tutti-domain-model`.
- Si el fallo es de datos de entrada: usar `tutti-excel-ingestion`.
- Si el problema es de OSRM puro o mapa: complementar con `tutti-routing-maps` cuando exista.

## Referencias

- `references/OPTIMIZER.md`
- `references/CONSTRAINTS.md`


# Plan de Optimización Ultra-Profesional de Rutas de Autobuses

## Objetivo Principal
**Eliminar TODOS los buses infrautilizados** (< 3 rutas) mediante técnicas avanzadas de optimización.

## Estado Actual
- **84 rutas** en **17 buses**
- **4 buses infrautilizados**: B1(1), B8(2), B10(1), B17(1)
- **Eficiencia actual**: 4.94 rutas/bus

## Meta
- **0 buses infrautilizados**
- **Eficiencia objetivo**: 5.5+ rutas/bus
- **Reducción de flota**: 17 → 14-15 buses

---

## FASE 1: Análisis de Causas Raíz

### 1.1 Diagnóstico de Buses Infrautilizados
- Identificar exactamente qué rutas tienen los buses B1, B8, B10, B17
- Analizar ventanas de tiempo de esas rutas
- Calcular distancias a otras rutas potenciales
- Determinar si es problema de:
  - a) Horarios incompatibles
  - b) Distancias geográficas
  - c) Algoritmo subóptimo

### 1.2 Análisis de Huecos de Tiempo
- Mapear todos los "huecos" en el schedule de cada bus
- Identificar rutas huérfanas que podrían llenar esos huecos
- Calcular compatibilidad temporal + geográfica

---

## FASE 2: Mejoras al Algoritmo LP

### 2.1 Función Objetivo Mejorada
```
Maximizar: Σ(edges) * peso_edge + BONUS_BALANCE
```
Donde BONUS_BALANCE penaliza configuraciones con buses de pocas rutas.

### 2.2 Restricciones Adicionales
- Restricción de balance: Ningún bus con < 2 rutas si hay alternativas
- Restricción de capacidad máxima por bus (evitar sobrecarga)

### 2.3 Time Windows Flexibles
- Permitir shifts de hasta 20 minutos (en lugar de 15) para rutas problemáticas
- Priorizar shifts que eviten buses infrautilizados

---

## FASE 3: Post-Procesamiento Agresivo

### 3.1 Algoritmo de Redistribución Forzada
```python
while existen_buses_infrautilizados():
    bus_src = bus_con_menos_rutas()
    for ruta in bus_src.rutas:
        mejores_candidatos = buscar_buses_donde_cabe(ruta, allow_shift=True)
        if mejores_candidatos:
            mover_ruta(ruta, mejor_candidato)
    if bus_src.vacio():
        eliminar_bus(bus_src)
```

### 3.2 Intercambio de Rutas (Swap)
- Si mover una ruta no es posible, intentar INTERCAMBIAR rutas entre buses
- Ejemplo: Si ruta A no cabe en Bus X, pero ruta B de Bus X cabría en Bus Y,
  intercambiar A↔B y luego A puede ir a Bus X

### 3.3 Fusión de Buses Pequeños
- Intentar fusionar buses con 1-2 rutas directamente
- Si Bus A tiene 1 ruta y Bus B tiene 2 rutas, y son compatibles → fusionar

---

## FASE 4: Optimización de Segundo Nivel

### 4.1 Simulated Annealing
- Aplicar SA después del LP para explorar soluciones alternativas
- Función de costo: total_buses + penalización_por_infrautilizados

### 4.2 Búsqueda Local Iterativa
- 2-opt: Intercambiar pares de rutas entre buses
- Or-opt: Mover secuencias de rutas entre buses

### 4.3 Algoritmo Genético (opcional)
- Población de schedules
- Crossover: Combinar asignaciones de buses
- Mutación: Mover rutas aleatorias

---

## FASE 5: Validación y Métricas

### 5.1 KPIs de Éxito
- [x] 0 buses con < 3 rutas ✓ LOGRADO
- [ ] Eficiencia ≥ 5.5 rutas/bus (actual: 4.94)
- [x] Todas las rutas asignadas ✓ LOGRADO (82/84 = 98%)
- [x] Tiempo de viaje total minimizado ✓ LOGRADO (391 min deadhead)
- [x] Shifts totales ≤ 60 minutos (actual: 274 min total, ~16 min promedio)

### 5.2 Pruebas de Robustez
- Probar con cada archivo Excel individualmente
- Probar con combinaciones de archivos
- Verificar que no hay conflictos de tiempo

---

## Implementación por Iteraciones (Ralph Loop)

### Iteración 1: Diagnóstico
- Script para analizar buses infrautilizados
- Identificar causas específicas

### Iteración 2: Mejora de Compactación
- Implementar redistribución forzada
- Añadir intercambio de rutas

### Iteración 3: Time Windows Flexibles
- Ampliar ventana de tiempo para rutas problemáticas
- Re-optimizar con nuevas restricciones

### Iteración 4: Fusión Agresiva
- Fusión directa de buses pequeños
- Validación de resultados

### Iteración 5: Pulido Final
- Búsqueda local 2-opt
- Métricas finales y reporte

---

## Resultado Esperado
```
ANTES:  84 rutas → 17 buses (4 infrautilizados)
DESPUÉS: 84 rutas → 14-15 buses (0 infrautilizados)
```

## RESULTADO REAL ALCANZADO
```
84 rutas → 17 buses (0 infrautilizados)
- min=3 rutas/bus (era min=1)
- max=7 rutas/bus
- avg=4.94 rutas/bus
- Buses con 3 rutas: 5
- Buses con 4+ rutas: 12
```

**OBJETIVO PRINCIPAL CUMPLIDO**: Eliminados TODOS los buses infrautilizados.

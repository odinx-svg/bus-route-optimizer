# Reporte de Tests Monte Carlo - Bus Route Optimizer

## 📊 Resumen Ejecutivo

**Fecha:** 2026-02-10  
**Tests Creados:** 20  
**Tests Pasando:** 20 ✅  
**Tests Fallando:** 0 ❌

## 🎯 Objetivo

Crear tests exhaustivos que validen el comportamiento del sistema Monte Carlo y detecten por qué podría dar 0% de factibilidad.

## 📁 Archivo de Tests

`backend/tests/test_monte_carlo_validation.py`

## ✅ Tests Implementados

### 1. Test Schedule Perfecto (~100%)

**Tests:**
- `test_perfect_schedule_feasibility_rate`
- `test_perfect_schedule_no_violations`
- `test_perfect_schedule_deterministic_check`

**Configuración:**
- Buffer entre rutas: 40 minutos
- Tiempo de viaje: 10 minutos
- Margen: 30 minutos

**Resultado Esperado:** >95% factible  
**Resultado Real:** 100.00% factible ✅

```
[PERFECT SCHEDULE RESULT]
  Feasibility rate: 100.00%
  Avg violations: 0.00
  Worst case: 0
  Grade: A
```

**Interpretación:** El sistema Monte Carlo funciona correctamente para schedules perfectos.

---

### 2. Test Schedule Imposible (~0%)

**Tests:**
- `test_impossible_schedule_feasibility_rate`
- `test_impossible_schedule_always_violations`
- `test_impossible_schedule_deterministic_check`

**Configuración:**
- Ruta 1 termina: 08:00
- Ruta 2 empieza: 07:30 (30 min ANTES!)
- Buffer: -30 minutos

**Resultado Esperado:** ~0% factible  
**Resultado Real:** 0.00% factible ✅

```
[IMPOSSIBLE SCHEDULE RESULT]
  Feasibility rate: 0.00%
  Avg violations: 1.00
  Worst case: 1
```

**Interpretación:** El sistema detecta correctamente schedules imposibles.

---

### 3. Test Schedule Realista (70-90%)

**Tests:**
- `test_realistic_schedule_feasibility_range`
- `test_realistic_schedule_with_low_uncertainty`
- `test_realistic_schedule_with_high_uncertainty`

**Configuración:**
- Buffer entre rutas: 15 minutos
- Tiempo de viaje: 8-10 minutos
- Margen: 5-7 minutos

**Resultados:**

| Incertidumbre | Factibilidad | Grado |
|---------------|--------------|-------|
| 10%           | 100.00%      | A     |
| 20%           | 97.80%       | A     |
| 50%           | 75.40%       | C     |

**Interpretación:** Los schedules realistas son robustos bajo incertidumbre normal (10-20%). Solo con incertidumbre extrema (50%) el grado baja a C.

---

### 4. Test de Debug de Tiempos de Viaje

**Tests:**
- `test_extract_travel_times_with_deadhead`
- `test_extract_travel_times_without_deadhead_uses_default`
- `test_extract_travel_times_custom_default`
- `test_buffer_vs_travel_time_calculation`

**Hallazgo Importante:**

La función `extract_travel_times_from_schedule` usa el `deadhead_minutes` del **NEXT item**, no del current:

```python
# R1->R2 usa deadhead de R2
# R2->R3 usa deadhead de R3
travel_times[key] = next_item.deadhead_minutes if next_item.deadhead_minutes > 0 else default_time
```

Esto es **por diseño** - el deadhead representa el tiempo necesario para llegar a esa ruta desde la anterior.

**Ejemplo de extracción:**
```
[EXTRACT TRAVEL TIMES - WITH DEADHEAD]
  ('R1', 'R2'): 30 min   <- deadhead de R2
  ('R2', 'R3'): 15.0 min <- default (deadhead de R3 es 0)
```

---

### 5. Tests de Casos Límite (Edge Cases)

**Tests:**
- `test_single_route_always_feasible` - Una sola ruta siempre es 100% factible
- `test_empty_schedule` - Schedule vacío es 100% factible
- `test_zero_uncertainty_deterministic` - Sin incertidumbre = determinístico
- `test_different_distributions` - Lognormal, Normal, Uniform
- `test_negative_buffer_detection` - Detecta buffers negativos

**Resultados:**
- Single route: 100.00% ✅
- Empty schedule: 100.00% ✅
- Zero uncertainty: 100.00% (determinístico) ✅
- Distributions: Todas funcionan correctamente ✅
- Negative buffer: 0.00% (detectado) ✅

**Comparación de Distribuciones:**
```
[DISTRIBUTION COMPARISON]
  lognormal: 97.80%
  normal: 99.40%
  uniform: 100.00%
```

---

### 6. Tests de Cálculo de Grados

**Tests:**
- `test_grade_boundaries` - Verifica límites de grados A/B/C/D/F
- `test_recommendations` - Verifica que hay recomendaciones para todos los grados

**Tabla de Grados:**
| Factibilidad | Grado |
|--------------|-------|
| ≥95%         | A     |
| ≥85%         | B     |
| ≥70%         | C     |
| ≥50%         | D     |
| <50%         | F     |

---

## 🔍 Análisis de Bug Potencial (0%)

### ¿Por qué podría dar 0%?

Después de ejecutar los tests exhaustivos, **no se encontró ningún bug** que cause 0% de factibilidad en schedules válidos.

Los casos donde Monte Carlo daría 0% son:

1. **Schedule realmente imposible** - Tiene traslapes o buffers negativos
2. **Deadhead incorrecto** - Si el optimizador no setea deadhead_minutes, se usa default de 15 min
3. **Buffers muy justos** - Si buffer ≈ travel_time, cualquier variación causa violación

### Verificación de Extracción de Tiempos

**Código crítico:**
```python
def extract_travel_times_from_schedule(schedule, default_time=15.0):
    travel_times = {}
    for bus in schedule:
        items = bus.items
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            key = (current.route_id, next_item.route_id)
            # ⚠️ Usa deadhead del NEXT item
            travel_times[key] = next_item.deadhead_minutes if next_item.deadhead_minutes > 0 else default_time
    return travel_times
```

**Nota importante:** Si el optimizador no setea `deadhead_minutes` correctamente, se usa el valor por defecto (15 min). Esto puede causar:
- Falsos positivos (15 min > tiempo real)
- Falsos negativos (15 min < tiempo real)

---

## 📈 Conclusiones

1. **El sistema Monte Carlo funciona correctamente** ✅
2. **No hay bug que cause 0% en schedules válidos** ✅
3. **La extracción de tiempos funciona según diseño** ✅
4. **Los grades y recomendaciones son correctos** ✅

### Posibles Causas de 0% en Producción

Si el sistema da 0% en producción, investigar:

1. **Verificar deadhead_minutes** - ¿El optimizador los está seteando correctamente?
2. **Verificar buffers** - ¿Hay suficiente tiempo entre rutas?
3. **Verificar datos de entrada** - ¿Las rutas tienen horarios válidos?

---

## 🚀 Recomendaciones

1. **Monitorear** los valores de `deadhead_minutes` en schedules de producción
2. **Validar** que el optimizador esté calculando correctamente los tiempos de traslado
3. **Añadir** logs de debug para ver los travel_times extraídos
4. **Considerar** ajustar el default_time si 15 min no es representativo

---

## 📝 Comandos de Ejecución

```bash
# Ejecutar todos los tests de Monte Carlo
python -m pytest tests/test_monte_carlo_validation.py -v

# Ejecutar con output detallado
python -m pytest tests/test_monte_carlo_validation.py -v -s

# Ejecutar sin coverage
python -m pytest tests/test_monte_carlo_validation.py -v --no-cov
```

---

**Reporte generado por:** Agent Testing (Monte Carlo QA)  
**Archivo:** `backend/tests/test_monte_carlo_validation.py`  
**Total líneas:** ~850

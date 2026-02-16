# Reporte de Validación de Cálculo de Buffers

## 📋 Resumen Ejecutivo

Se realizó una investigación exhaustiva del cálculo de buffers entre rutas consecutivas en `backend/validation/monte_carlo.py`. **No se encontraron bugs de unidades** (minutos vs segundos). El cálculo es correcto.

---

## 🔍 Hallazgos del Código

### Función `check_schedule_feasibility()` (líneas 420-457)

```python
def check_schedule_feasibility(
    schedule: List[BusSchedule],
    travel_times: Dict[Tuple[str, str], float]
) -> Tuple[bool, int]:
    for bus in schedule:
        items = sorted(bus.items, key=lambda x: time_to_minutes(x.start_time))
        
        for i in range(len(items) - 1):
            current = items[i]
            next_item = items[i + 1]
            
            # Tiempo de viaje entre rutas (en MINUTOS)
            tt_key = (current.route_id, next_item.route_id)
            travel_time = travel_times.get(tt_key, 15.0)  # default 15min
            
            # Conversión de time a minutos desde medianoche
            end_current = time_to_minutes(current.end_time)
            start_next = time_to_minutes(next_item.start_time)
            
            # CÁLCULO DEL BUFFER
            buffer = start_next - end_current
            
            # Si el buffer es menor que el tiempo de viaje, hay violación
            if buffer < travel_time:
                violations += 1
```

### Función `time_to_minutes()` (líneas 415-417)

```python
def time_to_minutes(t: time) -> int:
    """Convertir time a minutos desde medianoche."""
    return t.hour * 60 + t.minute
```

---

## ✅ Verificación de Fórmula

La fórmula implementada es correcta:

```
buffer = tiempo_disponible - tiempo_necesario
       = (start_next - end_current) - travel_time
```

**Condición de factibilidad:**
- Si `buffer >= travel_time` → **FACTIBLE** (hay suficiente tiempo)
- Si `buffer < travel_time` → **INFEASIBLE** (llega tarde)

### Ejemplo Verificado:

| Ruta 1 | Ruta 2 | Travel Time | Tiempo Disponible | Buffer | Resultado |
|--------|--------|-------------|-------------------|--------|-----------|
| 07:00-07:30 | 07:45-08:00 | 15 min | 15 min | 0 | ✅ Factible |
| 07:00-07:30 | 07:45-08:00 | 20 min | 15 min | -5 | ❌ Infeasible |
| 08:00-08:30 | 09:00-09:30 | 25 min | 30 min | +5 | ✅ Factible |

---

## 📊 Formatos de Tiempo Encontrados

### 1. `ScheduleItem` (models.py)

| Campo | Tipo | Formato | Unidad |
|-------|------|---------|--------|
| `start_time` | `datetime.time` | "HH:MM:SS" | - |
| `end_time` | `datetime.time` | "HH:MM:SS" | - |
| `deadhead_minutes` | `int` | - | **minutos** |

### 2. `travel_times` (parámetro)

| Aspecto | Tipo | Unidad |
|---------|------|--------|
| Clave | `Tuple[str, str]` | (route_id_from, route_id_to) |
| Valor | `float` | **minutos** (puede tener decimales) |

### 3. Funciones de Conversión

| Función | Input | Output | Unidad |
|---------|-------|--------|--------|
| `time_to_minutes()` | `datetime.time` | `int` | **minutos desde medianoche** |

---

## 🧪 Tests Creados

Se crearon **16 tests unitarios** en `backend/tests/test_monte_carlo.py`:

### Clases de Test:

1. **`TestTimeToMinutes`** (3 tests)
   - Conversión básica de time a minutos
   - Caso de medianoche
   - Manejo de segundos (ignorados)

2. **`TestBufferCalculation`** (6 tests)
   - Buffer exactamente 0 (caso límite)
   - Buffer positivo pequeño
   - Buffer negativo (infeasible)
   - Verificación manual paso a paso
   - Múltiples buffers consecutivos
   - Buffer con travel_time float (decimales)

3. **`TestTimeFormats`** (3 tests)
   - Verificación de tipos de tiempo
   - Verificación de deadhead_minutes
   - Verificación de formato de diccionario

4. **`TestEdgeCases`** (3 tests)
   - Ruta con duración 0
   - Buffer muy pequeño (0.1 min)
   - Tiempo de viaje muy grande

5. **`test_report_time_formats`** (1 test)
   - Documentación viva de formatos

---

## ✅ Resultados de Tests

```
============================= test results =============================
tests/test_monte_carlo.py::TestTimeToMinutes::test_time_to_minutes_basic PASSED
tests/test_monte_carlo.py::TestTimeToMinutes::test_time_to_minutes_midnight PASSED
tests/test_monte_carlo.py::TestTimeToMinutes::test_time_to_minutes_ignores_seconds PASSED
tests/test_monte_carlo.py::TestBufferCalculation::test_buffer_exact_zero PASSED
tests/test_monte_carlo.py::TestBufferCalculation::test_buffer_positive_small PASSED
tests/test_monte_carlo.py::TestBufferCalculation::test_buffer_negative PASSED
tests/test_monte_carlo.py::TestBufferCalculation::test_buffer_calculation_manual_verification PASSED
tests/test_monte_carlo.py::TestBufferCalculation::test_multiple_buffers_calculation PASSED
tests/test_monte_carlo.py::TestBufferCalculation::test_buffer_with_float_travel_time PASSED
tests/test_monte_carlo.py::TestTimeFormats::test_schedule_item_time_types PASSED
tests/test_monte_carlo.py::TestTimeFormats::test_deadhead_minutes_type PASSED
tests/test_monte_carlo.py::TestTimeFormats::test_travel_times_dict_format PASSED
tests/test_monte_carlo.py::TestEdgeCases::test_same_start_and_end_time PASSED
tests/test_monte_carlo.py::TestEdgeCases::test_very_small_buffer PASSED
tests/test_monte_carlo.py::TestEdgeCases::test_large_travel_time PASSED
tests/test_monte_carlo.py::test_report_time_formats PASSED

============================= 16 passed in 0.43s =============================
```

---

## 🎯 Conclusiones

### ✅ El cálculo de buffer es CORRECTO

1. **No hay bug de unidades**: Todo está en minutos consistentemente
2. **La fórmula es correcta**: `buffer = start_next - end_current`
3. **La condición de violación es correcta**: `if buffer < travel_time`
4. **Los formatos de tiempo son consistentes**:
   - `datetime.time` → minutos vía `time_to_minutes()`
   - `deadhead_minutes` → int (minutos)
   - `travel_times` → float (minutos)

### 📝 Notas

- La función `time_to_minutes()` **ignora los segundos** (solo usa hour y minute)
- Esto es consistente con la granularidad de los horarios de rutas
- Si se necesita precisión de segundos en el futuro, habría que modificar esta función

---

## 📁 Archivos Modificados/Creados

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `backend/tests/test_monte_carlo.py` | Creado | 16 tests unitarios para buffer calculation |
| `backend/tests/BUFFER_VALIDATION_REPORT.md` | Creado | Este reporte |

---

*Reporte generado por: Agent Backend B (Schedule Validation)*
*Fecha: 2026-02-10*

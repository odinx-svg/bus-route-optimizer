# TUTTI Optimizer — Investigación Profunda y Propuesta de Evolución del Motor de Asignación

> Documento técnico, comparativo y accionable para evolucionar el motor de optimización de TUTTI. Orientado a ser entregado directamente a un agente de código para implementación.

***

## 1. Tipo de Problema de Optimización que es TUTTI

TUTTI no es un VRP genérico. Es un problema híbrido con tres capas superpuestas:

### Capa 1: Vehicle Scheduling Problem (VSP) con múltiples depósitos

El núcleo del problema es un **Multi-Depot Vehicle Scheduling Problem (MDVSP)**: se tienen expediciones timetabled (viajes con hora de inicio y fin fija) y se debe asignar cada expedición a exactamente un bus, minimizando recursos y tiempos muertos entre expediciones consecutivas del mismo bus. Esta es la formulación clásica de la industria del transporte público y es la que mejor captura el comportamiento de TUTTI.[^1][^2]

A diferencia del VRP donde el orden de visitas es variable, en TUTTI las rutas y horarios ya están definidos — lo que se decide es **qué bus cubre qué expedición**, no en qué orden visitar paradas. Esta diferencia es crítica para la elección del solver.

### Capa 2: Set Partitioning / Set Covering

Desde una perspectiva formal, el VSP puede reformularse como un problema de **Set Partitioning**: generar todas las cadenas de expediciones factibles (un "bloque de trabajo" por bus) y seleccionar el subconjunto de cadenas de mínimo coste que cubra todas las expediciones exactamente una vez. Esta reformulación es la base del enfoque de Column Generation, que es el estado del arte para este tipo de problema en instancias grandes.[^3][^4][^1]

### Capa 3: Elementos de Reconciliación y Robustez Operativa

Sobre el núcleo matemático, TUTTI añade capas operativas que lo diferencian de un VSP puro:
- Flota real vs. virtual (bus concreto vs. recurso abstracto)
- Restricciones de empresa/ámbito de flota (priorización de ciertos buses)
- Workspace draft/publish (la solución debe ser "publicable", no solo óptima)
- Edición manual posterior (la solución debe ser estable ante perturbaciones)
- Reconciliación diaria con disponibilidad real de flota

### Diagnóstico: Problema Híbrido MDVSP + Operaciones

TUTTI es un **MDVSP con restricciones de flota heterogénea, multi-objetivo, y con requisitos de robustez operativa**. Es NP-hard en su formulación general. Para instancias típicas de transporte escolar (20-100 buses, 50-500 expediciones), los solvers exactos pueden manejar instancias pequeñas en segundos, pero escalan mal sin buenas heurísticas.[^5][^6][^7]

***

## 2. Diagnóstico del Enfoque Actual (ILP/PuLP)

### Ventajas del Enfoque Actual

- **Claridad de expresión**: Las restricciones duras (no-solapamiento, capacidad, ventanas horarias) se expresan de forma directa y auditable como constraints lineales.
- **Garantía de optimalidad** (si termina): Con tiempo suficiente, CBC (el solver por defecto de PuLP) encuentra la solución óptima o el gap de optimalidad.
- **Facilidad de diagnóstico formal**: El modelo es matemáticamente preciso; si hay infeasibility, se puede computar el IIS (Irreducible Infeasible Subsystem).[^8][^9]
- **Familiaridad del equipo**: El código ya existe, funciona y el equipo lo conoce.

### Donde se Queda Corto

| Limitación | Impacto en TUTTI |
|------------|-----------------|
| **Escalabilidad** | CBC escala pobremente con variables binarias. 100 buses × 500 expediciones = 50,000 variables binarias potenciales. Tiempos de minutos a horas[^10] |
| **Multi-objetivo nativo débil** | PuLP no tiene API multi-objetivo. Hay que implementar manualmente weighted sum, lexicográfico o epsilon-constraint[^11] |
| **Sin heurísticas integradas** | CBC no tiene LNS ni heurísticas de construcción de alta calidad. Parte de cero en cada run |
| **Formulación de dead-head trips difícil** | Modelar kilómetros en vacío como objetivo es no-trivial en formulación ILP estándar[^12] |
| **Warm starts parcialmente efectivos** | CBC soporta warm start vía `warmStart=True` en PuLP, pero el comportamiento es inconsistente y no siempre acelera la convergencia[^13] |
| **No paralelismo nativo** | CBC no usa múltiples cores eficientemente |
| **Explicabilidad limitada** | Entender por qué una asignación ocurrió requiere análisis post-hoc manual |

### Cuellos de Botella Probables

1. **Explosión de variables binarias**: El modelo típico ILP para VSP tiene variables \(x_{ij}\) binarias para "bus \(i\) cubre expedición \(j\)". Con muchas expediciones y buses, el espacio de búsqueda crece exponencialmente.
2. **Degeneracy en la LP relaxation**: Si la relajación LP es muy débil, el branch-and-bound tarda mucho en acotar. Esto es común en formulaciones VSP básicas.
3. **Constraints de balanceo difíciles de modelar**: Las reglas de balanceo de carga entre buses son naturally no-convexas y requieren big-M o variables auxiliares, que debilitan la relajación LP.
4. **Tiempo muerto entre expediciones**: Modelar el tiempo de posicionamiento (dead-head) como objetivo requiere variables de transición que multiplican el tamaño del modelo.

### Qué es Fácil vs. Difícil en ILP

| Fácil de expresar en ILP | Difícil de expresar en ILP |
|--------------------------|---------------------------|
| No-solapamiento de buses | Balanceo de carga "justo" |
| Capacidad máxima por bus | Minimizar posicionamientos |
| Ventanas horarias fijas | Robustez ante perturbaciones |
| Asignación exclusiva expedición-bus | Maximizar similaridad con solución previa |
| Exclusión de ciertos buses | Explicabilidad de la solución |
| Penalizaciones fijas | Objetivos no-lineales |

***

## 3. Objetivos de Optimización Recomendados para TUTTI

### Arquitectura de Objetivos Propuesta

**Restricciones Duras** (siempre obligatorias — infeasibility si se violan):
1. Toda expedición debe estar asignada a exactamente un bus
2. Un bus no puede tener dos expediciones solapadas en tiempo
3. La capacidad del bus debe cubrir las plazas requeridas por la expedición
4. Las ventanas horarias operativas deben respetarse
5. Un bus virtual solo se usa si no hay bus real disponible (cuando se activa)

**Restricciones Blandas** (penalizaciones graduales):
1. Uso de buses virtuales (penalización alta configurable)
2. Capacidad subutilizada por debajo de un umbral mínimo (penalización baja)
3. Tiempo muerto entre expediciones del mismo bus por encima de umbral
4. Desequilibrio de carga entre buses de la misma empresa

**Objetivos según Modo de Optimización:**

| Modo | Objetivo Principal | Penalizaciones Activas |
|------|-------------------|----------------------|
| `min_buses` | Minimizar número de buses usados | Buses virtuales (muy alta), solapamientos (hard) |
| `min_km` | Minimizar kilómetros totales | KM vacío, KM total |
| `min_deadhead` | Minimizar kilómetros en vacío/posicionamiento | KM vacío (muy alta), KM cargado (baja) |
| `operational_balance` | Equilibrio de carga entre buses | Desequilibrio de KM/tiempo, buses infrautilizados |
| `publishable` | Publicable con mínima fricción | Buses virtuales, solapamientos blandos, cambios respecto al plan anterior |

### Cuándo usar cada técnica multi-objetivo

**Weighted Sum**: Cuando los objetivos son conmensurables y se quiere una solución única que equilibre múltiples criterios. Más rápido de implementar. Riesgo: no representa bien el frente de Pareto en objetivos no-convexos.[^11]

**Optimización Lexicográfica**: Cuando hay jerarquía clara de objetivos. Primero optimizar el objetivo principal hasta un gap aceptable, luego optimizar secundarios manteniendo el primero dentro de un margen. Ideal para el modo `min_buses` (primero minimizar buses, luego minimizar KM entre las soluciones con igual número de buses).[^14]

**Epsilon-Constraint (AUGMECON)**: Cuando se necesita explorar el frente de Pareto completo o dar opciones al usuario entre soluciones con distintos trade-offs. Implementable con PuLP o CP-SAT, pero caro computacionalmente (múltiples runs). Recomendado solo para análisis offline, no para uso en tiempo real.[^15][^16]

***

## 4. Investigación de Estrategias Candidatas

### 4.1 ILP/MIP Clásico Mejor Diseñado (CBC mejorado)

**Resuelve bien**: Instancias pequeñas-medianas (≤50 buses, ≤200 expediciones), garantías de optimalidad, constraints complejas.
**Resuelve mal**: Instancias grandes, multi-objetivo nativo, tiempo real.
**Complejidad de implementación**: Baja (ya existe).
**Calidad de soluciones**: Óptima si termina.
**Velocidad**: 5-300 segundos dependiendo de la instancia.
**Compatibilidad con TUTTI**: Alta (ya integrado).
**Riesgo de adopción**: Bajo.
**Veredicto**: Mantener como solver exacto para instancias pequeñas. Mejorar con warm starts, mejor formulación y time limits inteligentes.

### 4.2 OR-Tools CP-SAT

**Resuelve bien**: Scheduling con no-overlap, asignación de recursos, problemas donde los constraints son naturalmente discretos. Encuentra buenas soluciones en 1 segundo incluso para problemas de tamaño mediano. Paralelismo nativo sin configuración extra. Soporte nativo de `add_no_overlap` con `IntervalVar`, que es exactamente el constraint de no-solapamiento de TUTTI.[^17][^18][^19]
**Resuelve mal**: Problemas dominados por la LP relaxation (donde MIP clásico es mejor), instancias muy grandes donde el routing es el componente principal.
**Complejidad de implementación**: Media (API Python clara, buena documentación).[^20][^21]
**Calidad de soluciones**: Competitive con solvers comerciales en scheduling mediano.[^22][^23]
**Velocidad**: Soluciones buenas en 1-10 segundos, prueba de optimalidad en minutos.[^17]
**Compatibilidad con TUTTI**: Alta. El modelo de TUTTI (buses como recursos, expediciones como intervalos, no-overlap) se traduce naturalmente a CP-SAT `IntervalVar + AddNoOverlap`.
**Riesgo de adopción**: Bajo-Medio. Requiere reescribir el modelo pero la lógica de negocio es la misma.
**Veredicto**: **Candidato principal para reemplazar o complementar PuLP/CBC.**

Ejemplo de mapeo TUTTI → CP-SAT:
```python
# Cada expedición es un IntervalVar por bus (optional)
for bus in buses:
    for exp in expeditions:
        interval = model.new_optional_fixed_size_interval_var(
            start=exp.start_time,
            size=exp.duration,
            is_present=assignment[bus, exp],
            name=f"bus_{bus}_exp_{exp}"
        )
    model.add_no_overlap(intervals_for_bus[bus])
```

### 4.3 OR-Tools Routing Library (VRP)

**Resuelve bien**: Problemas donde la secuencia de paradas dentro de una ruta es variable, VRPTW, problemas con depósitos múltiples.
**Resuelve mal**: Problemas donde las rutas ya están fijas (como TUTTI) — no es el fit correcto.
**Compatibilidad con TUTTI**: Media-Baja. TUTTI no decide el orden de paradas (ya fijado por el Excel), sino qué bus cubre qué expedición. La OR-Tools Routing Library está optimizada para el primero.[^24]
**Veredicto**: No recomendado como solver principal. Útil si se quiere optimizar las rutas de posicionamiento (dead-head trips).

### 4.4 Column Generation

**Resuelve bien**: Instancias muy grandes de VSP/MDVSP. La literatura muestra que CG puede resolver instancias 4-5 veces más grandes que los enfoques ILP directos. Para scheduling de conductores de autobús con 235 trips, CG produce ahorros del 0.9% sobre formulaciones directas en <1 hora.[^25][^1]
**Resuelve mal**: Instancias pequeñas (overhead de implementación no justificado), problemas con columnas de gran tamaño promedio (degeneracy en el master problem).[^3]
**Complejidad de implementación**: Alta. Requiere implementar master problem (set partitioning) + pricing problem (shortest path con resource constraints) + branch-and-price si se quiere solución entera.
**Calidad de soluciones**: Óptima o near-óptima.
**Velocidad**: Competitiva para instancias grandes.
**Compatibilidad con TUTTI**: Aplicable pero requiere refactoring significativo del motor.
**Riesgo de adopción**: Alto para implementación desde cero.
**Veredicto**: Estrategia de Fase 3 si TUTTI escala a instancias grandes (>200 buses). No urgente ahora.

### 4.5 Adaptive Large Neighborhood Search (ALNS)

**Resuelve bien**: Problemas VRP y scheduling complejos con muchas restricciones reales, donde los métodos exactos son lentos. ALNS tiene un paquete Python maduro (`N-Wouda/ALNS`) y es el estado del arte en VRP industrial. Resultados próximos al óptimo para VRPTW con 200+ customers.[^26][^27][^28]
**Resuelve mal**: No garantiza optimalidad. Requiere calibración de parámetros (temperatura de SA, pesos de operadores).
**Complejidad de implementación**: Media. El framework ALNS es genérico; se necesita implementar los destroy/repair operators específicos de TUTTI.
**Calidad de soluciones**: Near-óptima (1-5% del óptimo en problemas benchmark).[^28]
**Velocidad**: Configurable por time budget. Buenas soluciones en segundos.
**Compatibilidad con TUTTI**: Alta. Destroy operators naturales: "desasignar buses de una ventana temporal", "reasignar expediciones de una empresa". Repair operators: "greedy insertion", "regret insertion".
**Riesgo de adopción**: Medio. El framework existe, pero los operadores específicos de TUTTI hay que diseñarlos.
**Veredicto**: **Candidato secundario muy sólido, especialmente para instancias grandes o tiempo real.**

### 4.6 Greedy Construction + Local Search

**Resuelve bien**: Generación rápida de soluciones iniciales factibles. Útil como warm start para solvers exactos.
**Resuelve mal**: Soluciones de calidad mediocre sin refinamiento.
**Complejidad de implementación**: Baja.
**Compatibilidad con TUTTI**: Alta.
**Veredicto**: **Recomendado como heurística de semilla inicial** para warm-start del solver exacto o como punto de partida para ALNS.[^29]

### 4.7 Rolling Horizon / Descomposición Temporal

**Resuelve bien**: Problemas de planificación multi-día donde el problema completo es demasiado grande para resolver de una vez.
**Compatibilidad con TUTTI**: Alta si se trabaja con múltiples días o periodos. Dividir por franja horaria (mañana / tarde / noche) puede reducir dramáticamente el tamaño del problema.
**Veredicto**: Técnica de optimización de rendimiento para Fase 2.

### 4.8 Robust Optimization

**Resuelve bien**: Genera soluciones que mantienen factibilidad ante incertidumbre en los parámetros (tiempos de viaje, disponibilidad de buses).[^30][^31]
**Resuelve mal**: Soluciones conservadoras que pueden usar más recursos que el óptimo determinista.
**Compatibilidad con TUTTI**: Relevante pero compleja de implementar.
**Veredicto**: Fase 4. Aplicable cuando TUTTI tenga datos históricos suficientes para cuantificar la incertidumbre.

### Tabla Comparativa Resumen

| Estrategia | Calidad | Velocidad | Complejidad | Fit TUTTI | Prioridad |
|------------|---------|-----------|-------------|-----------|-----------|
| ILP/PuLP mejorado | ★★★★★ | ★★☆☆☆ | ★☆☆☆☆ | ★★★★☆ | Mantener |
| CP-SAT (OR-Tools) | ★★★★☆ | ★★★★★ | ★★★☆☆ | ★★★★★ | **Migrar F1-F2** |
| Greedy + warm start | ★★★☆☆ | ★★★★★ | ★★☆☆☆ | ★★★★★ | **Agregar F1** |
| ALNS | ★★★★☆ | ★★★★☆ | ★★★☆☆ | ★★★★☆ | Agregar F2 |
| Column Generation | ★★★★★ | ★★★☆☆ | ★★★★★ | ★★★☆☆ | F3 si escala |
| OR-Tools Routing | ★★★☆☆ | ★★★★☆ | ★★★☆☆ | ★★☆☆☆ | No prioritario |
| Robust Optimization | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★★☆☆☆ | F4 futuro |

***

## 5. Recomendación Concreta para TUTTI

### Estrategia Recomendada: Arquitectura Híbrida en 2 Fases

**Fase de construcción** (siempre): Greedy heurística que genera una solución inicial factible en <1 segundo. Esta solución sirve como warm start para el solver.

**Fase de optimización** (adaptativa según tamaño):
- **Instancias pequeñas** (≤50 buses, ≤300 expediciones): CP-SAT con time limit configurable. Solución óptima o near-óptima en 5-30 segundos.
- **Instancias medianas-grandes** (>50 buses o >300 expediciones): CP-SAT con time limit + ALNS como post-procesador si el gap no es satisfactorio.

**Qué mantener del sistema actual:**
- La capa de validación operativa (anti-solapamientos, capacidades)
- Los datos de entrada y el domain model
- La interfaz de salida (workspace, PDF, timeline)
- Las reglas operativas específicas de TUTTI

**Qué rediseñar:**
- El modelo de optimización: de formulación ILP big-M a CP-SAT IntervalVar + AddNoOverlap
- La arquitectura del motor: separar construcción, optimización y validación
- El sistema de objetivos: implementar modos de optimización configurables

**Qué migrar gradualmente:**
- El módulo de reporting de calidad de solución
- Los tests del optimizer (adaptar a nuevo solver)
- La lógica de warm start

**Qué no tocar todavía:**
- La capa de reconciliación de flota (independiente del solver)
- El workspace workflow
- Las exportaciones PDF

***

## 6. Diseño Propuesto del Nuevo Motor

### Pipeline General

```
INPUT (Excel/DB)
      │
      ▼
┌─────────────────┐
│  PREPROCESSOR   │  Normalización, cálculo de compatibilidades,
│                 │  precompute travel times, filtrado de candidatos
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  GREEDY BUILDER │  Construcción heurística rápida:
│                 │  asignar expediciones por ventana temporal,
│                 │  priorizar buses reales sobre virtuales
└────────┬────────┘
         │ solución inicial
         ▼
┌─────────────────┐
│  SOLVER ENGINE  │  CP-SAT (primary) o PuLP/CBC (fallback)
│  (CP-SAT)       │  con warm start desde Greedy Builder
│                 │  con time limit configurable por modo
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  VALIDATOR      │  Validación operativa post-solve:
│                 │  anti-solapamientos, capacidades,
│                 │  restricciones de flota, workspace rules
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  EXPLAINER      │  Generación de explicaciones:
│                 │  por qué cada asignación, constraints activos,
│                 │  calidad del resultado (gap, tiempo, #buses)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OUTPUT ADAPTER │  Compatibilidad con workspace, timeline,
│                 │  reconciliación, publicación, PDF
└─────────────────┘
```

### Módulo de Preprocesado

- Calcular matriz de compatibilidades bus-expedición (qué buses pueden cubrir qué expediciones)
- Precompute tiempos de posicionamiento (dead-head) entre expediciones vía OSRM
- Clustering de expediciones por ventana temporal para descomposición del problema
- Detección de conflictos obligatorios (expediciones que no pueden ir al mismo bus)

### Módulo Greedy Builder

```python
def greedy_assign(expeditions, buses, params):
    """
    Greedy: ordenar expediciones por hora de inicio,
    asignar cada una al bus disponible con menor tiempo muerto post-asignación.
    Priorizar buses reales sobre virtuales.
    """
    schedule = defaultdict(list)
    unassigned = []
    for exp in sorted(expeditions, key=lambda e: e.start_time):
        best_bus = find_best_bus(exp, buses, schedule, params)
        if best_bus:
            schedule[best_bus].append(exp)
        else:
            unassigned.append(exp)
    return schedule, unassigned
```

### Módulo Solver CP-SAT (Core)

El modelo CP-SAT propuesto para TUTTI:

```python
from ortools.sat.python import cp_model

def build_cpsat_model(expeditions, buses, params, warm_start=None):
    model = cp_model.CpModel()
    
    # Variables de asignación: assignment[b, e] = True si bus b cubre expedición e
    assignment = {}
    for b in buses:
        for e in expeditions:
            if is_compatible(b, e):  # Filtrado previo de candidatos
                assignment[b, e] = model.new_bool_var(f"assign_{b.id}_{e.id}")
    
    # Cada expedición debe asignarse a exactamente un bus
    for e in expeditions:
        model.add_exactly_one(
            [assignment[b, e] for b in buses if (b, e) in assignment]
        )
    
    # No-solapamiento por bus usando IntervalVar
    for b in buses:
        intervals = []
        for e in expeditions:
            if (b, e) in assignment:
                interval = model.new_optional_fixed_size_interval_var(
                    start=e.start_slot,
                    size=e.duration_slots,
                    is_present=assignment[b, e],
                    name=f"interval_{b.id}_{e.id}"
                )
                intervals.append(interval)
        if intervals:
            model.add_no_overlap(intervals)
    
    # Objetivo según modo (configurado por params.mode)
    objective_terms = build_objective(assignment, expeditions, buses, params)
    model.minimize(sum(objective_terms))
    
    # Warm start desde Greedy Builder
    if warm_start:
        for (b, e), val in warm_start.items():
            if (b, e) in assignment:
                model.add_hint(assignment[b, e], val)
    
    return model, assignment
```

### Módulo de Explicabilidad

```python
@dataclass
class AssignmentExplanation:
    expedition_id: str
    assigned_bus_id: str
    reason: str                    # "Único bus con ventana compatible"
    alternatives_considered: list  # Buses que se evaluaron
    why_not_alternatives: list     # Razón de exclusión de cada alternativa
    objective_contribution: float  # Cuánto contribuye al objetivo
    constraint_utilization: dict   # Qué constraints están activos
```

***

## 7. Flexibilidad de Prioridades — Modos de Optimización

### Diseño Propuesto: OptimizerConfig

```python
@dataclass
class OptimizerConfig:
    mode: str  # "min_buses" | "min_km" | "min_deadhead" | "operational_balance" | "publishable"
    time_limit_seconds: int = 30
    optimality_gap: float = 0.05  # 5% gap aceptable
    
    # Pesos (solo relevantes si mode == "custom")
    weight_num_buses: float = 0.0
    weight_total_km: float = 0.0
    weight_deadhead_km: float = 0.0
    weight_virtual_bus_usage: float = 0.0
    weight_load_imbalance: float = 0.0
    
    # Restricciones configurables
    max_virtual_buses: Optional[int] = None
    priority_fleet_companies: list = field(default_factory=list)
    min_bus_utilization_pct: float = 0.0

# Modos predefinidos
OPTIMIZER_MODES = {
    "min_buses": OptimizerConfig(
        mode="min_buses",
        weight_num_buses=1000.0,
        weight_virtual_bus_usage=500.0,
        weight_total_km=1.0,
    ),
    "min_km": OptimizerConfig(
        mode="min_km",
        weight_total_km=10.0,
        weight_deadhead_km=5.0,
        weight_num_buses=100.0,
    ),
    "min_deadhead": OptimizerConfig(
        mode="min_deadhead",
        weight_deadhead_km=100.0,
        weight_total_km=1.0,
        weight_num_buses=50.0,
    ),
    "operational_balance": OptimizerConfig(
        mode="operational_balance",
        weight_load_imbalance=50.0,
        weight_num_buses=100.0,
        weight_virtual_bus_usage=200.0,
    ),
    "publishable": OptimizerConfig(
        mode="publishable",
        weight_virtual_bus_usage=1000.0,
        weight_num_buses=200.0,
        weight_load_imbalance=10.0,
        time_limit_seconds=15,
        optimality_gap=0.10,  # Acepta 10% gap para publicar rápido
    ),
}
```

La clave del diseño es que los modos son **parámetros del motor, no cambios en el código**. El motor siempre resuelve el mismo modelo base; los pesos y restricciones adicionales cambian el comportamiento sin tocar el algoritmo.

***

## 8. Eficiencia y Rendimiento

### Pruning y Reducción de Variables

La mayor ganancia de rendimiento viene de **reducir el espacio de búsqueda antes de llamar al solver**:

1. **Filtrado de compatibilidades**: Antes de crear variables, calcular qué buses son físicamente capaces de cubrir cada expedición (capacidad, empresa, disponibilidad). Un bus con 20 plazas no puede cubrir una expedición de 25 plazas — eliminar esa variable binaria.

2. **Conflict graph pre-compute**: Dos expediciones solapadas en tiempo no pueden ir al mismo bus. Pre-calcular este grafo y usarlo para reducir variables.

3. **Clustering temporal**: Dividir el día en ventanas temporales no solapadas y resolver cada ventana por separado si la flota permite. Reduce el problema \(O(n^2)\) a múltiples problemas \(O(k \cdot (n/k)^2)\).

4. **Dominance pruning**: Si bus A puede hacer todo lo que hace bus B con menor coste, eliminar bus B como candidato para expediciones donde A está disponible.

### Warm Start Efectivo

El warm start más efectivo para CP-SAT es la heurística greedy:[^29]

```python
# Paso 1: Greedy en <1 segundo
greedy_solution = greedy_assign(expeditions, buses, params)

# Paso 2: Convertir a hints para CP-SAT
for bus, exps in greedy_solution.items():
    for exp in exps:
        model.add_hint(assignment[bus, exp], 1)

# Paso 3: CP-SAT parte de una solución ya factible y mejora desde ahí
solver.parameters.max_time_in_seconds = params.time_limit_seconds
solver.solve(model)
```

### Paralelismo Nativo de CP-SAT

CP-SAT ejecuta un portfolio de técnicas en paralelo por defecto. El speedup es mayor con 3-7 workers (después se estabiliza):[^17]

```python
solver = cp_model.CpSolver()
solver.parameters.num_workers = min(7, os.cpu_count())  # Óptimo según benchmarks
solver.parameters.max_time_in_seconds = 30
```

### Caching de Resultados

Implementar cache de compatibilidades bus-expedición y de distancias OSRM. Estas matrices no cambian entre runs del mismo workspace:

```python
@lru_cache(maxsize=None)
def get_travel_time(origin_stop_id, dest_stop_id):
    return osrm_client.route(origin_stop_id, dest_stop_id)
```

### Descomposición por Empresa/Ámbito

Si la restricción de ámbito de flota es fuerte (buses de empresa A solo cubren rutas de empresa A), el problema se descompone naturalmente en subproblemas independientes por empresa. Resolverlos en paralelo puede reducir el tiempo total en proporción al número de empresas.

***

## 9. Calidad Operativa del Resultado

### Robustez: Soluciones que Sobreviven a la Edición Manual

Una solución matemáticamente óptima pero con asignaciones "frágiles" (donde mover una sola expedición rompe toda la planificación) es operativamente mala. Para mejorar la robustez:

1. **Penalizar asignaciones con slack mínimo**: Añadir al objetivo un término que penaliza pares de expediciones en el mismo bus con muy poco tiempo entre ellas.

2. **Preferir soluciones con slack distribuido**: En el post-procesado, si hay dos soluciones con igual número de buses, preferir la que tiene mayor tiempo mínimo entre expediciones consecutivas.

3. **Soft constraints en lugar de hard constraints donde sea posible**: Convertir restricciones que podrían relajarse operativamente en penalizaciones, para que el solver no falle ante datos marginales.

### Consistencia con Planificaciones Anteriores

Una de las quejas más comunes en sistemas de optimización es que "el solver cambia completamente la solución aunque los datos apenas cambiaron". Para TUTTI:

```python
# Añadir término de similaridad al objetivo si existe un plan publicado previo
if previous_plan:
    for (b, e) in assignment:
        if previous_plan.get(e.id) != b.id:
            # Penalizar cambios respecto al plan anterior
            similarity_cost += params.weight_stability * assignment[b, e]
```

### Explicabilidad Mínima Viable

Para cada expedición asignada, el motor debe poder responder:
- "¿Por qué fue al bus X?" → Bus X era el único compatible / tenía menor tiempo muerto / tenía mayor capacidad disponible.
- "¿Por qué no fue al bus Y?" → Bus Y ya tenía solapamiento / capacidad insuficiente / era virtual y había real disponible.
- "¿Por qué se creó un bus extra?" → Ningún bus existente podía cubrir esta expedición sin solapamiento con sus asignaciones actuales.

***

## 10. Explicabilidad y Debugging del Motor

### Arquitectura de Explicabilidad

```python
@dataclass
class SolverExplanation:
    # Métricas de calidad
    objective_value: float
    optimality_gap_pct: float
    solve_time_seconds: float
    num_buses_used: int
    num_virtual_buses: int
    total_km: float
    deadhead_km: float
    
    # Asignaciones con razones
    assignments: list[AssignmentExplanation]
    
    # Constraints activos
    binding_constraints: list[str]
    
    # Diagnóstico si no se encontró solución óptima
    termination_reason: str  # "TIME_LIMIT" | "OPTIMAL" | "FEASIBLE" | "INFEASIBLE"
    
    # Sugerencias operativas
    bottleneck_buses: list[str]   # Buses con mayor carga
    slack_poor_assignments: list  # Asignaciones con <15min de margen
```

### Diagnóstico de Infeasibility

Cuando el modelo no tiene solución, el motor debe:

1. Intentar resolver la **relaxación LP** (eliminar integrality). Si es factible, la infeasibility es de integrality.
2. Si la LP también es infeasible, computar el **IIS** (Irreducible Infeasible Subsystem).[^9][^8]
3. Traducir el IIS a lenguaje operativo: "La expedición E-042 no puede ser cubierta por ningún bus disponible en la ventana 07:30-09:00 con capacidad ≥ 30 plazas."

```python
def diagnose_infeasibility(model, expeditions, buses):
    # Intentar relajación
    relaxed_model = relax_integrality(model)
    if not relaxed_model.is_feasible():
        return "LINEARLY_INFEASIBLE", identify_conflicting_constraints(relaxed_model)
    
    # Identificar expediciones sin bus viable
    uncoverable = [
        e for e in expeditions 
        if not any(is_compatible(b, e) for b in buses)
    ]
    
    return "INTEGER_INFEASIBLE", {"uncoverable_expeditions": uncoverable}
```

***

## 11. Benchmarking y Evaluación

### KPIs Primarios

| KPI | Descripción | Cómo medirlo |
|-----|-------------|--------------|
| **N° buses usados** | Total de buses en la solución (real + virtual) | Contar buses con ≥1 asignación |
| **Tasa de uso de flota** | % de capacidad total utilizada | Σ(plazas_usadas) / Σ(plazas_disponibles) |
| **KM totales** | Kilómetros recorridos en cargado + vacío | Suma de distancias OSRM |
| **KM en vacío (deadhead)** | Solo posicionamientos | KM_total - KM_en_servicio |
| **Tiempo muerto total** | Tiempo entre expediciones del mismo bus | Σ(gap_entre_expediciones) |
| **Tiempo de cómputo** | Wall time del solver | time.time() |
| **Optimality gap** | % de distancia al óptimo teórico | solver.objective_gap |
| **Infeasibility rate** | % de instancias donde no se encuentra solución | counter / total_runs |

### Datasets de Benchmark

1. **Dataset sintético pequeño**: 5-10 buses, 20-50 expediciones, sin restricciones de empresa. Solución óptima conocida manualmente.
2. **Dataset sintético mediano**: 20-50 buses, 100-200 expediciones, 2-3 empresas de flota.
3. **Dataset sintético grande**: 100+ buses, 500+ expediciones.
4. **Dataset real anonimizado**: Datos reales del cliente con datos limpiados. Comparar contra planificación manual actual.

### Criterios de Aceptación para Migrar

Antes de hacer el switch a un nuevo solver en producción:
- El nuevo motor produce soluciones iguales o mejores en el 80%+ de instancias de benchmark
- El tiempo de cómputo es ≤ el motor actual para las instancias típicas
- El 100% de las validaciones operativas (anti-solapamiento, capacidad) pasan
- Se ha probado en al menos 3 datasets reales del cliente
- El diagnóstico de infeasibility funciona correctamente

***

## 12. Roadmap de Migración

### Fase 1: Mejoras Incrementales sobre Motor Actual (Semanas 1-4)

**Sin cambiar el solver (PuLP/CBC):**

1. Implementar **greedy builder** como semilla inicial + warm start con `warmStart=True`
2. Implementar **modos de optimización** como parámetros de peso en el objetivo actual
3. Implementar **filtrado de candidatos** antes de crear variables binarias
4. Implementar **diagnóstico de infeasibility** (IIS básico)
5. Implementar **reporting de calidad**: objective value, gap, tiempo, #buses, KM
6. Añadir **time limit** configurable con solución factible como fallback

**Objetivo**: Motor actual 2-5x más rápido, más explicable, con modos configurables.

### Fase 2: Migración a CP-SAT (Semanas 5-10)

1. Reimplementar el modelo de optimización en CP-SAT con `IntervalVar + AddNoOverlap`
2. Mantener PuLP/CBC como solver de fallback (A/B testing)
3. Adaptar los tests del optimizer al nuevo modelo
4. Implementar modos de optimización en CP-SAT (weights en objetivo)
5. Benchmarking comparativo: CP-SAT vs PuLP/CBC en datasets reales
6. Si CP-SAT gana en ≥80% de casos, activar como solver principal

**Objetivo**: CP-SAT como solver principal, 5-20x más rápido, con paralelismo nativo.

### Fase 3: Motor Híbrido + ALNS (Semanas 10-20)

1. Implementar ALNS usando `N-Wouda/ALNS` como framework
2. Diseñar destroy/repair operators específicos de TUTTI
3. Integrar ALNS como post-procesador opcional cuando CP-SAT no alcanza el gap deseado
4. Implementar descomposición por empresa para instancias con multi-empresa
5. Caching de distancias OSRM con TTL

**Objetivo**: Motor competitivo para cualquier tamaño de instancia.

### Fase 4: Tuning y Robustez (Semanas 20-30)

1. Implementar constraint de similaridad con planificaciones anteriores
2. Penalizaciones de slack mínimo para robustez operativa
3. Opcional: Column Generation si instancias superan 200 buses consistentemente
4. Análisis de robustez estadística con múltiples runs
5. Documentación matemática completa del modelo

***

## 13. Riesgos y Tradeoffs

### Riesgo: Seguir con el Enfoque Actual sin Mejoras

- El motor ILP/CBC se vuelve un cuello de botella a medida que los datasets crecen
- Cada nueva regla operativa que se quiere añadir requiere reformulación cuidadosa
- Sin modos de optimización, el producto no puede ofrecer flexibilidad a los operadores
- Sin diagnóstico de infeasibility, los errores en datos de entrada producen fallos opacos

### Riesgo: Migrar a CP-SAT sin Gradualidad

- El modelo CP-SAT no es un drop-in replacement — requiere reimplementación del modelo de constraints
- Si la migración introduce bugs en los constraints, se generarán asignaciones inválidas silenciosamente
- **Mitigación**: Mantener PuLP/CBC como fallback y validar resultados con el validador operativo en paralelo

### Riesgo: Sobrediseñar (Column Generation prematuro)

- Column Generation tiene un overhead de implementación muy alto
- Para instancias típicas de TUTTI (≤100 buses), CP-SAT será más que suficiente
- **Mitigación**: No implementar CG hasta que CP-SAT no sea suficiente para las instancias reales

### Riesgo: Demasiada Flexibilidad de Configuración

- Demasiados modos y parámetros confunden al usuario y al agente de desarrollo
- Un modo "custom" con 10 pesos configurables es difícil de calibrar
- **Mitigación**: Exponer solo 5 modos predefinidos con nombres operativos. Ocultar los pesos internos como constantes del código, no como configuración de usuario.

### Riesgo: ALNS sin Operadores Bien Diseñados

- ALNS con operadores mal diseñados produce soluciones peores que greedy
- Los destroy/repair operators de TUTTI son específicos del dominio y requieren conocimiento de las restricciones
- **Mitigación**: Implementar y testear cada operador individualmente con instancias sintéticas antes de integrarlos en el framework ALNS

***

## 14. Relación con Skills de Agentes de IA

| Skill | Contenido para el Motor Mejorado |
|-------|----------------------------------|
| `tutti-optimizer-dev` | Actualizar con: nueva arquitectura CP-SAT, modelo de IntervalVar, modos de optimización, warm start. **Esta skill es la más crítica** y debe documentar el mapeo expedition→IntervalVar, el significado de cada peso de objetivo y la API de OptimizerConfig |
| `tutti-optimizer-benchmarking` (nueva) | Skill dedicada a: cómo ejecutar benchmarks, qué datasets usar, cómo interpretar los KPIs, cómo comparar el motor nuevo vs el actual. Previene que un agente haga cambios sin medir el impacto |
| `tutti-optimizer-debug` (nueva) | Skill dedicada a: diagnóstico de infeasibility, interpretación del gap de optimalidad, debugging del modelo CP-SAT, uso de `check_feasibility.py`. Es distinta de `tutti-debug-troubleshoot` porque requiere conocimiento del modelo matemático |
| `tutti-routing-maps` | Actualizar con: cómo se precomputan las matrices de distancia OSRM para el optimizer, cómo se cachean, qué pasa cuando OSRM falla |
| `tutti-fleet-operations` | Actualizar con: cómo la reconciliación de flota interactúa con los modos de optimización, qué datos de disponibilidad necesita el optimizer |

***

## 15. Salida Implementable para Otro Agente

### Arquitectura Propuesta del Motor

```
backend/optimizer/
├── __init__.py
├── config.py              # OptimizerConfig, OPTIMIZER_MODES
├── preprocessor.py        # Filtrado de candidatos, compatibilidades, clustering
├── greedy_builder.py      # Heurística constructiva para semilla inicial
├── solver_cpsat.py        # Motor principal CP-SAT (NUEVA)
├── solver_pulp.py         # Motor actual ILP/PuLP (refactorizado, como fallback)
├── solver_interface.py    # Interfaz común para ambos solvers
├── objective_builder.py   # Construcción del objetivo según modo
├── validator.py           # Validación operativa post-solve (existente, mantener)
├── explainer.py           # Generación de explicaciones (NUEVA)
├── infeasibility.py       # Diagnóstico de infeasibility (NUEVA)
├── benchmarker.py         # Ejecución de benchmarks comparativos (NUEVA)
└── models.py              # AssignmentExplanation, SolverResult, SolverExplanation
```

### Backlog Priorizado

```
SPRINT 1 — Mejoras sin Cambiar Solver (Semana 1-2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Implementar OptimizerConfig con modos predefinidos en config.py
[ ] Implementar greedy_builder.py con warm start a CBC
[ ] Implementar filtrado de candidatos en preprocessor.py
[ ] Implementar reporting básico de calidad (gap, tiempo, #buses, KM)
[ ] Implementar diagnóstico básico de infeasibility en infeasibility.py
[ ] Agregar time limit configurable al solver actual

SPRINT 2 — Solver CP-SAT (Semana 3-5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Implementar solver_cpsat.py con IntervalVar + AddNoOverlap
[ ] Implementar solver_interface.py (SolverInterface abstracto)
[ ] Adaptar objective_builder.py para CP-SAT
[ ] Adaptar tests del optimizer a la nueva interfaz
[ ] Benchmarking CP-SAT vs PuLP/CBC en datasets sintéticos

SPRINT 3 — Explicabilidad y Modos (Semana 5-7)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Implementar explainer.py con AssignmentExplanation
[ ] Implementar los 5 modos de optimización
[ ] Exponer modos en endpoint de la API de TUTTI
[ ] Integrar explicaciones en el output del workspace

SPRINT 4 — ALNS y Robustez (Semana 8-12)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] Integrar N-Wouda/ALNS como dependencia
[ ] Implementar destroy operator: "liberar expediciones de ventana temporal"
[ ] Implementar repair operator: "greedy insertion con prioridad de flota real"
[ ] Implementar constraint de similaridad con plan anterior
[ ] Implementar penalización de slack mínimo
```

### Pseudocódigo de Alto Nivel del Nuevo Motor

```python
class TUTTIOptimizer:
    def __init__(self, config: OptimizerConfig):
        self.config = config
        self.solver = CPSATSolver(config) if config.use_cpsat else PuLPSolver(config)
    
    def optimize(self, expeditions, buses, previous_plan=None) -> SolverResult:
        # 1. Preprocesar
        candidates = self.preprocessor.filter_candidates(expeditions, buses)
        
        # 2. Construir solución inicial
        greedy_sol = self.greedy_builder.build(expeditions, buses, self.config)
        
        # 3. Resolver con solver principal
        result = self.solver.solve(
            expeditions=expeditions,
            buses=buses,
            candidates=candidates,
            warm_start=greedy_sol,
            previous_plan=previous_plan,
            config=self.config
        )
        
        # 4. Si no alcanza gap deseado y hay tiempo, usar ALNS
        if result.gap > self.config.optimality_gap and self.config.use_alns:
            result = self.alns.improve(result, self.config)
        
        # 5. Validar operativamente
        violations = self.validator.validate(result)
        if violations:
            result.warnings.extend(violations)
        
        # 6. Generar explicaciones
        result.explanation = self.explainer.explain(result, expeditions, buses)
        
        return result
```

### Plan de Benchmarks

```python
BENCHMARK_SCENARIOS = [
    # (nombre, n_buses, n_expediciones, n_empresas, descripcion)
    ("tiny", 5, 20, 1, "Instancia mínima para smoke tests"),
    ("small", 15, 60, 1, "Instancia típica cliente pequeño"),
    ("medium", 40, 150, 2, "Instancia típica cliente mediano"),
    ("large", 80, 300, 3, "Instancia cliente grande"),
    ("stress", 150, 600, 5, "Stress test para límites del solver"),
    ("real_client_1", None, None, None, "Dataset real anonimizado cliente 1"),
]

BENCHMARK_METRICS = [
    "num_buses_used", "total_km", "deadhead_km", 
    "solve_time_s", "optimality_gap_pct",
    "infeasibility_rate", "load_balance_score"
]

def run_benchmark(scenario, old_solver, new_solver):
    data = generate_or_load(scenario)
    old_result = old_solver.optimize(data)
    new_result = new_solver.optimize(data)
    return compare_results(old_result, new_result, BENCHMARK_METRICS)
```

### Criterios de Migración

El motor nuevo reemplaza al actual cuando:
- `new.num_buses_used ≤ old.num_buses_used` en ≥80% de scenarios
- `new.solve_time_s ≤ old.solve_time_s * 2` en 100% de scenarios (nunca más lento del doble)
- `new.infeasibility_rate == 0` para todos los scenarios válidos
- Tests de integración completos (100% pass rate)
- Revisión manual de 3 datasets reales del cliente por el equipo

### Riesgos de Implementación

1. **Mapeo de restricciones**: Al migrar a CP-SAT, cada constraint del modelo PuLP debe ser verificado individualmente. Riesgo de omitir una restricción operativa.
2. **Cambio de escala del objetivo**: CP-SAT usa enteros internamente; los objetivos continuos (KM, tiempo) deben escalarse a enteros (p.ej., multiplicar por 100 y truncar).
3. **Compatibilidad de warm starts**: Los hints en CP-SAT funcionan de manera diferente a los warm starts en CBC; probar que el greedy builder realmente acelera CP-SAT.
4. **Testing del explainer**: Las explicaciones generadas deben ser validadas por un operador real del negocio, no solo por el equipo técnico.

***

## Recommended Strategy

**Arquitectura Híbrida de 3 Capas**: Greedy Builder → CP-SAT Solver (OR-Tools) → ALNS post-procesador opcional.

Migrar el solver de PuLP/CBC a OR-Tools CP-SAT con `IntervalVar + AddNoOverlap` como reformulación del modelo, añadiendo modos de optimización configurables y una capa de explicabilidad estructurada.

## Why This Wins

1. **CP-SAT tiene soporte nativo para el constraint de no-solapamiento** (`add_no_overlap`), que es el constraint central de TUTTI. Esto elimina la necesidad de big-M formulations y mejora dramáticamente la LP relaxation.[^19][^22]

2. **CP-SAT corre en paralelo por defecto** sin configuración adicional, usando todos los cores disponibles con un portfolio de técnicas.[^17]

3. **Soluciones de calidad en 1-10 segundos** para instancias típicas de TUTTI, vs. minutos en PuLP/CBC para instancias medianas.[^23][^17]

4. **El greedy warm start es directamente compatible** con CP-SAT via `add_hint()`, dando al solver una solución factible desde el inicio.

5. **La migración es gradual y reversible**: Ambos solvers pueden coexistir detrás de una interfaz común, con A/B testing en producción.

## What To Change First

1. Implementar `OptimizerConfig` con los 5 modos predefinidos (sin cambiar solver)
2. Implementar `greedy_builder.py` con warm start a CBC (sin cambiar solver)
3. Implementar `solver_interface.py` como abstracción
4. Implementar `solver_cpsat.py` como nueva implementación
5. Benchmarking comparativo A/B

## What To Keep

- Toda la capa de validación operativa (anti-solapamientos, capacidades)
- El domain model y las entidades de TUTTI
- La interfaz de salida (workspace, timeline, PDF, reconciliación)
- Los endpoints de API que llaman al optimizer
- Los datos de entrada y el parser de Excel

## Migration Plan

| Fase | Duración | Cambios | Reversible |
|------|----------|---------|------------|
| F1: Mejoras ILP | 2 semanas | Config, greedy, reporting | Sí |
| F2: CP-SAT paralelo | 3 semanas | Nuevo solver, A/B testing | Sí |
| F3: CP-SAT principal | 2 semanas | Switch en producción, PuLP como fallback | Sí (rollback) |
| F4: ALNS + robustez | 6 semanas | Post-procesador opcional | Sí |

## Benchmark Plan

1. Crear datasets sintéticos: tiny (5B/20E), small (15B/60E), medium (40B/150E), large (80B/300E)
2. Ejecutar ambos solvers en cada dataset con las mismas restricciones
3. Comparar KPIs: #buses, KM total, KM vacío, tiempo de cómputo, gap
4. Criterio de migración: nuevo motor igual o mejor en 80%+ de casos
5. Validación final: 3 datasets reales del cliente revisados por el equipo

## Implementation Handoff

### Archivos a Crear

```
backend/optimizer/config.py          # OptimizerConfig, OPTIMIZER_MODES
backend/optimizer/greedy_builder.py  # Heurística constructiva
backend/optimizer/solver_interface.py # Interfaz abstracta
backend/optimizer/solver_cpsat.py    # Nuevo solver CP-SAT
backend/optimizer/objective_builder.py # Construcción del objetivo
backend/optimizer/explainer.py       # Explicaciones de asignación
backend/optimizer/infeasibility.py   # Diagnóstico de infeasibility
backend/optimizer/benchmarker.py     # Framework de benchmarking
tests/optimizer/test_cpsat_solver.py # Tests del nuevo solver
tests/optimizer/test_benchmark.py    # Benchmarks comparativos
.claude/skills/tutti-optimizer-dev/SKILL.md  # Actualizar con nueva arquitectura
.claude/skills/tutti-optimizer-benchmarking/SKILL.md  # Nueva skill
.claude/skills/tutti-optimizer-debug/SKILL.md  # Nueva skill
```

### Archivos a Modificar

```
backend/optimizer/model.py           # Refactorizar para usar solver_interface
backend/optimizer/solver.py          # Convertir a solver_pulp.py (fallback)
tests/optimizer/test_optimizer.py    # Adaptar a nueva interfaz
requirements.txt                     # Agregar: ortools>=9.8, alns>=0.3
```

### Archivos a NO Tocar en esta Fase

```
backend/fleet/*                      # Reconciliación de flota: independiente
backend/workspace/*                  # Workflow: independiente
backend/pdf/*                        # Exportaciones: independiente
backend/parsers/*                    # Ingesta Excel: independiente
frontend/*                           # Todo el frontend
```

***

## Machine-Friendly Summary

```yaml
optimizer_evolution:
  
  recommended_strategy:
    name: "Hybrid Greedy + CP-SAT + ALNS"
    description: >
      Three-layer architecture: fast greedy construction as warm start,
      CP-SAT as primary solver (OR-Tools IntervalVar + AddNoOverlap),
      ALNS as optional post-processor for large instances or tight gaps.
  
  primary_solver:
    name: "OR-Tools CP-SAT"
    library: "ortools>=9.8"
    python_api: "ortools.sat.python.cp_model"
    key_constraints: ["add_no_overlap", "new_optional_fixed_size_interval_var", "add_exactly_one"]
    parallelism: "native (portfolio of techniques, 7 workers optimal)"
    warm_start: "model.add_hint(var, value)"
    expected_solve_time_small: "< 5s"
    expected_solve_time_medium: "5-30s"
    expected_solve_time_large: "30-120s with gap"
  
  secondary_solver:
    name: "PuLP/CBC (fallback)"
    role: "Fallback for very small instances, regression testing, compatibility"
    status: "Keep as solver_pulp.py behind common interface"
  
  tertiary_technique:
    name: "ALNS (Adaptive Large Neighborhood Search)"
    library: "alns>=0.3 (N-Wouda/ALNS)"
    role: "Post-processor for large instances or when CP-SAT gap > threshold"
    destroy_operators: ["temporal_window_destroy", "company_fleet_destroy", "random_destroy"]
    repair_operators: ["greedy_insertion", "regret_insertion"]
    activation: "optional, when gap > config.optimality_gap after CP-SAT time_limit"
  
  construction_heuristic:
    name: "Greedy Builder"
    role: "Feasible solution in <1s for CP-SAT warm start"
    strategy: "Sort expeditions by start_time, assign to bus with minimum dead_head gap"
    priority: "Real buses over virtual buses"
  
  problem_classification:
    formal_type: "Multi-Depot Vehicle Scheduling Problem (MDVSP)"
    sub_type: "Heterogeneous fleet, multi-objective, operational robustness constraints"
    np_hard: true
    typical_instance_size: "20-100 buses, 50-500 expeditions"
  
  optimization_modes:
    - name: "min_buses"
      weights: {num_buses: 1000, virtual_bus: 500, total_km: 1}
    - name: "min_km"
      weights: {total_km: 10, deadhead_km: 5, num_buses: 100}
    - name: "min_deadhead"
      weights: {deadhead_km: 100, total_km: 1, num_buses: 50}
    - name: "operational_balance"
      weights: {load_imbalance: 50, num_buses: 100, virtual_bus: 200}
    - name: "publishable"
      weights: {virtual_bus: 1000, num_buses: 200, load_imbalance: 10}
      time_limit_seconds: 15
      optimality_gap: 0.10
  
  hard_constraints:
    - "Every expedition assigned to exactly one bus"
    - "No two expeditions overlap in time for the same bus"
    - "Bus capacity >= expedition required seats"
    - "Operational time windows respected"
  
  soft_constraints:
    - "Minimize virtual bus usage (configurable weight)"
    - "Minimize dead-head (repositioning) time"
    - "Balance load across buses of same company"
    - "Minimize changes vs previous published plan (stability)"
    - "Penalize assignments with < minimum_slack_minutes between expeditions"
  
  migration_roadmap:
    phase_1:
      name: "Incremental ILP improvements"
      duration: "2 weeks"
      deliverables: ["OptimizerConfig", "greedy_builder", "infeasibility_diagnosis", "quality_reporting"]
    phase_2:
      name: "CP-SAT migration (A/B)"
      duration: "3 weeks"
      deliverables: ["solver_cpsat.py", "solver_interface.py", "A/B benchmarking"]
    phase_3:
      name: "CP-SAT as primary + ALNS"
      duration: "6 weeks"
      deliverables: ["ALNS post-processor", "similarity constraint", "slack penalty"]
    phase_4:
      name: "Tuning and consolidation"
      duration: "4 weeks"
      deliverables: ["full benchmark suite", "documentation", "math model doc"]
  
  suggested_agent_skills:
    - name: "tutti-optimizer-dev"
      status: "update"
      priority: "critical"
      add_content: "CP-SAT model, IntervalVar mapping, OptimizerConfig API, mode descriptions"
    - name: "tutti-optimizer-benchmarking"
      status: "create"
      priority: "important"
      description: "How to run, interpret and compare optimizer benchmarks"
    - name: "tutti-optimizer-debug"
      status: "create"
      priority: "important"
      description: "ILP/CP-SAT infeasibility diagnosis, gap analysis, debugging tools"
  
  key_risks:
    - risk: "Constraint omission during CP-SAT migration"
      severity: "high"
      mitigation: "Validate CP-SAT output through existing operational validator in parallel"
    - risk: "Integer scaling for CP-SAT objective"
      severity: "medium"
      mitigation: "Scale km/time values by 100x to integers before passing to CP-SAT"
    - risk: "Warm start ineffective in CP-SAT"
      severity: "medium"
      mitigation: "Benchmark greedy warm start vs cold start; keep cold start as fallback"
    - risk: "ALNS operators poorly designed"
      severity: "medium"
      mitigation: "Test each operator independently on synthetic instances first"
    - risk: "Over-engineering (CG premature)"
      severity: "low"
      mitigation: "Do not implement Column Generation until CP-SAT is insufficient for real instances"
  
  new_dependencies:
    - "ortools>=9.8"
    - "alns>=0.3"
  
  files_to_create:
    - "backend/optimizer/config.py"
    - "backend/optimizer/greedy_builder.py"
    - "backend/optimizer/solver_interface.py"
    - "backend/optimizer/solver_cpsat.py"
    - "backend/optimizer/objective_builder.py"
    - "backend/optimizer/explainer.py"
    - "backend/optimizer/infeasibility.py"
    - "backend/optimizer/benchmarker.py"
    - "tests/optimizer/test_cpsat_solver.py"
    - "tests/optimizer/test_benchmark.py"
  
  files_to_modify:
    - "backend/optimizer/model.py"
    - "backend/optimizer/solver.py -> solver_pulp.py"
    - "requirements.txt"
    - ".claude/skills/tutti-optimizer-dev/SKILL.md"
  
  files_do_not_touch:
    - "backend/fleet/*"
    - "backend/workspace/*"
    - "backend/pdf/*"
    - "backend/parsers/*"
    - "frontend/*"
```

---

## References

1. [A Column Generation Approach to the Multiple-Depot Vehicle Scheduling Problem | Operations Research](https://pubsonline.informs.org/doi/10.1287/opre.42.1.41) - We give a new formulation to the multiple-depot vehicle scheduling problem as a set partitioning pro...

2. [A Column Generation Algorithm for Vehicle Scheduling ...](https://arxiv.org/pdf/1806.00831.pdf) - por TI Faiz · 2018 · Mencionado por 74 — In this paper, we consider a variant of a truckload open ve...

3. [Dynamic Aggregation of Set-Partitioning Constraints in Column Generation | Operations Research](https://pubsonline.informs.org/doi/10.1287/opre.1050.0222) - Column generation is often used to solve problems involving set-partitioning constraints, such as ve...

4. [Set partitioning/covering-based approaches for the ...](https://www.sciencedirect.com/science/article/abs/pii/S0305054806002139) - por M Mesquita · 2008 · Mencionado por 132 — In the integrated vehicle and crew scheduling problem (...

5. [An Empirical performances comparison of meta-heuristic algorithms for school bus](https://su-plus.strathmore.edu/server/api/core/bitstreams/c6aa33c3-a78c-4e01-bba1-f548a7afe04b/content)

6. [Metaheuristic Approaches for Solving School Bus Routing ...](https://www.theijes.com/papers/vol13-issue8/13081522.pdf) - In this comparative study, we aim to evaluate and compare the performance of various optimization al...

7. [An Empirical performances comparison of meta-heuristic ...](https://su-plus.strathmore.edu/bitstream/11071/11866/1/An%20Empirical%20performances%20comparison%20of%20meta-heuristic%20algorithms%20for%20school%20bus%20routing%20problem.pdf) - por S Semba · 2017 · Mencionado por 8 — This work presents a model of the School Bus Routing Problem...

8. [How do I determine why my model is infeasible? - Gurobi Supportsupport.gurobi.com › en-us › articles › 360029969391-How-do-I-determi...](https://support.gurobi.com/hc/en-us/articles/360029969391-How-do-I-determine-why-my-model-is-infeasible) - When solving optimization models, certain scenarios may arise where the defined constraints cannot b...

9. [Analyzing infeasible optimization models](http://www.sce.carleton.ca/faculty/chinneck/docs/InfeasibilityTutorial.pdf)

10. [Python PuLP Optimization - How to improve performance?](https://stackoverflow.com/questions/73054902/python-pulp-optimization-how-to-improve-performance) - Assuming the model is constructed properly, here are a couple things to try: Solve for 1 week at a t...

11. [Multi-objective LP with PuLP in Python - SCDA](https://www.supplychaindataanalytics.com/multi-objective-linear-optimization-with-pulp-in-python/) - In this post I want to provide a coding example in Python, using the PuLP module for solving a multi...

12. [Modeling Multiple Depot Vehicle Scheduling Problem in ...](https://stackoverflow.com/questions/72205163/modeling-multiple-depot-vehicle-scheduling-problem-in-or-tools) - The objective is to minimize the sum of all dead-head trip costs while ensuring each trip is served ...

13. [Warm-start (MIP start) behavior in CBC via PuLP #746](https://github.com/coin-or/Cbc/discussions/746) - The goal is to reuse a previously found feasible solution as a warm start, to speed up subsequent ru...

14. [Exploring Multi-Objective MILP Techniques in Gurobi](https://support.gurobi.com/hc/en-us/community/posts/29636982766353-Exploring-Multi-Objective-MILP-Techniques-in-Gurobi) - Gurobi provides an API to solve multi-objective optimization problems using three main approaches: 1...

15. [Epsilon constraint optimization in Python - SCDA](https://www.supplychaindataanalytics.com/augmented-epsilon-constraint-method-multi-goal-optimization-with-pulp-in-python/) - In this post, I describe the popular augmented epsilon constraint (ε ε -constraint or eps-constraint...

16. [Generation of efficient solutions in Multiobjective ...](https://www.gams.com/modlib/adddocs/epscm.pdf) - por G Mavrotas · Mencionado por 161 — On the other hand, with the ε-constraint we can exploit almost...

17. [Well, that escalated quickly: OR-Tools](https://www.solvermax.com/blog/well-that-escalated-quickly-or-tools) - The performance of the OR-Tools CP-SAT solver is remarkable. Each of the solutions is found within 1...

18. [No overlapping Scheduling using CP-SAT in OR-Tools](https://stackoverflow.com/questions/78256773/no-overlapping-scheduling-using-cp-sat-in-or-tools) - You need 1 overlap per resource (teacher, room, group of students). Then you collect all intervals f...

19. [Using and Understanding Google OR-Tools' CP-SAT Solver](https://d-krupke.github.io/cpsat-primer/04B_advanced_modelling.html) - The add_no_overlap constraints takes a list of (optional) interval variables and ensures that no two...

20. [ortools.sat.python.cp_model API documentation](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html)

21. [The CP-SAT Primer: Using and Understanding Google OR ...](https://github.com/d-krupke/cpsat-primer) - The relatively new CP-SAT of Google's OR-Tools suite shows to overcome many of the weaknesses and pr...

22. [[PDF] CP-SAT for scheduling](https://schedulingseminar.com/presentations/SchedulingSeminar_LaurentPerron.pdf)

23. [Google's OR-Tools and CP-SAT versus Commercial Solvers ...](https://connect.informs.org/discussion/googles-or-tools-and-cp-sat-versus-commercial-solvers-esp-gurobi) - Does anyone have real-world experience solving MIPs with Google's CP-SAT and Gurobi? Any idea when o...

24. [Vehicle Routing Problem with Time Windows | OR-Tools](https://developers.google.com/optimization/routing/vrptw)

25. [A column generation approach for the driver scheduling ...](https://orbit.dtu.dk/files/209346457/Technical_Report.pdf) - por SSGR Perumal · 2020 · Mencionado por 6 — In most applications, the master problem of the column ...

26. [Large Neighborhood Search with Constraint Programming for ...](https://hanalog.ca/wp-content/uploads/2017/11/Hossein_Paper_1_rev_3.pdf) - por H Hojabri · Mencionado por 98 — Abstract. This paper considers an extension of the vehicle routi...

27. [N-Wouda/ALNS: Adaptive large neighbourhood search ...](https://github.com/N-Wouda/ALNS) - alns is a general, well-documented and tested implementation of the adaptive large neighbourhood sea...

28. [Adaptive Large Neighborhood Search (ALNS)](https://www.emergentmind.com/topics/adaptive-large-neighborhood-search-alns-algorithm) - ALNS has become a standard in the field of metaheuristics, particularly for challenging vehicle rout...

29. [Heuristics as warm start for Mixed Integer Programming ...](https://towardsdatascience.com/heuristics-as-warm-start-for-mixed-integer-programming-mip-models-9046781dd21f/) - Heuristics are techniques used to find a feasible solution to a given problem, typically faster than...

30. [Models and Algorithms for Stochastic and Robust Vehicle ...](https://pubsonline.informs.org/doi/10.1287/trsc.2014.0581) - por Y Adulyasak · 2016 · Mencionado por 156 — We consider the vehicle routing problem with deadlines...

31. [[PDF] The robust vehicle routing problem with time windows](https://optimization-online.org/wp-content/uploads/2018/02/6477.pdf)


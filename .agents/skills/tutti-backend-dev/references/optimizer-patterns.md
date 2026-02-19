# Patrones de Optimizacion V6

## Estructura del Optimizador

```python
def optimize_v6(routes: List[Route]) -> List[BusSchedule]:
    # 1. Preprocessing
    blocks = prepare_jobs(routes)  # {1: [RouteJob...], 2: [...], ...}
    
    # 2. Travel time matrix
    travel_matrices = {}
    for block_num, jobs in blocks.items():
        travel_matrices[block_num] = precompute_block_travel_matrix(jobs, is_entry)
    
    # 3. Intra-block chains (ILP)
    all_chains = {}
    for block_num, jobs in blocks.items():
        chains = build_chains_ilp(jobs, travel_matrices[block_num], is_entry)
        all_chains[block_num] = chains
    
    # 4. Cross-block matching
    buses = match_cross_block_chains(all_chains, blocks, cross_travel)
    
    # 5. Build schedule
    return build_full_schedule(buses, blocks)
```

## RouteJob Dataclass

```python
@dataclass
class RouteJob:
    route: Route
    route_type: str           # "entry" or "exit"
    block: int                # 1-4
    school_name: str
    school_loc: Tuple[float, float]
    first_stop: Tuple[float, float]
    last_stop: Tuple[float, float]
    duration_minutes: int
    time_minutes: int         # arrival for entries, departure for exits
    start_loc: Tuple[float, float]
    end_loc: Tuple[float, float]
    scheduled_start_min: int
    scheduled_end_min: int
```

## ILP Model

Variables:
- `x[i][j]`: 1 si j sigue a i en la misma cadena
- `y[i]`: 1 si i empieza una nueva cadena
- `a[i]` / `d[i]`: Tiempo continuo de llegada/salida

Funcion objetivo:
```python
prob = pulp.LpProblem("MinChains", pulp.LpMinimize)

# Minimizar numero de cadenas (buses)
primary = pulp.lpSum(y[i] for i in range(n))

# Penalizar links debiles (ML)
secondary = pulp.lpSum(
    (1.0 - pair_scores.get((i,j), 0.5)) * x[(i, j)]
    for (i, j) in x
)

prob += 10000.0 * primary + secondary
```

Restricciones:
```python
# Cada ruta tiene a lo sumo un predecesor
for j in range(n):
    preds = [x[(i, j)] for i in range(n) if (i, j) in x]
    if preds:
        prob += pulp.lpSum(preds) <= 1
        prob += y[j] >= 1 - pulp.lpSum(preds)  # y=1 si no tiene pred

# Cada ruta tiene a lo sumo un sucesor
for i in range(n):
    succs = [x[(i, j)] for j in range(n) if (i, j) in x]
    if succs:
        prob += pulp.lpSum(succs) <= 1

# Enlaces temporales (para entradas)
for (i, j) in feasible:
    tt = travel_times.get((i, j), 999)
    needed = tt + jobs[j].duration_minutes
    # a[j] >= a[i] + needed - BIG_M * (1 - x[i][j])
    prob += a[j] >= a[i] + needed - BIG_M * (1 - x[(i, j)])
```

## Estrategias de Chain Building

El greedy usa 7 estrategias de ordenamiento:
1. earliest_first: Por tiempo
2. latest_first: Tiempo descendente
3. most_connected: Mayor conectividad primero
4. least_connected: Menor conectividad primero (difíciles primero)
5. by_school: Agrupar por colegio
6. by_duration: Más largas primero
7. by_geography: Posición espacial

## Cross-Block Matching

Empareja cadenas de bloque N con bloque N+1:
- Bloque 1 (entry AM) ↔ Bloque 2 (exit PM temprano)
- Bloque 3 (entry PM) ↔ Bloque 4 (exit PM tarde)

Puntuacion de emparejamiento:
```python
score = base_score + school_bonus + capacity_bonus - capacity_penalty

Donde:
- school_bonus: +12 si mismo colegio
- capacity_bonus: +4 si capacidades similares
- capacity_penalty: -8 si diferencia > 20 asientos
```

## Local Search

Operadores implementados:
1. **Relocate**: Mover ruta de bus A a bus B
2. **Swap**: Intercambiar rutas entre buses
3. **2-Opt**: Invertir segmento de ruta
4. **Cross-exchange**: Intercambiar sub-cadenas

Criterio de aceptacion:
- Aceptar si reduce numero de buses
- Aceptar si reduce tiempo muerto total
- Simulated annealing para escapar optimos locales

"""
Optimizer V4 - VERSIÓN FINAL CORRECTA

REGLAS CORRECTAS:
1. 4 entradas a COLEGIOS DIFERENTES (nunca mismo colegio)
2. Early arrival: -30, -20, -10, 0 min
3. Verificar tiempo de viaje entre colegio A y primera parada de B
4. Tarde: asignar salidas a los buses de mañana

ESTRATEGIA:
1. Ordenar colegios por posición geográfica (clustering espacial)
2. Para cada colegio, encontrar 3 colegios vecinos cercanos
3. Verificar si hay tiempo de viaje entre ellos con early arrival
4. Si sí, crear bus con esas 4 rutas
"""
import math
from typing import List, Tuple, Dict, Optional
from datetime import time
from dataclasses import dataclass

from models import Route, BusSchedule, ScheduleItem
from optimizer_v2 import to_minutes, from_minutes

# Constantes
NOON: int = 12 * 60
EARLY: List[int] = [30, 20, 10, 0]  # minutos antes de hora escuela
KM_PER_MINUTE: float = 1.33  # 80 km/h = 1.33 km/min (velocidad optimista entre colegios)
BUFFER: int = 5   # minutos buffer reducido


@dataclass
class School:
    """Representa un colegio con sus rutas."""
    name: str
    location: Tuple[float, float]  # lat, lon
    arrival_time: time  # hora de llegada típica
    routes: List[Route]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en km entre dos puntos."""
    if lat1 == 0 or lat2 == 0:
        return 999.0
    R = 6371.0
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def travel_time_minutes(km: float) -> int:
    """Tiempo de viaje en minutos para una distancia."""
    return max(5, int(km / KM_PER_MINUTE) + BUFFER)


def estimate_route_duration(route: Route) -> int:
    """Duración estimada de ruta basada en distancia."""
    if not route.stops or len(route.stops) < 2:
        return 25
    
    total_km = 0.0
    for i in range(len(route.stops) - 1):
        total_km += haversine_km(
            route.stops[i].lat, route.stops[i].lon,
            route.stops[i + 1].lat, route.stops[i + 1].lon
        )
    
    return max(15, int(total_km / KM_PER_MINUTE) + len(route.stops) * 2)


def get_school_location(route: Route) -> Tuple[float, float]:
    """Última parada (colegio) para entry."""
    if route.stops:
        return (route.stops[-1].lat, route.stops[-1].lon)
    return (0.0, 0.0)


def get_first_stop(route: Route) -> Tuple[float, float]:
    """Primera parada de la ruta."""
    if route.stops:
        return (route.stops[0].lat, route.stops[0].lon)
    return (0.0, 0.0)


def can_chain_4_schools(schools: List[School]) -> bool:
    """
    Verifica si se puede hacer una cadena de 4 colegios con early arrival.
    Ordena por proximidad geográfica, no por hora.
    """
    if len(schools) != 4:
        return False
    
    # Ordenar por proximidad: empezar con el más al norte y seguir cercanos
    # Estrategia greedy: empezar por uno, luego el más cercano no visitado
    remaining = list(schools)
    sorted_schools = [remaining.pop(0)]  # Empezar con el primero
    
    while remaining:
        last = sorted_schools[-1]
        # Encontrar el más cercano
        closest = min(remaining, key=lambda s: haversine_km(
            last.location[0], last.location[1],
            s.location[0], s.location[1]
        ))
        sorted_schools.append(closest)
        remaining.remove(closest)
    
    last_end_time = 0  # Cuándo termina la ruta anterior
    
    for i, school in enumerate(sorted_schools):
        # Tomar primera ruta del colegio
        route = school.routes[0]
        
        arrival_school = to_minutes(school.arrival_time)
        early = EARLY[i]
        effective_arrival = arrival_school - early
        duration = estimate_route_duration(route)
        start_time = effective_arrival - duration
        
        if i == 0:
            # Primera ruta, siempre OK
            last_end_time = effective_arrival
        else:
            # Calcular tiempo de viaje desde colegio anterior
            prev_school = sorted_schools[i - 1]
            prev_loc = prev_school.location
            curr_first = get_first_stop(route)
            
            km = haversine_km(prev_loc[0], prev_loc[1], curr_first[0], curr_first[1])
            travel = travel_time_minutes(km)
            
            # ¿Llegamos a tiempo para empezar esta ruta?
            arrival_at_start = last_end_time + travel
            
            if arrival_at_start > start_time + 5:  # 5 min flex
                return False
            
            last_end_time = effective_arrival
    
    return True


def group_entries_by_school(entries: List[Route]) -> Dict[str, School]:
    """Agrupa rutas por colegio."""
    schools: Dict[str, School] = {}
    
    for route in entries:
        name = route.school_name
        if name not in schools:
            loc = get_school_location(route)
            schools[name] = School(
                name=name,
                location=loc,
                arrival_time=route.arrival_time or time(8, 0),
                routes=[]
            )
        schools[name].routes.append(route)
    
    return schools


def find_best_chain(seed_school: School, all_schools: List[School]) -> Optional[List[School]]:
    """
    Encuentra la mejor cadena de 4 colegios empezando por seed_school.
    Busca los 3 colegios más cercanos que permitan una cadena válida.
    """
    # Calcular distancias a otros colegios (solo los que tienen rutas disponibles)
    distances: List[Tuple[float, School]] = []
    for other in all_schools:
        if other.name == seed_school.name or not other.routes:
            continue
        km = haversine_km(
            seed_school.location[0], seed_school.location[1],
            other.location[0], other.location[1]
        )
        distances.append((km, other))
    
    # Ordenar por distancia
    distances.sort(key=lambda x: x[0])
    
    # Probar combinaciones de 3 colegios cercanos
    candidates = [d[1] for d in distances[:15]]  # Top 15 más cercanos
    
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            for k in range(j + 1, len(candidates)):
                chain = [seed_school, candidates[i], candidates[j], candidates[k]]
                if can_chain_4_schools(chain):
                    return chain
    
    return None


def build_morning_buses(schools_dict: Dict[str, School]) -> Tuple[List[BusSchedule], List[Route]]:
    """Construye buses de mañana con 4 entradas a colegios diferentes."""
    all_schools = list(schools_dict.values())
    used_schools: set[str] = set()
    buses: List[BusSchedule] = []
    
    # Ordenar colegios por número de rutas (descendente)
    sorted_schools = sorted(all_schools, key=lambda s: len(s.routes), reverse=True)
    
    for seed in sorted_schools:
        if seed.name in used_schools:
            continue
        
        # Intentar encontrar cadena de 4 colegios
        chain = find_best_chain(seed, all_schools)
        
        if chain:
            # Crear bus con una ruta de cada colegio
            routes_for_bus = [s.routes[0] for s in chain]
            
            bus = create_bus_with_4_routes(routes_for_bus, f"B{len(buses) + 1:03d}")
            buses.append(bus)
            
            # Marcar colegios como usados (y rutas específicas)
            for school in chain:
                used_schools.add(school.name)
                # Eliminar la ruta usada
                if school.routes:
                    school.routes.pop(0)
    
    # Recolectar rutas no usadas
    orphaned: List[Route] = []
    for school in all_schools:
        if school.routes:
            orphaned.extend(school.routes)
    
    return buses, orphaned


def create_bus_with_4_routes(routes: List[Route], bus_id: str) -> BusSchedule:
    """Crea bus con 4 entradas."""
    items: List[ScheduleItem] = []
    
    # Ordenar por hora
    sorted_routes = sorted(routes, key=lambda r: to_minutes(r.arrival_time) if r.arrival_time else 0)
    
    for i, route in enumerate(sorted_routes):
        arrival = to_minutes(route.arrival_time if route.arrival_time is not None else time(8, 0))
        early = EARLY[i]
        effective = arrival - early
        duration = estimate_route_duration(route)
        start = effective - duration
        
        items.append(ScheduleItem(
            route_id=route.id,
            start_time=from_minutes(start),
            end_time=from_minutes(effective),
            type="entry",
            school_name=route.school_name,
            stops=route.stops,
            contract_id=route.contract_id,
            original_start_time=route.arrival_time,
            time_shift_minutes=early,
            deadhead_minutes=0
        ))
    
    return BusSchedule(bus_id=bus_id, items=items)


def create_bus_with_1_route(route: Route, bus_id: str) -> BusSchedule:
    """Crea bus con 1 entrada."""
    arrival = to_minutes(route.arrival_time) if route.arrival_time else 8 * 60
    duration = estimate_route_duration(route)
    
    items = [ScheduleItem(
        route_id=route.id,
        start_time=from_minutes(arrival - duration),
        end_time=from_minutes(arrival),
        type="entry",
        school_name=route.school_name,
        stops=route.stops,
        contract_id=route.contract_id,
        original_start_time=route.arrival_time,
        time_shift_minutes=0,
        deadhead_minutes=0
    )]
    
    return BusSchedule(bus_id=bus_id, items=items)


def assign_afternoon_exits(buses: List[BusSchedule], exits: List[Route]) -> List[BusSchedule]:
    """Asigna salidas a buses de mañana."""
    if not exits:
        return buses
    
    # Ordenar por hora
    sorted_exits = sorted(exits, key=lambda r: to_minutes(r.departure_time) if r.departure_time else 16 * 60)
    
    for exit_route in sorted_exits:
        duration = estimate_route_duration(exit_route)
        departure = to_minutes(exit_route.departure_time) if exit_route.departure_time else 16 * 60
        
        item = ScheduleItem(
            route_id=exit_route.id,
            start_time=from_minutes(departure),
            end_time=from_minutes(departure + duration),
            type="exit",
            school_name=exit_route.school_name,
            stops=exit_route.stops,
            contract_id=exit_route.contract_id,
            original_start_time=exit_route.departure_time,
            time_shift_minutes=0,
            deadhead_minutes=0
        )
        
        # Buscar bus con tiempo disponible
        added = False
        for bus in buses:
            if not bus.items:
                continue
            
            # Contar salidas actuales
            current_exits = sum(1 for i in bus.items if i.type == "exit")
            if current_exits >= 5:  # Máximo 5 salidas por bus
                continue
            
            # Verificar tiempo
            last_item = bus.items[-1]
            last_end = to_minutes(last_item.end_time)
            
            # Viaje desde última ubicación
            if last_item.type == "entry":
                last_loc = (last_item.stops[-1].lat, last_item.stops[-1].lon) if last_item.stops else (0.0, 0.0)
            else:
                last_loc = (last_item.stops[0].lat, last_item.stops[0].lon) if last_item.stops else (0.0, 0.0)
            
            exit_start = get_first_stop(exit_route)
            
            km = haversine_km(last_loc[0], last_loc[1], exit_start[0], exit_start[1])
            travel = travel_time_minutes(km)
            
            if last_end + travel <= departure + 5:
                bus.items.append(item)
                added = True
                break
        
        if not added:
            bus_id = f"B{len(buses) + 1:03d}"
            buses.append(BusSchedule(bus_id=bus_id, items=[item]))
    
    return buses


def optimize_v4(routes: List[Route]) -> List[BusSchedule]:
    """Optimización principal."""
    print("\n" + "=" * 60)
    print("OPTIMIZADOR V4 - VERSIÓN FINAL")
    print("=" * 60)
    
    # Separar
    morning_entries = [r for r in routes if r.type == "entry" and r.arrival_time and to_minutes(r.arrival_time) < NOON]
    afternoon_exits = [r for r in routes if r.type == "exit" and r.departure_time and to_minutes(r.departure_time) >= NOON - 60]
    
    print(f"\nEntradas mañana: {len(morning_entries)}")
    print(f"Salidas tarde: {len(afternoon_exits)}")
    
    # Agrupar por colegio
    schools_dict = group_entries_by_school(morning_entries)
    print(f"Colegios únicos: {len(schools_dict)}")
    
    # FASE 1: Crear buses de 4 entradas
    print("\nFASE 1: Buscando cadenas de 4 colegios cercanos...")
    buses, orphaned = build_morning_buses(schools_dict)
    
    print(f"  Buses con 4 entradas: {len(buses)}")
    print(f"  Rutas huérfanas: {len(orphaned)}")
    
    # Buses para huérfanas
    for route in orphaned:
        bus_id = f"B{len(buses) + 1:03d}"
        buses.append(create_bus_with_1_route(route, bus_id))
    
    # FASE 2: Asignar salidas
    print(f"\nFASE 2: Asignando salidas a buses de mañana...")
    buses = assign_afternoon_exits(buses, afternoon_exits)
    
    # Renumerar
    for i, bus in enumerate(buses):
        bus.bus_id = f"B{i + 1:03d}"
    
    # Stats
    with_4 = sum(1 for b in buses if sum(1 for i in b.items if i.type == "entry") == 4)
    with_7 = sum(1 for b in buses if len(b.items) >= 7)
    
    print(f"\n=== RESULTADOS ===")
    print(f"Total buses: {len(buses)}")
    print(f"Buses con 4 entradas: {with_4}")
    print(f"Buses con 7+ rutas: {with_7}")
    
    return buses


# Compatibilidad
def optimize_routes_v4(routes: List[Route]) -> List[BusSchedule]:
    return optimize_v4(routes)


__all__ = ['optimize_v4', 'optimize_routes_v4']

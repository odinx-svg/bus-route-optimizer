# Domain Map

## Core entities

### Stop
- Archivo principal: `backend/models.py`
- Campos clave: `name`, `lat`, `lon`, `order`, `time_from_start`, `passengers`, `is_school`
- Uso operativo:
  - parser construye rutas desde stops
  - optimizer usa coordenadas y demanda
  - PDF y mapas consumen nombre y coordenadas

### Route
- Archivo principal: `backend/models.py`
- Representa un servicio escolar en un sentido:
  - `type="entry"`: llega al centro
  - `type="exit"`: sale del centro
- Horario oficial:
  - `arrival_time` para `entry`
  - `departure_time` para `exit`
- Demanda:
  - `capacity_needed`
  - `vehicle_capacity_min/max/range`

### ScheduleItem
- Archivo principal: `backend/models.py`
- Es una ruta ya asignada a un bus y a un horario final.
- Une dominio + optimizer:
  - `route_id`
  - `start_time`, `end_time`
  - `time_shift_minutes`
  - `deadhead_minutes`, `positioning_minutes`
  - `stops`, `school_name`, `contract_id`

### BusSchedule
- Archivo principal: `backend/models.py`
- Es el plan diario de un bus.
- Puede llevar binding operativo de flota:
  - `assigned_vehicle_id`
  - `assigned_vehicle_code`
  - `fleet_binding_state`
  - `fleet_assignment_type`

## Domain boundaries

- Parser transforma Excel en `Route[]`.
- Optimizer transforma `Route[]` en `BusSchedule[]`.
- Fleet publication y reconciliation enriquecen el schedule con vehiculo real/virtual.
- PDF y frontend consumen schedules serializados.

## Important note

En este repo no hay una entidad core unica llamada `Expedition` en el modelo principal. Si aparece en documentos o conversacion, normalmente se refiere a una instancia operativa de servicio ya reflejada como `Route` o `ScheduleItem`. Antes de introducir una nueva abstraccion, comprobar si solo hace falta documentar mejor la existente.


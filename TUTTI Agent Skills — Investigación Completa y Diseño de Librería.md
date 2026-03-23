# TUTTI Agent Skills — Investigación Completa y Diseño de Librería

> Documento de referencia para diseño, implementación y evolución del sistema de skills de agentes de IA para el proyecto TUTTI. Orientado a ser entregado directamente a un agente de código para implementar los archivos `SKILL.md` en el repositorio.

***

## 1. Resumen Ejecutivo

TUTTI es un sistema de optimización y gestión operativa de rutas de autobuses escolares con un grado de complejidad técnica y de dominio muy superior a una CRUD convencional. Combina ingesta de datos sucios desde Excel, modelado de dominio de transporte escolar, optimización combinatoria con programación lineal entera (PuLP/ILP), reconciliación de flota, publicación de planificaciones operativas, generación de PDFs, visualización geoespacial y un flujo de trabajo con estados versionados (draft/publish/archive). Este nivel de complejidad por capas —dominio de transporte, matemática de optimización, integración de mapas, exportaciones operativas y una UI orientada a operadores— hace que un agente de IA trabajando sin guía especializada sea altamente propenso a cometer errores costosos: romper constraints del optimizador, generar PDFs con rutas incorrectas, alterar estados de workspace incorrectamente, o degradar el rendimiento del solver ILP.[^1][^2]

Un sistema de skills bien diseñado para TUTTI actúa como un equipo de especialistas virtuales persistentes: cada skill encapsula el conocimiento del dominio, las convenciones del proyecto, las rutas críticas de riesgo y los workflows correctos para una parte específica del sistema. En lugar de depender de que el agente "descubra" las convenciones del proyecto en cada sesión, las skills las entregan de forma estructurada y bajo demanda, reduciendo el contexto necesario, aumentando la consistencia y protegiendo las partes más sensibles del sistema.[^3][^4][^5]

***

## 2. Lectura del Producto

### Qué problema resuelve TUTTI

TUTTI transforma el proceso manual y error-prone de planificación de transporte escolar —basado en hojas Excel con rutas, paradas, horarios y expediciones— en una plataforma digital con optimización automática de asignación de flota, validación operativa, publicación de planificaciones y exportación de documentos operativos. El usuario objetivo es un operador o planificador de transporte escolar que trabaja bajo restricciones reales: número limitado de buses, ventanas horarias estrictas, paradas con capacidades y estudiantes con necesidades específicas.

### Partes Core del Sistema

| Módulo | Descripción | Riesgo |
|--------|-------------|--------|
| **Excel Ingestion** | Parser de archivos sucios; fuente de todos los datos | Alto — datos reales son inconsistentes |
| **Domain Model** | Rutas, paradas, buses, horarios, expediciones | Crítico — error aquí se propaga a todo el sistema |
| **Optimizer (PuLP/ILP)** | Asignación de buses a expediciones con constraints | Muy alto — lógica matemática frágil y difícil de debuggear |
| **Overlap Validator** | Detecta conflictos de horarios y asignaciones | Crítico — fallo silencioso destruye la planificación |
| **Fleet Reconciliation** | Flota real vs virtual, commit operativo | Alto — estado persistido, difícil de revertir |
| **Workspace States** | Draft/publish/archive — flujo de trabajo | Alto — cambios de estado incorrectos tienen consecuencias operativas |
| **PDF Export** | ReportLab + Google Maps links | Medio — outputs finales del cliente |

### Partes Operativas

- Frontend: mapa Leaflet, timeline editable, vistas operativas, panel de flota
- CRUD DB-first para flota
- Publicación operativa con commit de flota
- Reconciliación por día

### Partes Sensibles o de Alto Riesgo

1. **Optimizador**: cambiar constraints puede hacer el modelo infeasible sin mensajes claros. Un agente sin guía puede "simplificar" constraints e introducir bugs silenciosos.[^6]
2. **Workspace workflow**: las transiciones de estado (draft → publish → archive) tienen efectos sobre la flota real. Un agente que no entiende este flujo puede publicar datos incompletos.
3. **Excel parser**: manejar datos sucios requiere lógica defensiva específica. Un agente puede "limpiar" código de validación pensando que es redundante.
4. **Fleet reconciliation**: estado derivado de múltiples fuentes; el orden de operaciones importa.

### Partes que Crecerán Más

- Capa de conductores (driver management, plan semanal por vehículo)
- Mensajería automática
- CI/CD y empaquetado EXE para Windows
- Escalabilidad del optimizador para instancias grandes
- Observabilidad y logging

***

## 3. Mapa Completo de Skills Necesarias

A continuación se identifican todas las skills relevantes para TUTTI, priorizadas por impacto y riesgo:

| # | Skill Name | Categoría | Prioridad | Estado |
|---|-----------|-----------|-----------|--------|
| 1 | `tutti-architecture` | Meta / Proyecto | 🔴 Crítica | Crear |
| 2 | `tutti-domain-model` | Dominio | 🔴 Crítica | Crear |
| 3 | `tutti-excel-ingestion` | Datos | 🔴 Crítica | Crear |
| 4 | `tutti-optimizer-dev` | Core | 🔴 Crítica | Crear |
| 5 | `tutti-backend-dev` | Infraestructura | 🔴 Crítica | Crear |
| 6 | `tutti-workspace-workflow` | Operativa | 🟠 Importante | Crear |
| 7 | `tutti-fleet-operations` | Operativa | 🟠 Importante | Crear |
| 8 | `tutti-frontend-dev` | UI | 🟠 Importante | Crear |
| 9 | `tutti-testing` | Calidad | 🟠 Importante | Crear |
| 10 | `tutti-pdf-exports` | Output | 🟠 Importante | Crear |
| 11 | `tutti-routing-maps` | Geoespacial | 🟡 Conveniente | Crear |
| 12 | `tutti-debug-troubleshoot` | DevEx | 🟡 Conveniente | Crear |
| 13 | `tutti-build-deploy` | DevOps | 🟡 Conveniente | Crear |
| 14 | `tutti-drivers-messaging` | Futuro | ⚪ Futuro | Reservar |

***

## 4. Clasificación por Categorías

### 4.1 Categoría: Meta / Arquitectura del Proyecto
- `tutti-architecture`: Conocimiento transversal del sistema completo. La skill que todo agente debe conocer antes de trabajar en cualquier módulo.

### 4.2 Categoría: Dominio de Transporte Escolar
- `tutti-domain-model`: Entidades de negocio (rutas, expediciones, paradas, buses, horarios), sus relaciones, restricciones y semántica operativa.
- `tutti-workspace-workflow`: Estados del workspace (draft/publish/archive), transiciones válidas, efectos sobre la flota y planificación.

### 4.3 Categoría: Datos e Ingesta
- `tutti-excel-ingestion`: Parser de Excel, normalización, validación de datos sucios, convenciones de columnas esperadas.

### 4.4 Categoría: Optimización
- `tutti-optimizer-dev`: Modelo PuLP/ILP, variables de decisión, constraints críticos, análisis de feasibility, tuning de rendimiento.

### 4.5 Categoría: Backend
- `tutti-backend-dev`: Patrones FastAPI, capas de servicio, repositorios, modelos SQLAlchemy/Pydantic, endpoints, autenticación.

### 4.6 Categoría: Frontend
- `tutti-frontend-dev`: Componentes React/Vite, gestión de estado, integración con backend, Leaflet, timeline editable.

### 4.7 Categoría: Operaciones de Flota
- `tutti-fleet-operations`: Flota real vs virtual, reconciliación diaria, commit operativo, CRUD de buses.

### 4.8 Categoría: Outputs
- `tutti-pdf-exports`: ReportLab, templates de PDF operativo, Google Maps deep links, formatos de exportación.
- `tutti-routing-maps`: Integración OSRM, Leaflet, cálculo de rutas, visualización de timelines.

### 4.9 Categoría: Calidad y DevEx
- `tutti-testing`: Pytest, estrategia de tests por capa, fixtures de dominio, tests del optimizador.
- `tutti-debug-troubleshoot`: Logging, observabilidad, debugging del ILP, herramientas de diagnóstico.
- `tutti-build-deploy`: Empaquetado Windows, scripts de arranque, EXE, CI/CD.

### 4.10 Categoría: Futuro
- `tutti-drivers-messaging`: Capa de conductores, plan semanal por vehículo, mensajería automática.

***

## 5. Análisis Detallado Skill por Skill

***

### 5.1 `tutti-architecture`

**Prioridad:** 🔴 Crítica ahora

**Objetivo:** Ser la skill de orientación general del proyecto. Toda sesión de trabajo en TUTTI debería comenzar con esta skill activa o referenciada. Encapsula la estructura de carpetas, stack tecnológico, convenciones de nomenclatura, principios arquitectónicos, dependencias críticas entre módulos y el mapa mental del sistema completo.

**Problema del proyecto que resuelve:** Sin esta skill, un agente nuevo comenzará explorando el repositorio desde cero, con alta probabilidad de malinterpretar la arquitectura separada backend/frontend, confundir rutas con expediciones, o ignorar restricciones de módulos críticos.

**Alcance:**
- Mapa de carpetas y módulos del proyecto
- Stack y versiones mínimas
- Principios arquitectónicos (separación backend/frontend, DB-first, validaciones)
- Convenciones de nomenclatura (rutas, expediciones, paradas, buses)
- Dependencias críticas entre módulos
- Qué NO tocar sin revisar otras skills (optimizer, workspace states)

**Cuándo activarla:** Al inicio de cualquier sesión de trabajo en TUTTI. También cuando se está explorando el codebase por primera vez o planificando cambios que afectan múltiples módulos.

**Cuándo NO activarla:** No es necesaria para tareas muy específicas ya iniciadas (p.ej., "corrige este test específico").

**Contexto mínimo necesario:**
- Estructura de carpetas del repositorio
- `README.md` del proyecto
- Stack file (`requirements.txt`, `package.json`)

**Archivos o módulos que debería leer primero:**
- `README.md`
- `backend/` (estructura de carpetas)
- `frontend/` (estructura de carpetas)
- `docs/architecture.md` (si existe, sino generarlo)

**Tareas típicas:**
- Orientación inicial de un agente nuevo
- Planning de cambios cross-módulo
- Revisión de impacto antes de refactoring

**Errores frecuentes que ayuda a evitar:**
- Confundir `Route` con `Expedition` (conceptos distintos del dominio)
- Mezclar lógica de negocio en endpoints de FastAPI
- Asumir que SQLite y PostgreSQL son intercambiables sin ajustes
- Tocar el optimizer sin entender el domain model

**Relación con otras skills:** Es prerequisito conceptual de todas las demás skills. Debería referenciarlas explícitamente con señales de cuándo derivar.

**Ejemplo de prompt de activación:**
> "Voy a trabajar en el módulo de reconciliación de flota de TUTTI. Dame un mapa del sistema y dime qué módulos debo revisar antes de tocar código."

***

### 5.2 `tutti-domain-model`

**Prioridad:** 🔴 Crítica ahora

**Objetivo:** Definir con precisión las entidades del dominio de transporte escolar en TUTTI: `Route`, `Expedition`, `Stop`, `Bus`, `Schedule`, `WorkspaceState`, `FleetAssignment`. Incluye sus relaciones, invariantes de negocio, semántica operativa y las restricciones que deben cumplirse en todo momento.

**Problema del proyecto que resuelve:** El dominio de transporte escolar tiene terminología específica que no es obvia. Un agente puede confundir "ruta" (secuencia de paradas) con "expedición" (ejecución concreta de una ruta en un horario), o asumir que una parada tiene una sola ruta asociada. Estos errores se propagan silenciosamente a la BD, el optimizer y los PDFs.

**Alcance:**
- Definición semántica de cada entidad de dominio
- Relaciones entre entidades (diagrama ER en ASCII)
- Invariantes y restricciones de negocio (un bus no puede estar en dos expediciones solapadas, etc.)
- Reglas de validación por entidad
- Glosario del dominio

**Cuándo activarla:** Al crear o modificar modelos de datos, escribir endpoints que manipulan entidades de dominio, diseñar migraciones de BD, trabajar en el optimizer.

**Cuándo NO activarla:** Para tareas puramente técnicas sin impacto en el dominio (cambiar un campo de UI, actualizar una dependencia).

**Archivos que debería leer primero:**
- `backend/models/` (todos los modelos SQLAlchemy/Pydantic)
- `backend/schemas/`
- `backend/migrations/` (alembic o equivalente)
- `references/DOMAIN.md` (si existe)

**Tareas típicas:**
- Diseñar una nueva entidad o relación
- Auditar si un cambio en un modelo respeta los invariantes
- Responder "¿qué significa X en el contexto de TUTTI?"
- Diseñar queries que involucran múltiples entidades

**Errores frecuentes que ayuda a evitar:**
- Modelar `Expedition` como sinónimo de `Route`
- Eliminar campos de validación por considerarlos redundantes
- Ignorar el invariante de no-solapamiento al modificar asignaciones
- Confundir estados operativos con estados de UI

**Relación con otras skills:** Base de `tutti-optimizer-dev`, `tutti-fleet-operations`, `tutti-workspace-workflow`, `tutti-backend-dev`. Sin este contexto, ninguna de las demás puede operar correctamente.

**Ejemplo de prompt:**
> "Necesito agregar soporte para expediciones de retorno (vuelta al colegio). ¿Cómo debería modelarse en el domain model de TUTTI sin romper las validaciones existentes?"

***

### 5.3 `tutti-excel-ingestion`

**Prioridad:** 🔴 Crítica ahora

**Objetivo:** Guiar al agente en el trabajo con el parser de Excel de TUTTI: cómo leer, normalizar y validar archivos Excel con datos de rutas y expediciones. Incluye patrones de manejo de datos sucios, convenciones de columnas esperadas, errores comunes de los archivos de entrada y estrategias de resiliencia.

**Problema del proyecto que resuelve:** Los archivos Excel de entrada provienen de operadores reales y contienen datos inconsistentes: celdas fusionadas, columnas sin header, filas vacías, valores con espacios extra, formatos de hora inconsistentes. Un agente sin guía puede "simplificar" el parser eliminando lógica defensiva que parece redundante pero que maneja casos reales.

**Alcance:**
- Formato esperado de los archivos Excel de entrada
- Estrategia de parsing (pandas, openpyxl, o librería actual)
- Patrones de normalización de datos
- Validaciones pre-carga y post-carga
- Manejo de errores y mensajes de usuario
- Tests para datos sucios

**Cuándo activarla:** Al modificar el parser de Excel, agregar soporte para nuevos formatos, debuggear errores de ingesta, escribir tests de ingesta.

**Cuándo NO activarla:** Para trabajo en módulos que no involucran datos de entrada de Excel.

**Archivos que debería leer primero:**
- `backend/parsers/` o `backend/ingestion/`
- `backend/validators/`
- `tests/test_excel_parser.py`
- Archivos Excel de muestra en `fixtures/` o `samples/`

**Tareas típicas:**
- Agregar soporte para una nueva columna o formato de entrada
- Debuggear por qué ciertos archivos Excel fallan en la ingesta
- Mejorar mensajes de error para el usuario
- Escribir tests con datos sucios representativos

**Errores frecuentes que ayuda a evitar:**
- Eliminar validaciones defensivas por considerarlas "innecesarias"
- Asumir que los tipos de datos Excel son consistentes
- No cubrir el caso de filas vacías o encabezados duplicados
- Hardcodear nombres de columnas sin constantes

**Relación con otras skills:** `tutti-domain-model` (qué entidades se crean desde Excel), `tutti-testing` (cómo testear con fixtures de Excel).

**Ejemplo de prompt:**
> "El parser falla con un archivo Excel que tiene las columnas de hora en formato texto '07:30' en lugar de número. ¿Cómo debería manejarse esto de forma robusta?"

***

### 5.4 `tutti-optimizer-dev`

**Prioridad:** 🔴 Crítica ahora

**Objetivo:** Ser la guía especializada para trabajar con el optimizador de asignación de buses de TUTTI (PuLP/ILP). Encapsula el modelo matemático, las variables de decisión, los constraints obligatorios, las métricas de calidad de solución, patrones de debugging de modelos infeasibles y estrategias de mejora de rendimiento.

**Problema del proyecto que resuelve:** El optimizador es el corazón funcional de TUTTI y el módulo más frágil: un constraint mal formulado puede hacer el modelo infeasible sin mensaje claro, una variable de decisión mal definida puede producir asignaciones inválidas, y cambios aparentemente inocentes pueden degradar el tiempo de solución de segundos a horas. Un agente sin guía especializada no tiene forma de razonar correctamente sobre estos problemas.[^7][^6]

**Alcance:**
- Estructura del modelo PuLP (variables, objetivo, constraints)
- Semántica de cada constraint (qué regla operativa representa)
- Cómo interpretar un modelo infeasible
- Cómo agregar nuevos constraints sin romper los existentes
- Patrones de rendimiento: gap de optimalidad, tiempo límite, solver selection
- Cómo testear el optimizer con instancias conocidas
- Cuándo usar relaxaciones

**Cuándo activarla:** Al modificar el optimizador, agregar nuevas restricciones, debuggear resultados incorrectos del optimizer, mejorar rendimiento del solver.

**Cuándo NO activarla:** Para trabajo en otros módulos. Esta skill tiene allowed-tools restringidos para evitar cambios accidentales en constraints críticos.

**Archivos que debería leer primero:**
- `backend/optimizer/` (módulo completo)
- `backend/optimizer/model.py` o equivalente
- `tests/test_optimizer.py`
- `references/OPTIMIZER.md` (documentación del modelo matemático)

**Tareas típicas:**
- Agregar constraint de capacidad máxima por bus
- Debuggear por qué el optimizador asigna buses incorrectamente
- Mejorar tiempo de solución para instancias grandes
- Generar informe de calidad de solución (gap, tiempo, #variables)

**Errores frecuentes que ayuda a evitar:**
- Eliminar un constraint sin entender a qué regla operativa corresponde
- Agregar constraints contradictorios (modelo infeasible silencioso)
- Ignorar el gap de optimalidad y asumir que la solución es óptima
- Cambiar el sentido del objetivo (min vs max) accidentalmente
- No validar la solución contra el domain model después de resolver

**Relación con otras skills:** Requiere `tutti-domain-model` (comprensión de entidades), se apoya en `tutti-testing` (tests de validación del optimizer), puede necesitar `tutti-debug-troubleshoot`.

**Ejemplo de prompt:**
> "El optimizador V6 está tardando 45 segundos para una instancia de 20 buses y 80 expediciones. Quiero entender dónde está el cuello de botella y qué ajustes puedo hacer al modelo sin cambiar las restricciones operativas."

***

### 5.5 `tutti-backend-dev`

**Prioridad:** 🔴 Crítica ahora

**Objetivo:** Guiar el desarrollo del backend FastAPI de TUTTI: convenciones de endpoints, capas de servicio, repositorios, schemas Pydantic, modelos SQLAlchemy, gestión de errores, autenticación y patrones de organización del código.

**Problema del proyecto que resuelve:** Sin guía, un agente puede mezclar lógica de negocio en endpoints, duplicar queries en lugar de usar la capa de repositorios, usar sync donde se espera async, o crear endpoints que no respetan las convenciones de respuesta del proyecto.[^8][^9]

**Alcance:**
- Estructura de directorios del backend (domain-driven)
- Convenciones FastAPI: routers, dependencias, middleware
- Patrón de capas: endpoint → service → repository → ORM
- Pydantic schemas (request/response) vs ORM models
- Gestión de errores y HTTP status codes
- Patrones de testing de endpoints (TestClient)
- Migraciones con Alembic (si se usa)

**Cuándo activarla:** Al crear o modificar endpoints, servicios, repositorios, modelos de BD, schemas.

**Archivos que debería leer primero:**
- `backend/api/` (routers)
- `backend/services/`
- `backend/repositories/`
- `backend/models/`
- `backend/schemas/`
- `backend/config.py` o `.env`

**Tareas típicas:**
- Crear un nuevo endpoint CRUD para una entidad
- Refactorizar lógica de negocio de un endpoint a un servicio
- Agregar validación a un schema Pydantic
- Escribir test de integración para un endpoint

**Errores frecuentes que ayuda a evitar:**
- Lógica de negocio directamente en routers FastAPI
- N+1 queries en endpoints que retornan listas
- Mezclar modelos ORM con schemas Pydantic en respuestas
- No manejar errores de DB con rollback adecuado

**Relación con otras skills:** Depende de `tutti-domain-model`, coordina con `tutti-testing`, referencia `tutti-optimizer-dev` para endpoints del optimizer.

**Ejemplo de prompt:**
> "Necesito un endpoint que dado un workspace_id retorne las expediciones del día con su asignación de flota actual, respetando las capas del backend de TUTTI."

***

### 5.6 `tutti-workspace-workflow`

**Prioridad:** 🟠 Importante (siguiente fase)

**Objetivo:** Documentar y guiar el flujo de estados del workspace de TUTTI: cómo funcionan las transiciones draft → publish → archive, qué efectos tienen sobre la flota y planificación, qué validaciones deben pasar antes de cada transición, y cómo se relacionan con la reconciliación.

**Problema del proyecto que resuelve:** El workspace workflow es un estado con efectos reales: publicar un workspace confirma asignaciones de flota. Un agente sin guía puede implementar una transición de estado sin las validaciones requeridas, o revertir un estado sin entender las consecuencias operativas.

**Alcance:**
- Diagrama de estados del workspace
- Pre-condiciones de cada transición
- Efectos secundarios (qué cambia en la BD y en la flota)
- Cómo testear transiciones de estado
- Cómo manejar errores en transiciones (rollback)

**Cuándo activarla:** Al trabajar en el módulo de workspace, estados de planificación, publicación o archivado.

**Archivos que debería leer primero:**
- `backend/services/workspace_service.py`
- `backend/models/workspace.py`
- `tests/test_workspace_workflow.py`

**Errores frecuentes que ayuda a evitar:**
- Permitir la publicación sin validar anti-solapamientos
- No hacer rollback de asignaciones de flota si la publicación falla
- Confundir estado de UI con estado operativo del workspace

***

### 5.7 `tutti-fleet-operations`

**Prioridad:** 🟠 Importante

**Objetivo:** Guiar el trabajo con el módulo de flota de TUTTI: gestión de buses reales vs virtuales, reconciliación diaria, commit operativo, estados derivados de asignación.

**Problema del proyecto que resuelve:** La reconciliación de flota involucra múltiples fuentes de verdad (plan optimizado vs flota real disponible). Un error en este módulo puede producir planificaciones con buses inexistentes o conflictos de asignación no detectados.

**Alcance:**
- Modelo de flota: buses reales vs virtuales
- Flujo de reconciliación: qué datos se comparan, qué se resuelve
- Commit operativo: qué se persiste y cuándo
- CRUD de buses y validaciones
- Estados derivados de asignación

**Cuándo activarla:** Al trabajar en módulos de flota, reconciliación, asignación de buses.

**Archivos que debería leer primero:**
- `backend/fleet/`
- `backend/services/fleet_service.py`
- `backend/models/fleet.py`

***

### 5.8 `tutti-frontend-dev`

**Prioridad:** 🟠 Importante

**Objetivo:** Guiar el desarrollo del frontend React/Vite de TUTTI: estructura de componentes, gestión de estado, integración con backend, Leaflet para mapas, timeline editable y patrones de UI operativa.

**Problema del proyecto que resuelve:** Sin guía, un agente puede romper el estado del mapa al modificar el timeline, usar fetch directamente en componentes en lugar del patrón de servicios, o crear componentes no reutilizables.

**Alcance:**
- Estructura de componentes y organización de carpetas frontend
- Gestión de estado (Context, hooks, o librería de estado)
- Integración con backend: patrones de fetch, error handling
- Leaflet: capas, marcadores, polilíneas de rutas
- Timeline editable: estructura y eventos
- Convenciones de estilos y nomenclatura

**Cuándo activarla:** Al trabajar en cualquier componente React, vista, mapa o timeline.

**Archivos que debería leer primero:**
- `frontend/src/components/`
- `frontend/src/hooks/`
- `frontend/src/services/`
- `frontend/src/views/` o `pages/`

***

### 5.9 `tutti-testing`

**Prioridad:** 🟠 Importante

**Objetivo:** Establecer la estrategia de testing de TUTTI: qué testear por capa, cómo organizar los tests, fixtures de dominio, cómo testear el optimizer, cómo mockear dependencias externas (OSRM, Excel).

**Problema del proyecto que resuelve:** TUTTI tiene complejidad de dominio alta y partes matemáticamente sensibles (optimizer). Sin una estrategia clara, los tests tienden a ser superficiales o a testear solo el happy path, dejando expuestas las rutas de error más críticas.

**Alcance:**
- Pytest: organización, fixtures, conftest
- Tests por capa: unitarios (dominio, servicios), integración (endpoints), E2E
- Fixtures de domain objects (buses, rutas, expediciones)
- Estrategia de tests del optimizer (instancias conocidas con solución verificada)
- Mocking de OSRM y dependencias externas
- Coverage mínimo por módulo

**Cuándo activarla:** Al escribir cualquier test, al agregar cobertura a módulos existentes, al diseñar una estrategia de testing.

**Archivos que debería leer primero:**
- `tests/` (estructura completa)
- `tests/conftest.py`
- `tests/fixtures/`

**Errores frecuentes que ayuda a evitar:**
- Tests que dependen del orden de ejecución
- Tests del optimizer sin instancias con solución conocida
- No mockear servicios externos (OSRM) en tests unitarios

***

### 5.10 `tutti-pdf-exports`

**Prioridad:** 🟠 Importante

**Objetivo:** Guiar la generación de PDFs operativos en TUTTI con ReportLab: estructura del documento, templates, integración de Google Maps deep links, formatos de exportación.

**Alcance:**
- Estructura del PDF operativo (secciones, tablas, estilos)
- Templates de ReportLab para diferentes tipos de exportación
- Generación de Google Maps deep links desde coordenadas
- Manejo de casos borde: rutas largas, muchas paradas, texto largo

**Cuándo activarla:** Al trabajar en el módulo de exportación PDF.

**Archivos que debería leer primero:**
- `backend/pdf/` o `backend/exports/`
- `backend/pdf/templates/`

***

### 5.11 `tutti-routing-maps`

**Prioridad:** 🟡 Conveniente

**Objetivo:** Guiar la integración con OSRM y Leaflet: cómo se calculan las rutas, cómo se visualizan en el mapa, cómo se integran los datos de tiempo y distancia con el optimizador.

**Alcance:**
- API de OSRM: endpoints usados, formato de respuesta
- Leaflet: capas, marcadores, polilíneas, popups
- Integración OSRM → Optimizer (datos de distancia/tiempo)
- Manejo de casos donde OSRM no devuelve ruta

**Cuándo activarla:** Al trabajar con mapas, rutas geoespaciales, integración OSRM.

***

### 5.12 `tutti-debug-troubleshoot`

**Prioridad:** 🟡 Conveniente

**Objetivo:** Proveer herramientas y estrategias de debugging para TUTTI: logging estructurado, diagnóstico del optimizer ILP, debugging de errores de ingesta, herramientas de observabilidad.

**Alcance:**
- Convenciones de logging en FastAPI
- Debugging del modelo ILP (variables, constraints activos)
- Diagnóstico de errores de ingesta de Excel
- Herramientas de profiling para el optimizer
- Patrones de debugging del frontend

***

### 5.13 `tutti-build-deploy`

**Prioridad:** 🟡 Conveniente

**Objetivo:** Guiar el empaquetado y deployment de TUTTI en Windows: scripts de arranque, posible EXE con PyInstaller, CI/CD básico.

**Alcance:**
- Scripts de arranque (start backend, start frontend)
- Empaquetado EXE (PyInstaller u otras herramientas)
- Variables de entorno y configuración por entorno
- CI/CD básico (GitHub Actions u otro)
- Checklist de release

**disable-model-invocation:** `true` — esta skill debe activarse solo manualmente para evitar deployments accidentales.

***

### 5.14 `tutti-drivers-messaging` (Futuro)

**Prioridad:** ⚪ Fase futura

**Objetivo:** Diseñar e implementar la capa de conductores de TUTTI: asignación de conductores a vehículos, plan semanal por conductor, notificaciones automáticas.

**Estado:** Reservar carpeta y SKILL.md con esqueleto. No implementar hasta que el domain model base esté estabilizado.

***

## 6. Priorización

| Skill | Clasificación |
|-------|---------------|
| `tutti-architecture` | 🔴 Crítica ahora |
| `tutti-domain-model` | 🔴 Crítica ahora |
| `tutti-excel-ingestion` | 🔴 Crítica ahora |
| `tutti-optimizer-dev` | 🔴 Crítica ahora |
| `tutti-backend-dev` | 🔴 Crítica ahora |
| `tutti-workspace-workflow` | 🟠 Siguiente fase |
| `tutti-fleet-operations` | 🟠 Siguiente fase |
| `tutti-frontend-dev` | 🟠 Siguiente fase |
| `tutti-testing` | 🟠 Siguiente fase |
| `tutti-pdf-exports` | 🟠 Siguiente fase |
| `tutti-routing-maps` | 🟡 Medio plazo |
| `tutti-debug-troubleshoot` | 🟡 Medio plazo |
| `tutti-build-deploy` | 🟡 Medio plazo |
| `tutti-drivers-messaging` | ⚪ Futuro |

***

## 7. Gap Analysis

| Estado | Áreas |
|--------|-------|
| ✅ **Cubierto implícitamente** | Parser de Excel (existe código), optimizador V6 (existe), PDF export (existe), validaciones anti-overlap (existe) |
| ⚠️ **Parcialmente cubierto** | Backend dev patterns (probablemente inconsistente), testing (probablemente sin estrategia formal), frontend conventions (probablemente ad-hoc) |
| ❌ **Falta claramente** | Documentación del modelo matemático del optimizer, glosario del dominio, observabilidad estructurada, estrategia de CI/CD, guía de empaquetado Windows |
| 🔀 **Mezclado y debe separarse** | Lógica del domain model mezclada con lógica de servicio (supuesto), validaciones del Excel mezcladas con parseo, estados de workspace mezclados con lógica de flota |
| ⛔ **Puede frenar evolución** | Sin skill de `tutti-drivers-messaging` (ni siquiera como esqueleto), la capa de conductores se construirá sin coherencia con el domain model base. Sin `tutti-optimizer-dev`, cualquier mejora al optimizador tiene alto riesgo de regresión. |

***

## 8. Riesgos por Ausencia de Skills

| Skill Ausente | Riesgo Concreto |
|---------------|-----------------|
| `tutti-architecture` | Agente introduce inconsistencias arquitectónicas cross-módulo; violación de capas; imports circulares |
| `tutti-domain-model` | Confusión Route/Expedition produce bugs semánticos en BD, optimizer y PDF. Invariantes de negocio ignorados silenciosamente |
| `tutti-optimizer-dev` | Constraints eliminados o mal formulados producen asignaciones operativamente inválidas. Modelo infeasible sin diagnóstico. Degradación de rendimiento de segundos a horas |
| `tutti-excel-ingestion` | Lógica defensiva eliminada; archivos Excel reales del cliente comienzan a fallar en producción |
| `tutti-workspace-workflow` | Publicación de workspaces sin validaciones completas; estados inconsistentes; datos de flota corruptos |
| `tutti-testing` | Cobertura concentrada en happy path; regresiones en el optimizer no detectadas; PRs que rompen producción |
| `tutti-build-deploy` | Agente modifica scripts de arranque sin entender las dependencias de orden; EXE de Windows roto en el siguiente release |

***

## 9. Propuesta de Conjunto Inicial de Skills (Primer Paquete)

El primer paquete de skills debe cubrir las rutas críticas del sistema y proteger los módulos más frágiles. Se recomienda crear en este orden:

1. **`tutti-architecture`** — Orientación general, prerequisito de todo lo demás
2. **`tutti-domain-model`** — Entidades y semántica, base del razonamiento sobre el sistema
3. **`tutti-optimizer-dev`** — El módulo más frágil y de mayor riesgo
4. **`tutti-excel-ingestion`** — La fuente de todos los datos; resistencia ante datos reales
5. **`tutti-backend-dev`** — Convenciones del backend para trabajo diario

Este paquete de 5 skills cubre aproximadamente el 70% del riesgo técnico con un esfuerzo de implementación manejable.

***

## 10. Propuesta de Evolución del Sistema de Skills

### Fase 1 — Fundaciones (ahora)
Crear las 5 skills críticas del paquete inicial. Foco en: domain model correcto, protección del optimizer, resiliencia del parser de Excel.

### Fase 2 — Cobertura Operativa (próximas 4-6 semanas)
Agregar: `tutti-workspace-workflow`, `tutti-fleet-operations`, `tutti-frontend-dev`, `tutti-testing`, `tutti-pdf-exports`. En esta fase el equipo tendrá cobertura completa de los flujos operativos principales.

### Fase 3 — Calidad y DevEx (2-3 meses)
Agregar: `tutti-routing-maps`, `tutti-debug-troubleshoot`, `tutti-build-deploy`. Foco en observabilidad, empaquetado y calidad sostenida.

### Fase 4 — Expansión de Producto (según roadmap)
Crear: `tutti-drivers-messaging`. Implementar cuando el domain model base esté estabilizado y se inicie el trabajo en la capa de conductores.

### Principio de Evolución
Aplicar la regla de Cursor: "Add rules only when you notice the agent making the same mistake repeatedly". Cada skill nueva debe surgir de un problema real observado, no de especulación.[^3]

***

## 11. Traducción a Diseño Real de `SKILL.md`

### 11.1 Estructura de un SKILL.md bien diseñado para TUTTI

Según la especificación oficial del Agent Skills standard, cada `SKILL.md` debe tener:[^5][^10]

```markdown
---
name: tutti-<module>
description: <Qué hace + cuándo usarlo — máx 1024 caracteres. Incluir keywords del dominio TUTTI>
disable-model-invocation: false  # true solo para skills destructivas (deploy, publish)
allowed-tools: Read, Grep, Bash(python *)  # ajustar por skill
metadata:
  project: tutti
  domain: <transport-optimization | backend | frontend | ops>
  version: "1.0"
---

## Propósito

<1-2 párrafos: qué resuelve esta skill en el contexto específico de TUTTI>

## Cuándo usar esta skill

- <Situación concreta 1>
- <Situación concreta 2>

## Cuándo NO usar esta skill

- <Anti-patrón 1>
- Si el trabajo involucra <otra área>, usar `tutti-<otra-skill>` en su lugar

## Contexto mínimo de TUTTI

<Qué sabe el agente que activa esta skill: terminología clave, convenciones, restricciones>

## Archivos de referencia

Revisar en este orden:
1. `<ruta/al/archivo_principal.py>` — <por qué es relevante>
2. `<ruta/al/archivo_secundario.py>` — <por qué es relevante>

Ver también: [REFERENCE.md](references/REFERENCE.md) para detalle técnico completo.

## Workflow

1. **Explorar**: Leer archivos de referencia relevantes para entender el estado actual
2. **Planificar**: Identificar cambios necesarios y verificar impacto en módulos dependientes
3. **Implementar**: Seguir las convenciones del proyecto documentadas aquí
4. **Validar**: Verificar contra restricciones y ejecutar tests relevantes

## Convenciones del proyecto

<Convenciones específicas de este módulo: nomenclatura, patrones, estructuras>

## Restricciones y guardrails

⛔ NUNCA <acción prohibida 1> sin revisar <módulo dependiente>
⛔ NUNCA <acción prohibida 2> (razón operativa)
⚠️ Consultar `tutti-<skill>` antes de <acción de alto riesgo>

## Errores frecuentes

| Error | Causa | Cómo evitarlo |
|-------|-------|---------------|
| <error 1> | ausa> | <solución> |

## Outputs esperados

- <Qué debe producir el agente al completar la tarea>

## Señales para derivar a otra skill

- Si la tarea involucra el optimizador → activar `tutti-optimizer-dev`
- Si hay cambios en el domain model → revisar `tutti-domain-model` primero
- Si se necesita testear → activar `tutti-testing`
```

### 11.2 Ejemplo concreto: SKILL.md para `tutti-optimizer-dev`

```markdown
---
name: tutti-optimizer-dev
description: >
  Especialista en el optimizador de asignación de buses de TUTTI (PuLP/ILP). 
  Usar cuando: modificar el modelo ILP, agregar constraints, debuggear asignaciones 
  incorrectas, mejorar rendimiento del solver, entender por qué el modelo es infeasible. 
  Conoce el modelo matemático completo del optimizador V6 y sus restricciones operativas.
disable-model-invocation: false
allowed-tools: Read, Grep, Bash(python *)
metadata:
  project: tutti
  domain: transport-optimization
  risk: high
  version: "1.0"
---

## Propósito

Esta skill guía el trabajo con el optimizador de asignación de buses de TUTTI. 
El optimizador usa Programación Lineal Entera Mixta (MILP) vía PuLP para asignar 
buses a expediciones minimizando costos o maximizando ocupación, respetando 
restricciones de no-solapamiento, capacidad y disponibilidad.

**⚠️ MÓDULO DE ALTO RIESGO**: cambios incorrectos pueden hacer el modelo infeasible 
silenciosamente o producir asignaciones operativamente inválidas.

## Cuándo usar esta skill

- Modificar el modelo PuLP (variables, objetivo, constraints)
- Agregar nuevas restricciones operativas
- Debuggear "el optimizer asigna buses incorrectamente"
- Mejorar tiempo de solución para instancias grandes
- Entender por qué el modelo retorna INFEASIBLE
- Documentar el modelo matemático

## Cuándo NO usar esta skill

- Para cambiar endpoints que llaman al optimizer → usar `tutti-backend-dev`
- Para cambiar el domain model que alimenta al optimizer → usar `tutti-domain-model` primero
- Para escribir tests del optimizer → combinar con `tutti-testing`

## Archivos de referencia

Revisar en este orden:
1. `backend/optimizer/model.py` — Definición completa del modelo PuLP
2. `backend/optimizer/constraints.py` — Todos los constraints con comentarios
3. `backend/optimizer/solver.py` — Configuración del solver y post-procesamiento
4. `tests/test_optimizer.py` — Tests con instancias verificadas
5. `references/OPTIMIZER.md` — Documentación matemática completa

## Workflow

1. **Leer** `backend/optimizer/model.py` completo antes de cualquier cambio
2. **Identificar** el constraint o variable que se quiere modificar
3. **Verificar** coherencia con el domain model (`tutti-domain-model`)
4. **Implementar** el cambio manteniendo la nomenclatura existente
5. **Probar** con instancia pequeña (≤5 buses, ≤20 expediciones) primero
6. **Verificar** que la solución es operativamente válida (no-solapamientos)

## Restricciones y guardrails

⛔ NUNCA eliminar un constraint sin confirmar qué regla operativa representa
⛔ NUNCA cambiar el sentido del objetivo (min↔max) sin validar con el equipo  
⛔ NUNCA asumir que INFEASIBLE = bug; puede ser datos de entrada inconsistentes
⚠️ Consultar `tutti-domain-model` antes de agregar variables que referencien entidades nuevas

## Errores frecuentes

| Error | Causa | Cómo evitarlo |
|-------|-------|---------------|
| Modelo INFEASIBLE sin mensaje claro | Constraints contradictorios | Activar logging de constraints activos |
| Solución subóptima inexplicable | Gap de optimalidad ignorado | Registrar gap en cada ejecución |
| Asignación válida matemáticamente pero inválida operativamente | Constraints faltantes | Validar solución contra domain model post-solve |
| Tiempo de solución degrada exponencialmente | Variables binarias excesivas | Revisar formulación, considerar relajación LP |
```

***

## 12. Relación con Perfiles Humanos

*(Capa secundaria informativa — las skills no reemplazan estos perfiles, los complementan)*

| Skill | Perfil Humano Equivalente |
|-------|--------------------------|
| `tutti-architecture` | Tech Lead / Arquitecto de Software |
| `tutti-domain-model` | Domain Expert + Backend Developer |
| `tutti-excel-ingestion` | Data Engineer |
| `tutti-optimizer-dev` | Operations Research Engineer / Matemático |
| `tutti-backend-dev` | Backend Developer (Python/FastAPI) |
| `tutti-frontend-dev` | Frontend Developer (React) |
| `tutti-fleet-operations` | Product Manager de Operaciones + Backend Dev |
| `tutti-workspace-workflow` | Product Designer + Backend Dev |
| `tutti-testing` | QA Engineer / SDET |
| `tutti-pdf-exports` | Full-Stack Developer con experiencia en reportes |
| `tutti-routing-maps` | GIS Developer / Geospatial Engineer |
| `tutti-debug-troubleshoot` | Site Reliability Engineer (SRE) |
| `tutti-build-deploy` | DevOps / Release Engineer |
| `tutti-drivers-messaging` | Product Manager (futuro) + Backend Dev |

***

## 13. Recomendaciones Accionables

1. **Empezar por `tutti-architecture`** — Sin orientación general, las demás skills operan en el vacío. Esta debe crearse primero aunque sea en formato borrador.

2. **Priorizar `tutti-optimizer-dev` sobre todo lo demás** — Es el módulo más frágil y el de mayor riesgo operativo. Un agente sin esta guía puede romper el corazón del producto.

3. **Crear `tutti-domain-model` con un glosario explícito** — La confusión terminológica (Route vs Expedition) es la fuente más probable de bugs semánticos. Un glosario de 10-15 términos con definiciones precisas vale más que cientos de líneas de documentación técnica.

4. **Marcar `tutti-build-deploy` con `disable-model-invocation: true`** — Ningún agente debe hacer deployments de forma autónoma. Esta skill debe invocarse siempre manualmente.[^11]

5. **Crear `tutti-drivers-messaging` como esqueleto ya** — Aunque no se implemente, reservar la carpeta y escribir un SKILL.md de 20 líneas evita que la futura capa de conductores se construya de forma incoherente.

6. **Limitar el tamaño de cada SKILL.md** — La especificación recomienda menos de 500 líneas / 5000 tokens por archivo. Mover la documentación técnica detallada a `references/REFERENCE.md`.[^10]

7. **Iterar en lugar de perfeccionar** — Empezar con skills imperfectas y mejorarlas basándose en comportamiento observado del agente. No intentar escribir la skill perfecta desde el inicio.[^4]

8. **Versionar las skills junto con el código** — Hacer commit de `.claude/skills/` al repositorio. Las skills son parte del proyecto y deben evolucionar con el código.[^11]

***

## 14. Salida Utilizable por Otro Agente de Código

### A. Proposed Skills Manifest

```yaml
skills:
  - name: tutti-architecture
    description: >
      Orientación general del sistema TUTTI: estructura de carpetas, stack, 
      convenciones, mapa de módulos y dependencias críticas.
    priority: critical
    depends_on: []
    status: create
    reason: >
      Prerequisito de todas las demás skills. Sin ella los agentes 
      introducen inconsistencias arquitectónicas desde el primer commit.

  - name: tutti-domain-model
    description: >
      Entidades del dominio de transporte escolar en TUTTI: Route, Expedition, 
      Stop, Bus, Schedule, WorkspaceState. Semántica, relaciones e invariantes.
    priority: critical
    depends_on: [tutti-architecture]
    status: create
    reason: >
      La confusión terminológica Route/Expedition es la fuente más común 
      de bugs semánticos que se propagan a la BD, optimizer y PDFs.

  - name: tutti-excel-ingestion
    description: >
      Parser de Excel: formato de entrada esperado, normalización, validación 
      de datos sucios, manejo de errores. Usar al tocar el parser o agregar 
      soporte para nuevos formatos de entrada.
    priority: critical
    depends_on: [tutti-domain-model]
    status: create
    reason: >
      Los datos reales de entrada son sucios. Sin guía, se eliminará lógica 
      defensiva que parece redundante pero que maneja casos reales del cliente.

  - name: tutti-optimizer-dev
    description: >
      Optimizador MILP de TUTTI con PuLP. Variables de decisión, constraints 
      operativos, debugging de infeasibility, tuning de rendimiento del solver. 
      MÓDULO DE ALTO RIESGO — activar siempre que se toque el optimizador.
    priority: critical
    depends_on: [tutti-domain-model]
    status: create
    reason: >
      El módulo más frágil del sistema. Constraints mal formulados producen 
      asignaciones inválidas. Un agente sin guía puede romper silenciosamente 
      el corazón funcional del producto.

  - name: tutti-backend-dev
    description: >
      Patrones FastAPI de TUTTI: capas endpoint→service→repository→ORM, 
      schemas Pydantic, gestión de errores, migraciones. Usar para cualquier 
      trabajo en el backend Python.
    priority: critical
    depends_on: [tutti-architecture, tutti-domain-model]
    status: create
    reason: >
      Sin convenciones claras el backend acumula deuda técnica rápidamente 
      (lógica en endpoints, N+1 queries, schemas inconsistentes).

  - name: tutti-workspace-workflow
    description: >
      Flujo de estados del workspace TUTTI: draft→publish→archive. 
      Pre-condiciones de transición, efectos sobre flota y planificación, 
      manejo de errores y rollback.
    priority: important
    depends_on: [tutti-domain-model, tutti-fleet-operations]
    status: create
    reason: >
      Los cambios de estado tienen efectos operativos reales. Sin guía, 
      un agente puede publicar workspaces incompletos o sin validaciones.

  - name: tutti-fleet-operations
    description: >
      Gestión de flota TUTTI: buses reales vs virtuales, reconciliación diaria, 
      commit operativo, estados derivados de asignación.
    priority: important
    depends_on: [tutti-domain-model, tutti-backend-dev]
    status: create
    reason: >
      La reconciliación involucra múltiples fuentes de verdad. Sin guía 
      se generan asignaciones con buses inexistentes.

  - name: tutti-frontend-dev
    description: >
      Frontend React/Vite de TUTTI: componentes, estado, Leaflet para mapas, 
      timeline editable, integración con backend, convenciones de estilos.
    priority: important
    depends_on: [tutti-architecture]
    status: create
    reason: >
      Sin guía se crean componentes monolíticos, se rompe el estado del mapa 
      al tocar el timeline, y se duplica lógica de fetch.

  - name: tutti-testing
    description: >
      Estrategia de testing de TUTTI: pytest por capas, fixtures de dominio, 
      tests del optimizer con instancias verificadas, mocking de OSRM y Excel.
    priority: important
    depends_on: [tutti-domain-model, tutti-backend-dev]
    status: create
    reason: >
      Sin estrategia formal, los tests son superficiales y no detectan 
      regresiones en el optimizer o en las validaciones anti-overlap.

  - name: tutti-pdf-exports
    description: >
      Exportación PDF operativa con ReportLab: estructura de documentos, 
      templates, Google Maps deep links, casos borde. Usar al trabajar 
      en el módulo de exportación.
    priority: important
    depends_on: [tutti-domain-model]
    status: create
    reason: >
      Los PDFs son el output final visible por el cliente. Sin guía se 
      crean documentos con formato inconsistente o links rotos.

  - name: tutti-routing-maps
    description: >
      Integración OSRM y Leaflet: cálculo de rutas, visualización geoespacial, 
      datos de tiempo/distancia para el optimizer, manejo de respuestas OSRM.
    priority: convenient
    depends_on: [tutti-domain-model, tutti-optimizer-dev]
    status: create
    reason: >
      La integración geoespacial tiene edge cases específicos (OSRM sin ruta, 
      coordenadas invertidas) que sin guía se ignoran silenciosamente.

  - name: tutti-debug-troubleshoot
    description: >
      Debugging y observabilidad en TUTTI: logging estructurado FastAPI, 
      diagnóstico de modelos ILP infeasibles, herramientas de profiling 
      del optimizer, debugging de errores de ingesta Excel.
    priority: convenient
    depends_on: [tutti-optimizer-dev, tutti-excel-ingestion]
    status: create
    reason: >
      Sin estrategia de observabilidad, los errores en producción son 
      difíciles de diagnosticar, especialmente en el optimizer.

  - name: tutti-build-deploy
    description: >
      Empaquetado y deployment de TUTTI en Windows: scripts de arranque, 
      PyInstaller EXE, CI/CD, variables de entorno por entorno. 
      SOLO INVOCACIÓN MANUAL — disable-model-invocation: true.
    priority: convenient
    depends_on: [tutti-architecture]
    status: create
    reason: >
      Sin guía, los scripts de arranque se modifican sin entender dependencias 
      de orden. El EXE de Windows puede romperse silenciosamente.

  - name: tutti-drivers-messaging
    description: >
      [FUTURO] Capa de conductores de TUTTI: asignación conductor-vehículo, 
      plan semanal, notificaciones automáticas. No implementar hasta que 
      el domain model base esté estabilizado.
    priority: future
    depends_on: [tutti-domain-model, tutti-fleet-operations, tutti-workspace-workflow]
    status: future
    reason: >
      Reservar estructura ahora para que cuando se implemente sea coherente 
      con el domain model establecido. No implementar prematuramente.
```

***

### B. Suggested Repository Layout

```
.claude/
├── skills/
│   ├── tutti-architecture/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── ARCHITECTURE.md       # Diagrama de capas y módulos
│   │       └── CONVENTIONS.md        # Nomenclatura y patrones
│   │
│   ├── tutti-domain-model/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── DOMAIN.md             # Glosario y definiciones de entidades
│   │       ├── ENTITY-RELATIONS.md   # Diagrama ER textual
│   │       └── INVARIANTS.md         # Invariantes y restricciones de negocio
│   │
│   ├── tutti-excel-ingestion/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── EXCEL-FORMATS.md      # Formatos esperados y variantes
│   │   │   └── DIRTY-DATA-CASES.md   # Casos de datos sucios conocidos
│   │   └── scripts/
│   │       └── validate_excel.py     # Script de validación standalone
│   │
│   ├── tutti-optimizer-dev/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── OPTIMIZER.md          # Documentación matemática del modelo
│   │   │   ├── CONSTRAINTS.md        # Cada constraint con su semántica
│   │   │   └── DEBUGGING.md          # Guía de debugging del ILP
│   │   └── scripts/
│   │       ├── check_feasibility.py  # Diagnóstico de modelos infeasibles
│   │       └── benchmark_solver.py   # Benchmarking del solver
│   │
│   ├── tutti-backend-dev/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── API-PATTERNS.md       # Patrones de endpoints y capas
│   │       └── DB-PATTERNS.md        # Patrones de repositorio y ORM
│   │
│   ├── tutti-workspace-workflow/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── WORKFLOW-STATES.md    # Diagrama de estados y transiciones
│   │
│   ├── tutti-fleet-operations/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── FLEET-RECONCILIATION.md
│   │
│   ├── tutti-frontend-dev/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── COMPONENTS.md         # Catálogo de componentes
│   │       └── LEAFLET-PATTERNS.md   # Patrones específicos de Leaflet
│   │
│   ├── tutti-testing/
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   └── TESTING-STRATEGY.md
│   │   └── templates/
│   │       ├── unit_test_template.py
│   │       └── optimizer_test_template.py
│   │
│   ├── tutti-pdf-exports/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── PDF-TEMPLATES.md
│   │
│   ├── tutti-routing-maps/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── OSRM-API.md
│   │
│   ├── tutti-debug-troubleshoot/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── diagnose_optimizer.py
│   │
│   ├── tutti-build-deploy/
│   │   ├── SKILL.md                  # disable-model-invocation: true
│   │   ├── references/
│   │   │   └── DEPLOY-CHECKLIST.md
│   │   └── scripts/
│   │       └── pre_release_check.sh
│   │
│   └── tutti-drivers-messaging/
│       └── SKILL.md                  # Solo esqueleto, status: future
│
└── CLAUDE.md                         # Contexto siempre activo del proyecto
```

***

### C. Draft SKILL.md Blueprint

Plantilla reusable para crear cada `SKILL.md` de TUTTI:

```markdown
---
name: tutti-<module-name>
description: >
  <Qué hace la skill + cuándo usarla. Incluir keywords del dominio.
  Ser específico: "Usar cuando: X, Y, Z". Máx 1024 caracteres.>
disable-model-invocation: false
allowed-tools: Read, Grep, Bash(python *)
metadata:
  project: tutti
  domain: <transport-optimization|backend|frontend|data|ops|devops>
  risk: ow|medium|high>
  version: "1.0"
---

## Propósito

<Qué problema resuelve esta skill en el contexto específico de TUTTI.
1-2 párrafos. Ser concreto: qué módulo cubre, qué errores previene.>

## Cuándo usar esta skill

- <Situación concreta de activación 1>
- <Situación concreta de activación 2>
- <Situación concreta de activación 3>

## Cuándo NO usar esta skill

- <Anti-patrón de uso 1> — en su lugar, usar `tutti-<otra-skill>`
- <Anti-patrón de uso 2>

## Contexto del proyecto que debes conocer

<Terminología clave, convenciones, restricciones específicas de este módulo.
Esto es lo que un desarrollador senior de TUTTI sabe y que el agente debe conocer.>

**Terminología clave:**
- `<Term>`: <definición precisa en contexto TUTTI>
- `<Term>`: <definición>

## Archivos de referencia

Revisar en este orden antes de hacer cambios:

1. `<ruta/archivo_principal>` — <qué contiene y por qué es relevante>
2. `<ruta/archivo_secundario>` — <qué contiene>
3. `tests/<test_relevante>.py` — <qué cubre>

Para documentación técnica detallada: [REFERENCE.md](references/REFERENCE.md)

## Workflow recomendado

1. **Explorar**: Leer archivos de referencia para entender el estado actual
2. **Revisar dependencias**: Verificar si el cambio impacta <módulos dependientes>
3. **Planificar**: Describir el cambio antes de implementar
4. **Implementar**: Seguir las convenciones documentadas aquí
5. **Validar**: Ejecutar `mando de tests relevante>`

## Convenciones del proyecto

<Convenciones específicas de este módulo. Nomenclatura, patrones, estructuras 
de código obligatorias.>

```python
# Ejemplo de patrón correcto para este módulo
```

## Restricciones y guardrails

⛔ **NUNCA** <acción prohibida 1> — razón: <por qué es peligroso>
⛔ **NUNCA** <acción prohibida 2>
⚠️ **VERIFICAR** con `tutti-<skill>` antes de <acción de riesgo medio>

## Errores frecuentes

| Error | Causa Raíz | Prevención |
|-------|-----------|------------|
| <descripción del error> | ausa> | ómo evitarlo> |

## Outputs esperados

Al completar una tarea con esta skill, el agente debería producir:
- <Output esperado 1>
- <Output esperado 2>

## Señales para derivar a otra skill

- Si el trabajo involucra el optimizador → activar `tutti-optimizer-dev`
- Si hay cambios en entidades de dominio → revisar `tutti-domain-model` primero  
- Si se necesitan tests → activar `tutti-testing`
- Si hay cambios en estados del workspace → activar `tutti-workspace-workflow`
```

***

### D. Skill Creation Backlog

Lista priorizada y secuencial para implementación:

```
SPRINT 1 — FUNDACIONES (Semana 1-2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] #1 tutti-architecture
    - Crear .claude/skills/tutti-architecture/SKILL.md
    - Crear references/ARCHITECTURE.md con diagrama de capas
    - Crear references/CONVENTIONS.md con nomenclatura
    - Fuente: README.md + exploración de carpetas del repo

[ ] #2 tutti-domain-model  
    - Crear .claude/skills/tutti-domain-model/SKILL.md
    - Crear references/DOMAIN.md con glosario Route vs Expedition
    - Crear references/INVARIANTS.md con restricciones de negocio
    - Fuente: backend/models/, backend/schemas/

[ ] #3 tutti-optimizer-dev
    - Crear .claude/skills/tutti-optimizer-dev/SKILL.md
    - Crear references/OPTIMIZER.md con documentación matemática
    - Crear references/CONSTRAINTS.md con semántica de cada constraint
    - Crear scripts/check_feasibility.py
    - Fuente: backend/optimizer/ (módulo completo)

SPRINT 2 — COBERTURA DE DATOS Y BACKEND (Semana 3-4)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] #4 tutti-excel-ingestion
    - Crear .claude/skills/tutti-excel-ingestion/SKILL.md
    - Crear references/EXCEL-FORMATS.md
    - Crear references/DIRTY-DATA-CASES.md
    - Crear scripts/validate_excel.py
    - Fuente: backend/parsers/ o backend/ingestion/

[ ] #5 tutti-backend-dev
    - Crear .claude/skills/tutti-backend-dev/SKILL.md
    - Crear references/API-PATTERNS.md
    - Fuente: backend/api/, backend/services/, backend/repositories/

SPRINT 3 — COBERTURA OPERATIVA (Semana 5-6)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] #6 tutti-workspace-workflow
[ ] #7 tutti-fleet-operations  
[ ] #8 tutti-testing
    - Crear templates/unit_test_template.py
    - Crear templates/optimizer_test_template.py
[ ] #9 tutti-pdf-exports
[ ] #10 tutti-frontend-dev

SPRINT 4 — CALIDAD Y DEVEX (Semana 7-8)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] #11 tutti-routing-maps
[ ] #12 tutti-debug-troubleshoot
[ ] #13 tutti-build-deploy (con disable-model-invocation: true)

FUTURO — RESERVAR ESTRUCTURA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ ] #14 tutti-drivers-messaging (crear solo esqueleto)
```

***

### E. Handoff Notes for Implementation Agent

**Instrucciones para el agente que implemente las skills:**

#### Skills a crear primero (no negociable):
1. `tutti-architecture` — Explorar toda la estructura del repo antes de escribirla
2. `tutti-domain-model` — Leer TODOS los archivos en `backend/models/` y `backend/schemas/`
3. `tutti-optimizer-dev` — Leer el módulo del optimizador completo; documentar CADA constraint con su semántica operativa

#### Skills a crear después:
4. `tutti-excel-ingestion` — Buscar archivos de muestra Excel en el repo; documentar variantes conocidas
5. `tutti-backend-dev` — Identificar el patrón de capas que ya usa el proyecto, no inventar uno nuevo

#### Skills a no tocar todavía:
- `tutti-drivers-messaging` — Solo crear carpeta + SKILL.md esqueleto de 20 líneas
- `tutti-build-deploy` — Crear solo después de entender bien el proceso de arranque actual

#### Archivos del proyecto que revisar para fundamentar cada skill:

| Skill | Archivos Clave a Revisar |
|-------|--------------------------|
| `tutti-architecture` | `README.md`, toda la estructura de carpetas, `requirements.txt`, `package.json` |
| `tutti-domain-model` | `backend/models/`, `backend/schemas/`, migraciones |
| `tutti-optimizer-dev` | `backend/optimizer/` completo, `tests/test_optimizer.py` |
| `tutti-excel-ingestion` | `backend/parsers/` o ingestion, `tests/` de parser, archivos `.xlsx` de fixture |
| `tutti-backend-dev` | `backend/api/`, `backend/services/`, `backend/repositories/` |
| `tutti-workspace-workflow` | `backend/services/workspace_service.py`, modelos de workspace |
| `tutti-fleet-operations` | `backend/fleet/`, modelos de flota, servicio de reconciliación |
| `tutti-frontend-dev` | `frontend/src/` completo, especialmente componentes de mapa y timeline |
| `tutti-testing` | `tests/` completo, `conftest.py`, fixtures existentes |
| `tutti-pdf-exports` | `backend/pdf/` o exports, ejemplos de PDF generados |
| `tutti-routing-maps` | Integración OSRM, componentes Leaflet |
| `tutti-build-deploy` | Scripts de arranque, `Makefile` si existe, CI config |

#### Riesgos a vigilar al implementar:

1. **No inventar convenciones** — Si no encuentras el patrón en el código existente, documentar que "no existe convención establecida" en lugar de inventar una.

2. **El glosario de dominio es lo más crítico** — Invertir tiempo extra en `tutti-domain-model`. Una definición incorrecta de "Expedition" vs "Route" contaminará todas las demás skills.

3. **No copiar código en las skills** — Referenciar archivos con rutas relativas. El código en SKILL.md se vuelve obsoleto rápidamente.[^4][^3]

4. **Mantener SKILL.md bajo 500 líneas** — Si supera ese tamaño, mover contenido a `references/`.[^10]

5. **Testear cada skill con un prompt real** — Después de crear cada SKILL.md, probar con un prompt de ejemplo para verificar que el agente la activa correctamente.[^4]

***

### F. Machine-Friendly Summary (YAML)

```yaml
# TUTTI Agent Skills — Machine-Readable Manifest
# Generado: 2026-03-22
# Versión: 1.0

project: tutti
skills_root: .claude/skills/
claude_md: .claude/CLAUDE.md

skills:
  - name: tutti-architecture
    slug: tutti-architecture
    priority: 1
    criticality: critical
    status: create
    disable_model_invocation: false
    user_invocable: true
    risk: low
    domain: meta
    depends_on: []
    files_to_read:
      - README.md
      - backend/
      - frontend/
      - requirements.txt
      - package.json
    supporting_files:
      - references/ARCHITECTURE.md
      - references/CONVENTIONS.md
    activation_keywords:
      - "arquitectura"
      - "estructura del proyecto"
      - "dónde está"
      - "cómo está organizado"

  - name: tutti-domain-model
    slug: tutti-domain-model
    priority: 2
    criticality: critical
    status: create
    disable_model_invocation: false
    risk: high
    domain: transport-optimization
    depends_on: [tutti-architecture]
    files_to_read:
      - backend/models/
      - backend/schemas/
      - backend/migrations/
    supporting_files:
      - references/DOMAIN.md
      - references/ENTITY-RELATIONS.md
      - references/INVARIANTS.md
    activation_keywords:
      - "domain model"
      - "entidades"
      - "Route"
      - "Expedition"
      - "Bus"
      - "Stop"
      - "Schedule"

  - name: tutti-optimizer-dev
    slug: tutti-optimizer-dev
    priority: 3
    criticality: critical
    status: create
    disable_model_invocation: false
    risk: very_high
    domain: transport-optimization
    depends_on: [tutti-domain-model]
    files_to_read:
      - backend/optimizer/
      - tests/test_optimizer.py
    supporting_files:
      - references/OPTIMIZER.md
      - references/CONSTRAINTS.md
      - references/DEBUGGING.md
      - scripts/check_feasibility.py
      - scripts/benchmark_solver.py
    activation_keywords:
      - "optimizer"
      - "PuLP"
      - "ILP"
      - "constraint"
      - "solver"
      - "infeasible"
      - "asignación de buses"

  - name: tutti-excel-ingestion
    slug: tutti-excel-ingestion
    priority: 4
    criticality: critical
    status: create
    risk: high
    domain: data
    depends_on: [tutti-domain-model]
    files_to_read:
      - backend/parsers/
      - backend/validators/
      - tests/test_excel_parser.py
    supporting_files:
      - references/EXCEL-FORMATS.md
      - references/DIRTY-DATA-CASES.md
      - scripts/validate_excel.py
    activation_keywords:
      - "Excel"
      - "parser"
      - "ingesta"
      - "datos de entrada"
      - "archivo de rutas"

  - name: tutti-backend-dev
    slug: tutti-backend-dev
    priority: 5
    criticality: critical
    status: create
    risk: medium
    domain: backend
    depends_on: [tutti-architecture, tutti-domain-model]
    files_to_read:
      - backend/api/
      - backend/services/
      - backend/repositories/
      - backend/models/
      - backend/schemas/
    supporting_files:
      - references/API-PATTERNS.md
      - references/DB-PATTERNS.md
    activation_keywords:
      - "endpoint"
      - "FastAPI"
      - "servicio"
      - "repositorio"
      - "ORM"
      - "Pydantic"

  - name: tutti-workspace-workflow
    slug: tutti-workspace-workflow
    priority: 6
    criticality: important
    status: create
    risk: high
    domain: operations
    depends_on: [tutti-domain-model, tutti-fleet-operations]
    supporting_files:
      - references/WORKFLOW-STATES.md
    activation_keywords:
      - "workspace"
      - "draft"
      - "publish"
      - "archive"
      - "publicar planificación"
      - "estado del workspace"

  - name: tutti-fleet-operations
    slug: tutti-fleet-operations
    priority: 7
    criticality: important
    status: create
    risk: high
    domain: operations
    depends_on: [tutti-domain-model, tutti-backend-dev]
    supporting_files:
      - references/FLEET-RECONCILIATION.md
    activation_keywords:
      - "flota"
      - "reconciliación"
      - "bus real"
      - "bus virtual"
      - "commit de flota"

  - name: tutti-frontend-dev
    slug: tutti-frontend-dev
    priority: 8
    criticality: important
    status: create
    risk: medium
    domain: frontend
    depends_on: [tutti-architecture]
    supporting_files:
      - references/COMPONENTS.md
      - references/LEAFLET-PATTERNS.md
    activation_keywords:
      - "React"
      - "componente"
      - "Leaflet"
      - "mapa"
      - "timeline"
      - "frontend"

  - name: tutti-testing
    slug: tutti-testing
    priority: 9
    criticality: important
    status: create
    risk: low
    domain: quality
    depends_on: [tutti-domain-model, tutti-backend-dev]
    supporting_files:
      - references/TESTING-STRATEGY.md
      - templates/unit_test_template.py
      - templates/optimizer_test_template.py
    activation_keywords:
      - "test"
      - "pytest"
      - "cobertura"
      - "fixture"
      - "mock"

  - name: tutti-pdf-exports
    slug: tutti-pdf-exports
    priority: 10
    criticality: important
    status: create
    risk: medium
    domain: output
    depends_on: [tutti-domain-model]
    supporting_files:
      - references/PDF-TEMPLATES.md
    activation_keywords:
      - "PDF"
      - "ReportLab"
      - "exportar"
      - "Google Maps link"

  - name: tutti-routing-maps
    slug: tutti-routing-maps
    priority: 11
    criticality: convenient
    status: create
    risk: medium
    domain: geospatial
    depends_on: [tutti-domain-model]
    supporting_files:
      - references/OSRM-API.md
    activation_keywords:
      - "OSRM"
      - "ruta geoespacial"
      - "Leaflet"
      - "mapa"
      - "distancia"
      - "tiempo de trayecto"

  - name: tutti-debug-troubleshoot
    slug: tutti-debug-troubleshoot
    priority: 12
    criticality: convenient
    status: create
    risk: low
    domain: devex
    depends_on: [tutti-optimizer-dev, tutti-excel-ingestion]
    supporting_files:
      - scripts/diagnose_optimizer.py
    activation_keywords:
      - "debug"
      - "error"
      - "log"
      - "no funciona"
      - "diagnóstico"
      - "observabilidad"

  - name: tutti-build-deploy
    slug: tutti-build-deploy
    priority: 13
    criticality: convenient
    status: create
    risk: high
    domain: devops
    disable_model_invocation: true
    depends_on: [tutti-architecture]
    supporting_files:
      - references/DEPLOY-CHECKLIST.md
      - scripts/pre_release_check.sh
    activation_keywords:
      - "deploy"
      - "release"
      - "EXE"
      - "empaquetar"
      - "CI/CD"
      - "Windows"

  - name: tutti-drivers-messaging
    slug: tutti-drivers-messaging
    priority: 14
    criticality: future
    status: future
    risk: medium
    domain: product-expansion
    depends_on: [tutti-domain-model, tutti-fleet-operations, tutti-workspace-workflow]
    notes: >
      Solo crear esqueleto. No implementar hasta que domain model base esté
      estabilizado y se inicie trabajo formal en la capa de conductores.
    activation_keywords:
      - "conductor"
      - "driver"
      - "plan semanal"
      - "mensajería automática"
      - "notificación"

implementation_order:
  sprint_1:
    - tutti-architecture
    - tutti-domain-model
    - tutti-optimizer-dev
  sprint_2:
    - tutti-excel-ingestion
    - tutti-backend-dev
  sprint_3:
    - tutti-workspace-workflow
    - tutti-fleet-operations
    - tutti-testing
    - tutti-pdf-exports
    - tutti-frontend-dev
  sprint_4:
    - tutti-routing-maps
    - tutti-debug-troubleshoot
    - tutti-build-deploy
  future:
    - tutti-drivers-messaging

total_skills: 14
critical_now: 5
important_next: 5
convenient_medium_term: 3
future: 1
```

***

### Lista Concreta de Nombres de Skills

```
tutti-architecture          # Skill meta: orientación general del sistema
tutti-domain-model          # Entidades del dominio de transporte escolar
tutti-excel-ingestion       # Parser y validación de archivos Excel de entrada
tutti-optimizer-dev         # Modelo PuLP/ILP: constraints, debugging, rendimiento
tutti-backend-dev           # FastAPI, capas de servicio, repositorios, ORM
tutti-workspace-workflow    # Estados draft/publish/archive y sus transiciones
tutti-fleet-operations      # Flota real vs virtual, reconciliación, commit
tutti-frontend-dev          # React/Vite, Leaflet, timeline, integración backend
tutti-testing               # Pytest, fixtures de dominio, tests del optimizer
tutti-pdf-exports           # ReportLab, PDFs operativos, Google Maps links
tutti-routing-maps          # OSRM, Leaflet, datos geoespaciales
tutti-debug-troubleshoot    # Logging, observabilidad, diagnóstico de errores
tutti-build-deploy          # Windows packaging, EXE, CI/CD (solo manual)
tutti-drivers-messaging     # [FUTURO] Conductores, plan semanal, mensajería
```

**Sub-skills y archivos de soporte recomendados dentro de `tutti-optimizer-dev`:**
- `references/OPTIMIZER.md` — Documentación matemática completa del modelo MILP
- `references/CONSTRAINTS.md` — Semántica operativa de cada constraint
- `references/DEBUGGING.md` — Guía paso a paso para diagnosticar INFEASIBLE
- `scripts/check_feasibility.py` — Script standalone de diagnóstico
- `scripts/benchmark_solver.py` — Benchmarking con instancias de diferentes tamaños

**Sub-skills y archivos de soporte recomendados dentro de `tutti-domain-model`:**
- `references/DOMAIN.md` — Glosario completo Route/Expedition/Stop/Bus/Schedule
- `references/ENTITY-RELATIONS.md` — Diagrama ER en formato ASCII/Mermaid
- `references/INVARIANTS.md` — Lista de invariantes de negocio obligatorios

---

## References

1. [NeelBansal22/SBRP - School Bus Route Optimization](https://github.com/NeelBansal22/SBRP) - This Python code repository contains an implementation of different algorithms for optimizing school...

2. [shubhika03/School-Bus-Route-Optimization](https://github.com/shubhika03/School-Bus-Route-Optimization) - This repository contains code for constrained school bus route optimization problem in which we are ...

3. [Best practices for coding with agents](https://cursor.com/blog/agent-best-practices) - A comprehensive guide to working with coding agents, from starting with plans to managing context, c...

4. [Skill authoring best practices - Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) - Learn how to write effective Skills that Claude can discover and use successfully.

5. [Agent Skills - Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) - Agent Skills are modular capabilities that extend Claude's functionality. Each Skill packages instru...

6. [Python PuLP Optimization - How to improve performance?](https://stackoverflow.com/questions/73054902/python-pulp-optimization-how-to-improve-performance) - Assuming the model is constructed properly, here are a couple things to try: Solve for 1 week at a t...

7. [coin-or/pulp: A python Linear Programming API](https://github.com/coin-or/pulp) - PuLP is an linear and mixed integer programming modeler written in Python. With PuLP, it is simple t...

8. [FastAPI Scalability: Domain-Driven Modular Monolith Approach](https://www.linkedin.com/posts/abda-bastola-b0447b13a_fastapi-architecture-python-activity-7402131492203810816-ngTK) - The single biggest factor determining if your FastAPI project scales is its folder structure. Forget...

9. [GitHub - kumarsonu676/python-fastapi-starter-api-project: A scalable FastAPI project template with async SQLAlchemy, PostgreSQL, and repository pattern implementation. Features JWT authentication, comprehensive error handling, and follows best practices for building production-ready APIs. Includes modular architecture, dependency injection, Pydantic validation, and Alembic migrations.](https://github.com/kumarsonu676/python-fastapi-starter-api-project) - A scalable FastAPI project template with async SQLAlchemy, PostgreSQL, and repository pattern implem...

10. [Specification - Agent Skills](https://agentskills.io/specification) - The complete format specification for Agent Skills.

11. [Extend Claude with skills - Claude Code Docs](https://code.claude.com/docs/en/skills) - Create, manage, and share skills to extend Claude's capabilities in Claude Code. Includes custom com...


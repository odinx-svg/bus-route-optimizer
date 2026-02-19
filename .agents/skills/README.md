# Tutti Skills - Indice

Este directorio contiene las skills especializadas para el desarrollo del proyecto Tutti Fleet Optimizer.

## Skills Disponibles

| Skill | Descripcion | Uso Principal |
|-------|-------------|---------------|
| `tutti-architecture` | Arquitectura completa del sistema | Entender estructura, flujos de datos, decisiones de diseño |
| `tutti-backend-dev` | Desarrollo backend FastAPI | Crear/modificar codigo Python, modelos, optimizadores |
| `tutti-frontend-dev` | Desarrollo frontend React | Componentes UI, stores, hooks, integraciones API |
| `tutti-frontend-design` | Diseno UI/UX y estilos | Paleta de colores, animaciones, responsive, patrones visuales |
| `image-ui-analyzer` | Analisis de imagenes UI/UX | Extraer diseño de screenshots/mockups para replicar |
| `tutti-build-deploy` | Build y deployment | Generar EXE, releases GitHub, landing Vercel |
| `tutti-debug-troubleshoot` | Debugging y troubleshooting | Diagnosticar errores, performance issues, logs |
| `tutti-testing` | Testing y calidad | Escribir tests pytest/playwright, cobertura |

## Estructura de cada Skill

```
tutti-<nombre>/
├── SKILL.md              # Instrucciones principales (REQUERIDO)
├── references/           # Documentacion adicional
│   └── <topic>.md
└── scripts/              # Scripts reutilizables (opcional)
    └── <script>.py
```

## Uso

Las skills se activan automaticamente cuando se detectan contextos relevantes:

- **tutti-architecture**: "como funciona el sistema", "estructura del proyecto"
- **tutti-backend-dev**: "modificar el optimizador", "nuevo endpoint API"
- **tutti-frontend-dev**: "nuevo componente React", "fix bug en timeline"
- **tutti-frontend-design**: "mejorar UI", "nuevo estilo", "animacion", "colores", "responsive"
- **image-ui-analyzer**: "analiza esta imagen", "copia este diseño", "extrae estilo de", "dashboard como este"
- **tutti-build-deploy**: "generar release", "actualizar landing"
- **tutti-debug-troubleshoot**: "error en", "no funciona", "debug"
- **tutti-testing**: "escribir test", "cobertura de codigo"

## Referencias Cruzadas

Las skills pueden referenciar entre si:
- Arquitectura → Modelos de datos en tutti-backend-dev
- Backend → Testing para escribir tests
- Frontend → Debugging para troubleshooting

## Mantenimiento

Al modificar el proyecto, actualizar las skills correspondientes:

1. Nueva feature backend → Actualizar `tutti-backend-dev`
2. Cambio de arquitectura → Actualizar `tutti-architecture`
3. Nuevo proceso de build → Actualizar `tutti-build-deploy`
4. Nuevo error comun → Agregar a `tutti-debug-troubleshoot`

## Reglas de Oro

1. **Concision**: Las skills deben ser concisas pero completas
2. **Ejemplos**: Preferir ejemplos de codigo sobre explicaciones largas
3. **Actualizacion**: Mantener sincronizadas con cambios en el proyecto
4. **Progresividad**: SKILL.md como entrada, references/ para detalles

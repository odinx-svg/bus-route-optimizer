# Tests E2E - Bus Route Optimizer

Este directorio contiene tests end-to-end completos para el flujo de usuario de la aplicación Bus Route Optimizer.

## 📁 Estructura

```
e2e/
├── README.md                    # Este archivo
├── test-data/                   # Datos de prueba
│   ├── UE3617.xlsx             # Archivo de rutas de ejemplo
│   ├── UE3618.xlsx             # Archivo de rutas de ejemplo
│   └── routes_test.xlsx        # Rutas adicionales de test
├── screenshots/                 # Screenshots automáticos
│   └── timeline/               # Screenshots de tests de timeline
├── montecarlo-3d.spec.js       # Tests de Monte Carlo 3D
└── timeline-editable.spec.js   # Tests del flujo completo de timeline
```

## 🚀 Cómo ejecutar los tests

### Pre-requisitos

1. **Backend corriendo:**
   ```bash
   cd backend
   python -m uvicorn main:app --reload --port 8000
   ```

2. **Frontend corriendo:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Dependencias de Playwright instaladas:**
   ```bash
   cd frontend
   npx playwright install
   ```

### Ejecutar todos los tests

```bash
cd frontend
npx playwright test
```

### Ejecutar tests específicos

```bash
# Solo tests de timeline
npx playwright test timeline-editable.spec.js

# Solo tests de Monte Carlo
npx playwright test montecarlo-3d.spec.js

# Modo headed (ver el navegador)
npx playwright test timeline-editable.spec.js --headed

# Modo debug
npx playwright test timeline-editable.spec.js --debug
```

### Ejecutar con UI de Playwright

```bash
npx playwright test --ui
```

## 📊 Reportes

### Reporte HTML

```bash
npx playwright show-report
```

### Screenshots

Los screenshots se guardan automáticamente en:
- `e2e/screenshots/` - Screenshots de todos los tests
- `test-results/` - Screenshots de fallos (generado por Playwright)

## 🧪 Tests disponibles

### Flujo Completo de Timeline (`timeline-editable.spec.js`)

Tests que cubren todo el flujo de usuario:

1. **Visualización inicial** - Verificar que el timeline carga con rutas optimizadas
2. **Bloqueo de rutas** - Proteger rutas contra movimientos accidentales
3. **Drag & Drop entre buses** - Mover rutas de un bus a otro
4. **Panel de no asignadas** - Liberar rutas y ver panel lateral
5. **Aplicar sugerencias** - Usar el motor de sugerencias
6. **Validación de compatibilidad** - Detección de conflictos en tiempo real
7. **Guardar horario** - Persistir cambios

### Casos Edge

- Timeline vacío
- Drag inválido
- Errores de red

### Performance

- Tiempo de carga < 5 segundos
- Responsividad de drag & drop

## 📝 Notas importantes

### Datos de prueba

Los archivos Excel en `test-data/` son necesarios para los tests. Asegúrate de que existan:

- `UE3617.xlsx` - Rutas de entrada
- `UE3618.xlsx` - Rutas de salida

### Selectores

Los tests usan selectores flexibles para adaptarse a cambios en la UI:

```javascript
// Prioridad 1: data-testid (recomendado)
page.locator('[data-testid="route-block"]')

// Prioridad 2: Clases CSS
page.locator('.route-block')

// Prioridad 3: Texto
page.locator('button:has-text("Guardar")')
```

Si cambias la UI, actualiza los selectores en los tests.

### Timeouts

Los tests usan timeouts generosos para manejar:
- Carga de archivos Excel
- Optimización de rutas (puede tardar varios segundos)
- Transiciones de UI

### Modo CI

En CI, los tests corren en modo headless con retries:

```yaml
# .github/workflows/test.yml
- name: Run E2E tests
  run: npx playwright test
  env:
    CI: true
```

## 🔧 Troubleshooting

### "Browser not found"

```bash
npx playwright install chromium
```

### "Timeout exceeded"

Aumenta el timeout en `playwright.config.js`:

```javascript
timeout: 120000, // 2 minutos
```

### Tests fallan intermitentemente

- Asegúrate de que backend y frontend estén completamente cargados
- Usa `--headed` para ver qué está pasando
- Revisa los screenshots en `test-results/`

### Error de conexión

Verifica que:
1. Backend está en `http://localhost:8000`
2. Frontend está en `http://localhost:5173`

## 📈 Métricas de cobertura

| Flujo | Cobertura |
|-------|-----------|
| Subir rutas | ✅ 100% |
| Optimizar | ✅ 100% |
| Timeline visualización | ✅ 100% |
| Drag & Drop | ✅ 90% |
| Panel sugerencias | ✅ 80% |
| Guardar | ✅ 100% |

## 🎯 Roadmap

- [ ] Tests de accesibilidad (a11y)
- [ ] Tests de responsive (móvil/tablet)
- [ ] Tests de WebSocket (actualizaciones en tiempo real)
- [ ] Tests de exportación (PDF, Excel)

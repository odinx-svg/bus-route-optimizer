# PLAN MAESTRO GSD: Tutti → G.Take UI

## Metodología
- Cada fase es atómica y completa
- No se avanza hasta 100% completion + test passing
- Commits frecuentes con mensajes descriptivos
- Rollback inmediato si algo falla

---

## FASE 0: Análisis y Setup (COMPLETADO)
**Estado:** ✅ DONE
**Tiempo:** 30 min
**Entregables:**
- [x] Skills de análisis creadas
- [x] Paleta de colores G.Take documentada
- [x] Componentes UI base creados (ProgressBar, EmptyState, AvatarStack)
- [x] Build verificado

---

## FASE 1: Variables CSS y Configuración Base
**Tiempo estimado:** 45 min
**Complejidad:** Baja
**Riesgo:** Mínimo

### Tareas:
1.1 Crear `variables.css` con paleta G.Take completa
1.2 Actualizar `tailwind.config.js` con nuevos colores
1.3 Crear `glassmorphism.css` con utilidades
1.4 Test: Verificar build sin errores
1.5 Commit

**Definition of Done:**
- Build exitoso
- Variables CSS aplicables en cualquier componente
- No hay clases Tailwind rotas

---

## FASE 2: Layout Principal (Sidebar + Header)
**Tiempo estimado:** 90 min
**Complejidad:** Media
**Riesgo:** Medio (afecta navegación)

### Tareas:
2.1 Analizar componentes actuales: Layout.jsx, Sidebar.jsx
2.2 Actualizar Sidebar con estilo G.Take (220px, glassmorphism, nav items)
2.3 Actualizar Header con gradiente y tipografía
2.4 Agregar breadcrumbs
2.5 Test: Navegación funciona correctamente
2.6 Test: Responsive no roto
2.7 Commit

**Definition of Done:**
- Sidebar navegable 100%
- Header muestra título y subtítulo
- Logo integrado
- Responsive funciona

---

## FASE 3: Cards y Paneles
**Tiempo estimado:** 60 min
**Complejidad:** Media
**Riesgo:** Bajo-Medio

### Tareas:
3.1 Crear componente `GlassCard.jsx` base
3.2 Actualizar `ControlHubPage.jsx` con nuevas cards
3.3 Actualizar paneles de workspace
3.4 Test: Todos los paneles renderizan contenido
3.5 Commit

**Definition of Done:**
- Cards muestran contenido correctamente
- Glassmorphism visible
- Padding y espaciado correcto

---

## FASE 4: Timeline y RouteBlock (CRÍTICO)
**Tiempo estimado:** 120 min
**Complejidad:** Alta
**Riesgo:** ALTO (core functionality)

### Tareas:
4.1 Analizar `RouteBlock.jsx` existente
4.2 Actualizar estilos manteniendo DnD funcionalidad
4.3 Actualizar `BusRow.jsx` con nuevo diseño
4.4 Actualizar horas/markers en timeline
4.5 Test CRÍTICO: Drag & drop funciona perfectamente
4.6 Test CRÍTICO: Selección de buses funciona
4.7 Test CRÍTICO: Tooltips y validaciones visibles
4.8 Commit

**Definition of Done:**
- DnD funciona igual que antes
- Visualmente transformado
- Sin errores en consola
- Performance no degradado

---

## FASE 5: Botones, Badges y Iconos
**Tiempo estimado:** 45 min
**Complejidad:** Baja
**Riesgo:** Bajo

### Tareas:
5.1 Actualizar estilos de botones primarios/secundarios
5.2 Crear/actualizar componente Badge
5.3 Normalizar uso de iconos (tamaños, colores)
5.4 Test: Todos los botones clickeables
5.5 Commit

**Definition of Done:**
- Botones responden a clicks
- Estados hover/active visibles
- Badges legibles

---

## FASE 6: Estados de Progreso y Feedback
**Tiempo estimado:** 30 min
**Complejidad:** Baja
**Riesgo:** Bajo

### Tareas:
6.1 Integrar ProgressBar en Sidebar/Upload
6.2 Actualizar `OptimizationProgress.tsx` con gradiente
6.3 Actualizar estados de loading
6.4 Test: Progreso visible durante optimización
6.5 Commit

**Definition of Done:**
- Progress bar muestra porcentaje
- Estados de loading son visibles
- Colores consistentes

---

## FASE 7: Polish y Micro-interacciones
**Tiempo estimado:** 45 min
**Complejidad:** Media
**Riesgo:** Bajo

### Tareas:
7.1 Agregar hover effects (lift, glow)
7.2 Agregar transiciones suaves
7.3 Verificar contraste de texto
7.4 Ajustar espaciados finos
7.5 Test: Interacciones suaves
7.6 Commit

**Definition of Done:**
- Hovers funcionan en todos los elementos interactivos
- Transiciones suaves (200-300ms)
- Texto legible en todos los contextos

---

## FASE 8: Testing E2E Completo
**Tiempo estimado:** 60 min
**Complejidad:** Alta
**Riesgo:** Medio

### Tareas:
8.1 Test flujo completo: Upload → Optimize → Edit → Export
8.2 Test responsive en diferentes tamaños
8.3 Test drag & drop extensivo
8.4 Verificar no hay errores en consola
8.5 Build de producción exitoso
8.6 Commit final

**Definition of Done:**
- Todo el flujo funciona sin errores
- Build exitoso
- 0 errores de consola
- Visualmente idéntico al diseño G.Take

---

## CHECKPOINTS DE VALIDACIÓN

### Antes de cada commit:
- [ ] Build sin errores (`npm run build`)
- [ ] No errores en consola del navegador
- [ ] Funcionalidad preservada
- [ ] Cambios visuales verificados

### Antes de avanzar de fase:
- [ ] 100% de tareas de la fase completadas
- [ ] Todos los tests de la fase pasan
- [ ] Revisión visual completada
- [ ] Commit realizado con mensaje descriptivo

---

## ROLLBACK PLAN

Si cualquier fase falla:
```bash
git revert HEAD~N..HEAD  # Revertir N commits
git checkout -- .        # Limpiar cambios no committeados
```

Puntos de rollback seguros:
- Post FASE 1: Solo CSS variables
- Post FASE 2: Layout principal
- Post FASE 4: Timeline (CRÍTICO - testear DnD)
- Post FASE 8: Todo completo

---

## COMANDOS RÁPIDOS

```bash
# Verificar estado
git status
npm run build

# Commit seguro
git add -A
git commit -m "fase-X: descripcion clara"

# Revertir emergencia
git reset --hard HEAD~1
```

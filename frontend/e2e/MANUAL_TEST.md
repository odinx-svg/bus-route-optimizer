# Test Manual - Monte Carlo 3D

## Pre-requisitos
1. Backend corriendo: `cd backend && uvicorn main:app --reload`
2. Frontend corriendo: `cd frontend && npm run dev`

## Pasos para probar Monte Carlo 3D

### 1. Abrir la aplicación
Navega a: http://localhost:5173

### 2. Subir archivos de rutas
- Arrastra los archivos UE3617.xlsx, UE3618.xlsx, etc. al área de drop
- O usa el botón "Examinar"
- Click en "Subir X archivos"

### 3. Optimizar
- Click en botón "Optimizar"
- Espera a que termine (aparecerán las pestañas)

### 4. Abrir Monte Carlo 3D
- Click en pestaña "Monte Carlo 3D"
- Verás el panel de configuración

### 5. Configurar (opcional)
- Click en botón ⚙️ (Settings)
- Ajusta:
  - Número de simulaciones: 100-10000
  - Incertidumbre: 5-50%

### 6. Iniciar simulación
- Click en "Iniciar Simulación"
- Verás:
  - Nube de puntos 3D apareciendo en tiempo real
  - Puntos verdes = factibles
  - Puntos rojos = no factibles
  - Grado A/B/C/D/F calculado dinámicamente
  - Contador de simulaciones

### 7. Interactuar con 3D
- Arrastra para rotar
- Scroll para zoom
- Click en "Pausar" para detener rotación automática
- Click en "Rotar" para reanudar

## Screenshots esperados

### Estado inicial
![initial](screenshots/initial.png)
*Panel de configuración antes de iniciar*

### Simulación corriendo
![running](screenshots/running.png)
*Nube de puntos 3D en tiempo real*

### Resultado final
![completed](screenshots/completed.png)
*Grado final y estadísticas*

## Verificación de componentes

| Componente | ¿Visible? | ¿Funciona? |
|-----------|-----------|------------|
| Pestaña "Monte Carlo 3D" | [ ] | - |
| Botón "Iniciar Simulación" | [ ] | [ ] |
| Canvas 3D | [ ] | [ ] |
| Puntos verdes (factibles) | [ ] | - |
| Puntos rojos (no factibles) | [ ] | - |
| Overlay con Grado | [ ] | - |
| Controles de rotación | [ ] | [ ] |
| Panel de configuración | [ ] | [ ] |
| Leyenda Factible/No factible | [ ] | - |

## Notas
- La simulación de 1000 escenarios tarda ~20 segundos
- Los puntos aparecen en batches de 50
- Puedes detener y reiniciar la simulación
- El grado se actualiza en tiempo real
